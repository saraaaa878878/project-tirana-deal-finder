"""
backend/llm.py

Gemini wrapper for Tirana Deal Finder.

Responsibilities:
  - read API/model settings from .env
  - expose the backend tool schemas to Gemini
  - perform manual function-calling turns
  - retry temporary failures and use fallback models
  - normalize Gemini responses for backend/chat.py
"""

from __future__ import annotations

import logging
import os
import random
import time
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types

from backend.tools import TOOL_SCHEMAS


load_dotenv()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Environment configuration
# ---------------------------------------------------------------------------

def _env_int(name: str, default: int, minimum: int = 0) -> int:
    """Read a bounded integer from the environment."""
    raw = os.getenv(name)
    if raw is None:
        return default

    try:
        return max(minimum, int(raw))
    except ValueError:
        logger.warning("Invalid %s=%r; using %d", name, raw, default)
        return default


def _env_float(name: str, default: float, minimum: float = 0.0) -> float:
    """Read a bounded float from the environment."""
    raw = os.getenv(name)
    if raw is None:
        return default

    try:
        return max(minimum, float(raw))
    except ValueError:
        logger.warning("Invalid %s=%r; using %.2f", name, raw, default)
        return default


PRIMARY_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

FALLBACK_MODELS = [
    name.strip()
    for name in os.getenv(
        "GEMINI_FALLBACK_MODELS",
        "gemini-2.5-flash-lite",
    ).split(",")
    if name.strip()
]

MAX_RETRIES = _env_int("GEMINI_MAX_RETRIES", 5, minimum=1)
MAX_BACKOFF_SECONDS = _env_float(
    "GEMINI_MAX_BACKOFF_SECONDS",
    16.0,
    minimum=1.0,
)
REQUEST_TIMEOUT_MS = _env_int(
    "GEMINI_TIMEOUT_MS",
    45_000,
    minimum=1_000,
)
TEMPERATURE = _env_float("GEMINI_TEMPERATURE", 0.2, minimum=0.0)


# ---------------------------------------------------------------------------
# Client + tools
# ---------------------------------------------------------------------------

_client: genai.Client | None = None

_GEMINI_TOOLS = types.Tool(
    function_declarations=TOOL_SCHEMAS,
)


def _get_client() -> genai.Client:
    """Create and cache one Gemini client."""
    global _client

    if _client is None:
        api_key = (os.getenv("GEMINI_API_KEY") or "").strip()

        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Add it to the project's .env file."
            )

        _client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=REQUEST_TIMEOUT_MS,
            ),
        )

    return _client


def close_client() -> None:
    """Close network resources, mainly useful in tests or shutdown hooks."""
    global _client

    if _client is not None:
        try:
            _client.close()
        finally:
            _client = None


# ---------------------------------------------------------------------------
# Errors and retries
# ---------------------------------------------------------------------------

_TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}


def _status_code(exc: Exception) -> int | None:
    """Extract an HTTP-like status code from SDK exceptions when available."""
    for attr in ("status_code", "code"):
        value = getattr(exc, attr, None)

        try:
            if value is not None:
                return int(value)
        except (TypeError, ValueError):
            continue

    return None


def _is_transient(exc: Exception) -> bool:
    """Return True for quota, timeout, and temporary server failures."""
    status = _status_code(exc)
    if status in _TRANSIENT_STATUS_CODES:
        return True

    text = str(exc).lower()

    return any(
        marker in text
        for marker in (
            "429",
            "resource_exhausted",
            "quota",
            "rate limit",
            "timeout",
            "timed out",
            "503",
            "unavailable",
            "500",
            "internal",
            "502",
            "504",
        )
    )


def _backoff_seconds(attempt: int) -> float:
    """Exponential backoff with jitter."""
    exponential = min(2 ** attempt, MAX_BACKOFF_SECONDS)
    return exponential + random.uniform(0.0, 1.0)


# ---------------------------------------------------------------------------
# Response normalization
# ---------------------------------------------------------------------------

def _usage_dict(response: Any) -> dict:
    """Extract token usage when the SDK returns it."""
    usage = getattr(response, "usage_metadata", None)

    if usage is None:
        return {}

    return {
        "prompt_tokens": getattr(usage, "prompt_token_count", None),
        "response_tokens": getattr(usage, "candidates_token_count", None),
        "total_tokens": getattr(usage, "total_token_count", None),
    }


def _normalize(response: Any, model_name: str) -> dict:
    """Convert a Gemini response into the format backend/chat.py expects."""
    candidates = getattr(response, "candidates", None) or []

    if not candidates:
        feedback = getattr(response, "prompt_feedback", None)
        raise RuntimeError(
            f"Gemini returned no response candidates. Prompt feedback: {feedback}"
        )

    candidate = candidates[0]
    content = getattr(candidate, "content", None)
    finish_reason = getattr(candidate, "finish_reason", None)

    calls = getattr(response, "function_calls", None) or []

    if calls:
        normalized_calls = []

        for call in calls:
            normalized_calls.append({
                "name": call.name,
                "args": dict(call.args or {}),
                # Gemini 3 returns an id. Older models may leave it absent.
                "id": getattr(call, "id", None),
            })

        return {
            "type": "tool_calls",
            "calls": normalized_calls,
            "content": content,
            "model": model_name,
            "finish_reason": str(finish_reason) if finish_reason else None,
            "usage": _usage_dict(response),
        }

    try:
        text = (response.text or "").strip()
    except Exception:
        text = ""

    if not text:
        raise RuntimeError(
            "Gemini returned neither text nor a function call. "
            f"Finish reason: {finish_reason}"
        )

    return {
        "type": "text",
        "text": text,
        "content": content,
        "model": model_name,
        "finish_reason": str(finish_reason) if finish_reason else None,
        "usage": _usage_dict(response),
    }


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def _generation_config(
    system_instruction: str | None,
) -> types.GenerateContentConfig:
    """Build one request configuration."""
    return types.GenerateContentConfig(
        tools=[_GEMINI_TOOLS],
        system_instruction=system_instruction,
        temperature=TEMPERATURE,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(
            disable=True,
        ),
    )


def generate(
    contents,
    system_instruction: str | None = None,
) -> dict:
    """Run one Gemini turn with retry and fallback handling."""
    if not contents:
        raise ValueError("contents must contain at least one message.")

    client = _get_client()
    config = _generation_config(system_instruction)

    # Remove duplicate model names while preserving order.
    model_names = list(
        dict.fromkeys([PRIMARY_MODEL, *FALLBACK_MODELS])
    )

    last_error: Exception | None = None

    for model_name in model_names:
        for attempt in range(MAX_RETRIES):
            started = time.perf_counter()

            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config,
                )

                normalized = _normalize(response, model_name)
                elapsed = time.perf_counter() - started

                logger.info(
                    "Gemini response model=%s type=%s elapsed=%.2fs "
                    "total_tokens=%s",
                    model_name,
                    normalized["type"],
                    elapsed,
                    normalized.get("usage", {}).get("total_tokens"),
                )

                if model_name != PRIMARY_MODEL:
                    logger.info(
                        "Primary model unavailable; answered with fallback %s",
                        model_name,
                    )

                return normalized

            except Exception as exc:  # noqa: BLE001
                last_error = exc

                if not _is_transient(exc):
                    logger.exception(
                        "Non-transient Gemini error on model %s",
                        model_name,
                    )
                    raise

                if attempt < MAX_RETRIES - 1:
                    wait = _backoff_seconds(attempt)

                    logger.warning(
                        "Temporary Gemini error model=%s attempt=%d/%d "
                        "error=%s; retrying in %.1fs",
                        model_name,
                        attempt + 1,
                        MAX_RETRIES,
                        type(exc).__name__,
                        wait,
                    )
                    time.sleep(wait)
                else:
                    logger.warning(
                        "Model %s failed after %d attempts; trying fallback.",
                        model_name,
                        MAX_RETRIES,
                    )

    raise RuntimeError(
        "All configured Gemini models failed. "
        f"Last error: {type(last_error).__name__}: {last_error}"
    ) from last_error


# ---------------------------------------------------------------------------
# Conversation helpers used by backend/chat.py
# ---------------------------------------------------------------------------

def user_message(text: str) -> types.Content:
    """Create one validated Gemini user message."""
    text = str(text or "").strip()

    if not text:
        raise ValueError("User message cannot be empty.")

    return types.Content(
        role="user",
        parts=[types.Part(text=text)],
    )


def tool_result_message(
    name: str,
    result,
    call_id: str | None = None,
) -> types.Content:
    """Wrap a real tool result so Gemini can continue the conversation."""
    kwargs = {
        "name": name,
        "response": {"result": result},
    }

    if call_id:
        kwargs["id"] = call_id

    try:
        part = types.Part.from_function_response(**kwargs)
    except TypeError:
        # Compatibility with SDK/model combinations that do not accept ids.
        kwargs.pop("id", None)
        part = types.Part.from_function_response(**kwargs)

    return types.Content(
        role="user",
        parts=[part],
    )