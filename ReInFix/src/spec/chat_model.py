"""LangChain chat model factory for ReInFix spec pipeline."""

from __future__ import annotations

import os
from typing import Optional


def _default_temperature(model: str) -> float:
    temperature = float(os.environ.get("TEMPERATURE", "0.0"))
    if model.startswith("gpt-5"):
        return 1.0
    return temperature


def get_langchain_chat_model(model: str, temperature: Optional[float] = None):
    """Return ChatOpenAI using ReInFix config / environment API settings."""
    if temperature is None:
        temperature = _default_temperature(model)

    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        from langchain.chat_models import ChatOpenAI

    kwargs = {"model": model, "temperature": temperature}

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        try:
            from src.config import OPENAI_API_KEY as cfg_key

            api_key = cfg_key
        except ImportError:
            pass
    if api_key:
        kwargs["openai_api_key"] = api_key

    api_base = os.environ.get("OPENAI_API_BASE") or os.environ.get("OPENAI_API_BASE_URL")
    if api_base:
        kwargs["openai_api_base"] = api_base

    return ChatOpenAI(**kwargs)
