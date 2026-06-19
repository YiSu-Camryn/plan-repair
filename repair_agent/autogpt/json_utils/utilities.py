"""Utilities for the json_fixes package."""
import ast
import json
import os.path
from json_repair import repair_json
from typing import Any, Literal

from jsonschema import Draft7Validator

from autogpt.config import Config
from autogpt.logs import logger

LLM_DEFAULT_RESPONSE_FORMAT = "llm_response_format_1"


def extract_dict_from_response(response_content: str) -> dict[str, Any]:
    # Sometimes the response includes the JSON in a code block with ```
    start_triple_quote = response_content.find("```")
    if start_triple_quote != -1:
        response_content = response_content[start_triple_quote:]
        end_triple_quote = response_content[3:].find("```")
        if end_triple_quote != -1:
            response_content = response_content[:end_triple_quote+3]
            if response_content.startswith('json'):
                response_content = response_content[4:]
            response_content = "\n".join(response_content.split("\n")[1:])
            
        """if response_content.startswith("```") and response_content.endswith("```"):
            response_content = response_content.split("\n")[1:]
            for i in range(len(response_content)-1, 0, -1):
                if response_content[i]=="```":
                    response_content = response_content[:i]
                    break
            response_content = "\n".join(response_content)"""
            # Discard the first and last ```, then re-join in case the response naturally included ```
            #response_content = "```".join(response_content.split("```")[1:-1])

    # Repair malformed JSON before parsing (trailing commas, single quotes, etc.)
    response_content = repair_json(response_content)

    if not response_content or not response_content.strip():
        return {}

    # Try json.loads first (handles null/true/false correctly).
    # Fall back to ast.literal_eval for Python-dict-style responses (single quotes, etc.).
    try:
        result = json.loads(response_content)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    try:
        result = ast.literal_eval(response_content)
        if isinstance(result, dict):
            return result
    except BaseException:
        pass

    logger.debug(f"Could not parse response as dict: {response_content[:200]}")
    return {}


def normalize_llm_response_dict(raw: dict[str, Any]) -> dict[str, Any]:
    """Coerce common alternate LLM JSON shapes into the RepairAgent schema.

    Some models return {"command": "read_range", "params": {...}} instead of
    {"thoughts": "...", "command": {"name": "read_range", "args": {...}}}.
    """
    if not isinstance(raw, dict) or not raw:
        return {"thoughts": "Proceeding with the next repair step.", "command": {"name": "missing_command", "args": {}}}

    data = dict(raw)

    nested = data.get("next_command")
    if isinstance(nested, dict):
        for key, value in nested.items():
            if key not in data or data[key] in (None, "", {}):
                data[key] = value

    extra_args: dict[str, Any] = {}
    for key in ("params", "arguments"):
        value = data.pop(key, None)
        if isinstance(value, dict):
            extra_args.update(value)

    thoughts = data.get("thoughts") or data.get("reasoning") or data.get("thought")
    if not thoughts:
        thoughts = "Proceeding with the next repair step."

    cmd = data.get("command")
    if isinstance(cmd, str):
        command = {"name": cmd, "args": dict(extra_args)}
    elif isinstance(cmd, dict):
        name = cmd.get("name") or cmd.get("command")
        args = cmd.get("args")
        if not isinstance(args, dict):
            args = {}
        for alt_key in ("params", "arguments"):
            alt = cmd.get(alt_key)
            if isinstance(alt, dict):
                args = {**alt, **args}
        args = {**extra_args, **args}
        if isinstance(name, str) and name:
            command = {"name": name, "args": args}
        else:
            command = {"name": "missing_command", "args": args}
    else:
        command = {"name": "missing_command", "args": dict(extra_args)}

    if "args" not in command or not isinstance(command["args"], dict):
        command["args"] = {}

    normalized = {"thoughts": str(thoughts), "command": command}
    if normalized != {"thoughts": data.get("thoughts"), "command": data.get("command")}:
        logger.info(
            "Normalized alternate LLM response format to command.name/args "
            "(command={})".format(command.get("name"))
        )
    return normalized


def llm_response_schema(
    config: Config, schema_name: str = LLM_DEFAULT_RESPONSE_FORMAT
) -> dict[str, Any]:
    filename = os.path.join(os.path.dirname(__file__), f"{schema_name}.json")
    with open(filename, "r") as f:
        try:
            json_schema = json.load(f)
        except Exception as e:
            raise RuntimeError(f"Failed to load JSON schema: {e}")
    if config.openai_functions:
        del json_schema["properties"]["command"]
        json_schema["required"].remove("command")
    return json_schema


def validate_dict(
    object: object, config: Config, schema_name: str = LLM_DEFAULT_RESPONSE_FORMAT
) -> tuple[Literal[True], None] | tuple[Literal[False], list]:
    """
    :type schema_name: object
    :param schema_name: str
    :type json_object: object

    Returns:
        bool: Whether the json_object is valid or not
        list: Errors found in the json_object, or None if the object is valid
    """
    schema = llm_response_schema(config, schema_name)
    validator = Draft7Validator(schema)

    if errors := sorted(validator.iter_errors(object), key=lambda e: e.path):
        for error in errors:
            logger.debug(f"JSON Validation Error: {error}")

        if config.debug_mode:
            logger.error(json.dumps(object, indent=4))
            logger.error("The following issues were found:")

            for error in errors:
                logger.error(f"Error: {error.message}")
        return False, errors

    logger.debug("The JSON object is valid.")

    return True, None
