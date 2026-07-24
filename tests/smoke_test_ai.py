"""
tests/smoke_test_ai.py

Health check for the AI layer — runs WITHOUT spending any API calls.

It verifies the parts that don't need the network: every tool runs and returns
JSON-serializable data, the schemas are well-formed, dispatch handles bad input,
and the chat loop correctly runs tools + respects its iteration cap (using a
scripted/mock model in place of Gemini).

    python tests/smoke_test_ai.py

For a real end-to-end check against Gemini (uses ~1 API call), see the bottom.
Exits 0 if all checks pass, 1 otherwise.
"""

import json
import os
import sys
import types as pytypes
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# A dummy key lets us import llm.py without a real one (we mock the network).
os.environ.setdefault("GEMINI_API_KEY", "dummy-key-for-offline-test")

from backend import tools, chat, llm  # noqa: E402

_passed = 0
_failed = 0


def check(name, condition, detail=""):
    global _passed, _failed
    mark = "PASS" if condition else "FAIL"
    _passed += 1 if condition else 0
    _failed += 0 if condition else 1
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))


def section(title):
    print(f"\n=== {title} ===")


# ---------------------------------------------------------------------------
# 1. Tools + schemas
# ---------------------------------------------------------------------------
section("Tools & schemas")
check("six tools registered", len(tools.TOOLS) == 6, f"{len(tools.TOOLS)}")
check("one schema per tool", len(tools.TOOL_SCHEMAS) == len(tools.TOOLS))

schema_names = {s["name"] for s in tools.TOOL_SCHEMAS}
check("schema names match functions", schema_names == set(tools.TOOLS))
check("every schema has a description",
      all(s.get("description") for s in tools.TOOL_SCHEMAS))
check("every schema declares parameters",
      all("parameters" in s and "properties" in s["parameters"] for s in tools.TOOL_SCHEMAS))

# ---------------------------------------------------------------------------
# 2. Each tool runs through dispatch and returns JSON-serializable data
# ---------------------------------------------------------------------------
section("Tool execution (via dispatch)")
sample_calls = {
    "search_properties": {"max_price": 150000, "limit": 3},
    "find_best_deals": {"limit": 3},
    "get_property_details": {"property_id": 0},
    "estimate_price": {"square_meters": 85, "bedrooms": 2},
    "get_market_stats": {},
    "compare_property_to_market": {"property_id": 0},
}
for name in tools.TOOLS:
    result = tools.dispatch(name, sample_calls[name])
    ok_json = True
    try:
        json.dumps(result, default=str)
    except Exception:
        ok_json = False
    no_error = not (isinstance(result, dict) and "error" in result)
    check(f"{name} runs & is JSON-serializable", ok_json and no_error)

# ---------------------------------------------------------------------------
# 3. Dispatch robustness
# ---------------------------------------------------------------------------
section("Dispatch robustness")
check("unknown tool -> error dict",
      tools.dispatch("nope", {}).get("error") is not None)
check("missing required arg -> error dict",
      tools.dispatch("estimate_price", {}).get("error") is not None)
check("missing id -> error dict",
      tools.dispatch("get_property_details", {"property_id": 10**9}).get("error") is not None)

# ---------------------------------------------------------------------------
# 4. Chat loop with a MOCK model (no API calls)
# ---------------------------------------------------------------------------
section("Chat loop (mock model)")

def _fake_content():
    return pytypes.SimpleNamespace(role="model", parts=[])

_real_generate = llm.generate

# Scenario A: model calls one tool, then answers.
_script = [
    {"type": "tool_calls", "calls": [{"name": "find_best_deals", "args": {"limit": 2}}],
     "content": _fake_content()},
    {"type": "text", "text": "Here are two strong deals.", "content": _fake_content()},
]
_step = {"i": 0}
def _scripted(contents, system_instruction=None):
    r = _script[_step["i"]]
    _step["i"] += 1
    return r
llm.generate = _scripted
out = chat.ask("best deals?")
check("loop returns the model's final answer", out["answer"] == "Here are two strong deals.")
check("loop actually ran the tool", len(out["trace"]) == 1 and out["trace"][0]["tool"] == "find_best_deals")
check("tool result is real data", out["trace"][0]["result"].get("count") is not None)

# Scenario B: model loops forever -> iteration cap.
def _always_tool(contents, system_instruction=None):
    return {"type": "tool_calls", "calls": [{"name": "get_market_stats", "args": {}}],
            "content": _fake_content()}
llm.generate = _always_tool
out2 = chat.ask("loop")
check("iteration cap stops runaway loop", len(out2["trace"]) == chat.MAX_TOOL_TURNS)

llm.generate = _real_generate  # restore

# ---------------------------------------------------------------------------
print(f"\n{'-' * 42}")
print(f"  {_passed} passed, {_failed} failed   (no API calls used)")
print(f"{'-' * 42}")
print("\nLive end-to-end check (uses ~1 API call):")
print('  python -m backend.chat "what is the market overview?"')

sys.exit(1 if _failed else 0)
