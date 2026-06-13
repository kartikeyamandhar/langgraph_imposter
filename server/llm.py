"""Thin LLM interface. All LLM access goes through here so tests can mock one seam.

Model id comes from MODEL_ID env, defaulting to a cheap fast model class.
"""

import os
from functools import lru_cache

DEFAULT_MODEL_ID = "claude-haiku-4-5-20251001"


@lru_cache(maxsize=1)
def get_chat_model():  # pragma: no cover - exercised only with a live key
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(
        model_name=os.environ.get("MODEL_ID", DEFAULT_MODEL_ID), timeout=30, stop=None
    )
