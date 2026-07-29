"""
backend/llm.py

The one file that knows about Gemini. Everything else (tools.py, chat.py) stays
provider-neutral. This wrapper:

  - reads the API key + model from .env
  - turns our TOOL_SCHEMAS into Gemini's function-calling format
  - calls the model with retry + exponential backoff on rate limits (429),
    then falls back to a lighter model if the primary's quota is exhausted
  - returns a normalized result the chat loop understands

Free-tier note: quota is enforced per Google Cloud PROJECT, not per key — each
student needs their own project, or the whole class shares one tiny quota.
"""

from __future__ import annotations

import logging
import os
import random
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types

from backend.tools import TOOL_SCHEMAS

load_dotenv()
logger = logging.getLogger(__name__)

# --- Model configuration (change models here, or override in .env) ----------
# Primary: best quality/limit balance for tool-calling on the free tier.
# Fallback(s): tried in order when the primary is rate-limited or out of quota.
PRIMARY_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
FALLBACK_MODELS = ["gemini-2.5-flash-lite"]

MAX_RETRIES = 5          # backoff attempts per model before giving up on it
MAX_BACKOFF_SECONDS = 16

_client = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Add it to your .env file."
            )
        _client = genai.Client(api_key=key)
    return _client


# Our schemas are already in FunctionDeclaration shape (name/description/parameters).
_GEMINI_TOOLS = types.Tool(function_declarations=TOOL_SCHEMAS)


def _is_transient(exc: Exception) -> bool:
    """True for errors worth retrying: rate limits AND temporary server errors.

    429 / RESOURCE_EXHAUSTED = you hit a quota.
    503 UNAVAILABLE, 500, 502, 504 = Google's side is briefly overloaded.
    Both clear on their own, so both get backoff-and-retry.
    """
    text = str(exc).lower()
    return any(s in text for s in (
        "429", "resource_exhausted", "quota", "rate limit",          # rate limits
        "503", "unavailable", "500", "internal", "502", "504",       # transient server errors
    ))


def _normalize(response) -> dict:
    """Convert a Gemini response into a provider-neutral result dict."""
    calls = getattr(response, "function_calls", None)
    content = response.candidates[0].content if response.candidates else None
    if calls:
        return {
            "type": "tool_calls",
            "calls": [{"name": c.name, "args": dict(c.args or {})} for c in calls],
            "content": content,   # the model's turn, to append to history
        }
    # No tool calls -> a plain text answer.
    text = ""
    try:
        text = response.text or ""
    except Exception:
        pass
    return {"type": "text", "text": text, "content": content}


def generate(contents, system_instruction: str | None = None) -> dict:
    """One model turn over the given conversation `contents`.

    Returns {"type": "tool_calls", "calls": [...], "content": ...}
        or  {"type": "text", "text": "...", "content": ...}

    Handles rate limits with exponential backoff + jitter, then falls back to
    lighter models. Non-rate-limit errors are raised immediately.
    """
    client = _get_client()
    config = types.GenerateContentConfig(
        tools=[_GEMINI_TOOLS],
        system_instruction=system_instruction,
        temperature=0.2,  # low -> consistent tool choices
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    last_error = None
    for model_name in [PRIMARY_MODEL, *FALLBACK_MODELS]:
        for attempt in range(MAX_RETRIES):
            try:
                response = client.models.generate_content(
                    model=model_name, contents=contents, config=config,
                )
                if model_name != PRIMARY_MODEL:
                    logger.info("Answered with fallback model %s", model_name)
                return _normalize(response)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if not _is_transient(exc):
                    raise  # real error (bad request, auth) -> surface now
                if attempt < MAX_RETRIES - 1:
                    wait = min(2 ** attempt, MAX_BACKOFF_SECONDS) + random.uniform(0, 1)
                    logger.warning("Transient error on %s (attempt %d/%d): %s; waiting %.1fs",
                                   model_name, attempt + 1, MAX_RETRIES,
                                   type(exc).__name__, wait)
                    time.sleep(wait)
                else:
                    logger.warning("%s failing after %d attempts; trying fallback",
                                   model_name, MAX_RETRIES)
    raise RuntimeError(f"All models exhausted. Last error: {last_error}")


# --- Helpers for chat.py to build conversation `contents` ------------------
def user_message(text: str) -> types.Content:
    return types.Content(role="user", parts=[types.Part(text=text)])


def tool_result_message(name: str, result) -> types.Content:
    """Wrap a tool's return value as a function response the model can read."""
    return types.Content(
        role="user",
        parts=[types.Part.from_function_response(name=name, response={"result": result})],
    )