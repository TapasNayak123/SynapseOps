"""Amazon Bedrock client — delegates to app.services.llm (single source of truth).

Root-level modules that do `from bedrock_client import invoke_model` continue to work.
Uses the BEDROCK_MODEL_ID from config (supports nova, anthropic, meta models).
"""

from __future__ import annotations

import threading
from config import BEDROCK_MODEL_ID
from app.services.llm import LLMService

_service = None
_service_lock = threading.Lock()


def _get_service() -> LLMService:
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = LLMService(model_id=BEDROCK_MODEL_ID)
    return _service


def invoke_model(prompt: str, max_tokens: int = 4096) -> str:
    """Invoke a Bedrock model with the given prompt and return the response text."""
    return _get_service().invoke(prompt, max_tokens=max_tokens)
