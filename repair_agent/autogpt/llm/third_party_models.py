"""Official API pricing for OpenAI-compatible third-party models (DeepSeek, Qwen, etc.)."""

from __future__ import annotations

from autogpt.llm.base import ChatModelInfo

# Prices are $/1M tokens (same convention as comments in openai.py / anthropic.py).
# ApiManager converts via: tokens * cost / 1000  (see api_manager.update_cost).

_THIRD_PARTY_SPECS: dict[str, tuple[float, float, int]] = {
    # DeepSeek V3.2 — official rate card (retired 2026-04-24; still used via proxies)
    "deepseek-v3.2": (0.28, 0.42, 128000),
    # Qwen3-Next-80B-A3B-Instruct — Alibaba Cloud DashScope official pricing
    "qwen3-next-80b-a3b-instruct": (0.15, 1.20, 262144),
}

# Bedrock / OpenRouter / provider-specific IDs → canonical pricing key
MODEL_PRICING_ALIASES: dict[str, str] = {
    "deepseek.v3.2": "deepseek-v3.2",
    "deepseek/deepseek-v3.2": "deepseek-v3.2",
    "deepseek-v3.2-exp": "deepseek-v3.2",
    "qwen.qwen3-next-80b-a3b-instruct": "qwen3-next-80b-a3b-instruct",
    "qwen/qwen3-next-80b-a3b-instruct": "qwen3-next-80b-a3b-instruct",
    "dashscope/qwen3-next-80b-a3b-instruct": "qwen3-next-80b-a3b-instruct",
}


def _per_mtok_to_cost_field(dollars_per_million: float) -> float:
    return dollars_per_million / 1000


def build_third_party_chat_models() -> dict[str, ChatModelInfo]:
    models: dict[str, ChatModelInfo] = {}
    for name, (input_m, output_m, max_tokens) in _THIRD_PARTY_SPECS.items():
        models[name] = ChatModelInfo(
            name=name,
            prompt_token_cost=_per_mtok_to_cost_field(input_m),
            completion_token_cost=_per_mtok_to_cost_field(output_m),
            max_tokens=max_tokens,
            supports_functions=False,
        )
    for alias, target in MODEL_PRICING_ALIASES.items():
        if target in models:
            alias_info = ChatModelInfo(**models[target].__dict__)
            alias_info.name = alias
            models[alias] = alias_info
    return models


def normalize_model_name(model: str) -> str:
    """Normalize provider-specific model IDs for pricing lookup."""
    normalized = model.strip()
    if normalized.endswith("-v2"):
        normalized = normalized[:-3]

    lowered = normalized.lower()
    if lowered in MODEL_PRICING_ALIASES:
        return MODEL_PRICING_ALIASES[lowered]

    if lowered in _THIRD_PARTY_SPECS:
        return lowered

    if "/" in normalized:
        tail = normalized.split("/")[-1].lower()
        if tail in MODEL_PRICING_ALIASES:
            return MODEL_PRICING_ALIASES[tail]
        if tail in _THIRD_PARTY_SPECS:
            return tail

    if "." in normalized:
        parts = normalized.split(".")
        if len(parts) == 2:
            candidate = f"{parts[0]}-{parts[1]}".lower()
            if candidate in _THIRD_PARTY_SPECS:
                return candidate
            if candidate in MODEL_PRICING_ALIASES:
                return MODEL_PRICING_ALIASES[candidate]
        if len(parts) >= 2 and parts[0].lower() in ("qwen", "deepseek"):
            candidate = parts[-1].lower()
            if candidate in _THIRD_PARTY_SPECS:
                return candidate
            if candidate in MODEL_PRICING_ALIASES:
                return MODEL_PRICING_ALIASES[candidate]

    return normalized


def resolve_pricing_model(model: str) -> str:
    """Return the ALL_MODELS key to use for cost calculation."""
    normalized = normalize_model_name(model)
    if normalized in _THIRD_PARTY_SPECS:
        return normalized
    if normalized in MODEL_PRICING_ALIASES:
        return MODEL_PRICING_ALIASES[normalized]
    return normalized
