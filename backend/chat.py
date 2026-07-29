"""
backend/chat.py

The tool-calling loop — the heart of the AI layer.

A user asks in plain language. The model (via llm.py) decides whether to call one
of our tools. If it does, we run the REAL function (via tools.dispatch), feed the
result back, and let the model either call another tool or write the final answer.

    question -> [tool call -> real backend -> result] (repeat) -> phrased answer

Run it from the terminal:
    python -m backend.chat "what are the best deals under 150k?"
    python -m backend.chat            # interactive mode
"""

from __future__ import annotations

import logging

from backend import llm, tools

logger = logging.getLogger(__name__)

# Cap tool rounds so a confused model can't loop forever and burn quota.
MAX_TOOL_TURNS = 5

SYSTEM_PROMPT = (
    "You are the assistant for Tirana Deal Finder, which helps people find "
    "well-priced apartments in Tirana. Answer using the provided tools — they "
    "query a real listings database and a price model. Never invent listings, "
    "prices, or statistics; if you need data, call a tool. "
    "Deal grades: 'great' = priced well below the model's estimate, "
    "'good' = somewhat below, 'bad' = at or above the estimate. "
    "When you mention a specific listing, link it as a Markdown link to its page, "
    "for example [listing 935](/listing/935), so the user can click through. "
    "You may use light Markdown (bold, short bullet lists) but keep answers concise "
    "and in euros. If a tool returns an error or no results, say so "
    "plainly and suggest a sensible next step."
)


def ask(message: str, history: list | None = None, verbose: bool = False) -> dict:
    """Answer one user message, running tools as needed.

    Returns {"answer": str, "history": list, "trace": list}. Pass the returned
    `history` back in on the next call to keep a multi-turn conversation.
    `trace` records every tool call + result (useful for the UI and for teaching).
    """
    contents = list(history) if history else []
    contents.append(llm.user_message(message))
    trace: list[dict] = []

    for _ in range(MAX_TOOL_TURNS):
        result = llm.generate(contents, system_instruction=SYSTEM_PROMPT)

        if result["type"] == "tool_calls":
            # 1. Record the model's "I want to call X" turn.
            if result.get("content") is not None:
                contents.append(result["content"])
            # 2. Run each requested tool for real and feed results back.
            for call in result["calls"]:
                if verbose:
                    print(f"  \u2192 calling {call['name']}({call['args']})")
                output = tools.dispatch(call["name"], call["args"])
                trace.append({"tool": call["name"], "args": call["args"], "result": output})
                contents.append(llm.tool_result_message(call["name"], output))
            continue  # let the model see the results and decide what's next

        # A plain text answer — we're done.
        if result.get("content") is not None:
            contents.append(result["content"])
        return {"answer": result["text"], "history": contents, "trace": trace}

    # Ran out of tool rounds.
    return {
        "answer": "I couldn't finish that in a reasonable number of steps. "
                  "Try rephrasing or asking something more specific.",
        "history": contents,
        "trace": trace,
    }


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    if len(sys.argv) > 1:
        # One-shot mode: python -m backend.chat "your question"
        question = " ".join(sys.argv[1:])
        print(f"you > {question}")
        result = ask(question, verbose=True)
        print(f"\nassistant > {result['answer']}")
    else:
        # Interactive mode.
        print("Tirana Deal Finder assistant — ask about listings, prices, or deals.")
        print("Type 'quit' to exit.\n")
        history = None
        while True:
            try:
                question = input("you > ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if question.lower() in ("quit", "exit", "q", ""):
                break
            result = ask(question, history=history, verbose=True)
            history = result["history"]
            print(f"\nassistant > {result['answer']}\n")
