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

# Cap tool rounds so a confused model cannot loop forever and burn quota.
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


def ask(
    message: str,
    history: list | None = None,
    verbose: bool = False,
) -> dict:
    """Answer one user message, running tools as needed.

    Returns:
        {
            "answer": str,
            "history": list,
            "trace": list,
        }

    Pass the returned history back on the next call to keep a multi-turn
    conversation.

    trace records every tool call and result, which is useful for the UI,
    debugging, and teaching.
    """
    contents = list(history) if history else []
    contents.append(llm.user_message(message))

    trace: list[dict] = []

    for turn_number in range(1, MAX_TOOL_TURNS + 1):
        result = llm.generate(
            contents,
            system_instruction=SYSTEM_PROMPT,
        )

        if result["type"] == "tool_calls":
            # Record Gemini's tool-call turn in the conversation history.
            if result.get("content") is not None:
                contents.append(result["content"])

            # Run every requested tool and return each result to Gemini.
            for call in result["calls"]:
                tool_name = call["name"]
                tool_args = call.get("args") or {}
                call_id = call.get("id")

                if verbose:
                    print(
                        f"  → calling {tool_name}({tool_args})"
                    )

                output = tools.dispatch(
                    tool_name,
                    tool_args,
                )

                trace.append({
                    "turn": turn_number,
                    "tool": tool_name,
                    "args": tool_args,
                    "call_id": call_id,
                    "result": output,
                })

                # The improved llm.py accepts call_id and passes it back to
                # Gemini. This is important for newer Gemini models that attach
                # an id to every function call.
                contents.append(
                    llm.tool_result_message(
                        tool_name,
                        output,
                        call_id=call_id,
                    )
                )

            # Let Gemini read the tool results and decide whether it needs
            # another tool or can now produce the final answer.
            continue

        # A normal text response means the assistant is finished.
        if result.get("content") is not None:
            contents.append(result["content"])

        return {
            "answer": result["text"],
            "history": contents,
            "trace": trace,
            "model": result.get("model"),
            "usage": result.get("usage", {}),
        }

    logger.warning(
        "Chat exceeded MAX_TOOL_TURNS=%d for message %r",
        MAX_TOOL_TURNS,
        message,
    )

    return {
        "answer": (
            "I couldn't finish that in a reasonable number of steps. "
            "Try rephrasing or asking something more specific."
        ),
        "history": contents,
        "trace": trace,
        "model": None,
        "usage": {},
    }


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s: %(message)s",
    )

    if len(sys.argv) > 1:
        # One-shot mode:
        # python -m backend.chat "your question"
        question = " ".join(sys.argv[1:])
        print(f"you > {question}")

        result = ask(
            question,
            verbose=True,
        )

        print(f"\nassistant > {result['answer']}")

    else:
        # Interactive terminal mode.
        print(
            "Tirana Deal Finder assistant — "
            "ask about listings, prices, or deals."
        )
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

            result = ask(
                question,
                history=history,
                verbose=True,
            )

            history = result["history"]
            print(f"\nassistant > {result['answer']}\n")