"""Shared LangChain chat model factory (OpenAI-compatible proxy + native Anthropic)."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from autogpt.config import Config


def _default_temperature(model: str) -> float:
    temperature = float(os.environ.get("TEMPERATURE", "0.0"))
    if model.startswith("gpt-5"):
        return 1.0
    return temperature


def get_langchain_chat_model(
    model: str,
    config: Optional["Config"] = None,
    temperature: Optional[float] = None,
):
    """Return ChatAnthropic or ChatOpenAI based on model and API routing config."""
    from autogpt.config import Config
    from autogpt.llm.providers.anthropic import use_anthropic_native_api

    if config is None:
        config = Config()
    if temperature is None:
        temperature = _default_temperature(model)

    if use_anthropic_native_api(model, config):
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=model, temperature=temperature)

    from langchain.chat_models import ChatOpenAI

    kwargs = {"model": model, "temperature": temperature}
    credentials = config.get_openai_credentials(model)
    if credentials.get("api_key"):
        kwargs["openai_api_key"] = credentials["api_key"]
    if credentials.get("api_base"):
        kwargs["openai_api_base"] = credentials["api_base"]
    return ChatOpenAI(**kwargs)
