"""
app/app.py

Flask web app for the Tirana Deal Finder.

Routes:
    /                home page: hero, filters, and a grid of listing cards,
                     each showing a great / good / bad deal badge
    /listing/<id>    details page for a single listing

Everything is read through app/data.py, which loads the cleaned listings and the
trained model once at startup. Run it with:

    python -m app.app
"""

from __future__ import annotations

from uuid import uuid4

from flask import Flask, render_template, request, abort, jsonify

from app import data
from backend import stats, chat

app = Flask(__name__)

# In-memory chat history, keyed by conversation id.
# Fine for a teaching demo (single process; resets on restart).
_conversations: dict[str, list] = {}

PAGE_SIZE = 24  # listing cards shown per page


def _to_int(value):
    """Parse a query-string value into an int, or None if blank/invalid."""
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


@app.route("/")
def home():
    # All filters are optional; a blank field means "no filter".
    filters = {
        "min_price": _to_int(request.args.get("min_price")),
        "max_price": _to_int(request.args.get("max_price")),
        "bedrooms": _to_int(request.args.get("bedrooms")),
        "min_sqm": _to_int(request.args.get("min_sqm")),
        "max_sqm": _to_int(request.args.get("max_sqm")),
        "deal_grade": request.args.get("deal_grade") or None,
    }
    page = max(1, _to_int(request.args.get("page")) or 1)

    matches = data.search_listings(**filters)
    total = len(matches)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    start = (page - 1) * PAGE_SIZE
    page_listings = matches[start:start + PAGE_SIZE]

    return render_template(
        "index.html",
        listings=page_listings,
        total=total,
        page=page,
        total_pages=total_pages,
        filters=filters,
        bounds=data.get_filter_bounds(),
        stats=data.get_hero_stats(),
    )


@app.route("/analytics")
def analytics():
    return render_template(
        "analytics.html",
        stats=stats.get_market_stats(),
        points=stats.get_map_points(),
    )


@app.route("/chat", methods=["POST"])
def chat_endpoint():
    """Receive a message, run the tool-calling assistant, return its answer."""
    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip()
    if not message:
        return jsonify({"error": "Please type a message."}), 400

    conversation_id = payload.get("conversation_id") or uuid4().hex
    history = _conversations.get(conversation_id)

    try:
        result = chat.ask(message, history=history)
    except Exception as exc:  # keep the widget alive on any backend failure
        app.logger.exception("chat failed")
        return jsonify({
            "conversation_id": conversation_id,
            "answer": "Sorry, I ran into a problem answering that. Please try again.",
            "error": str(exc),
        }), 200

    _conversations[conversation_id] = result["history"]
    return jsonify({
        "conversation_id": conversation_id,
        "answer": result["answer"],
        "tools_used": [t["tool"] for t in result["trace"]],
    })


@app.route("/listing/<int:listing_id>")
def listing_detail(listing_id):
    listing = data.get_listing(listing_id)
    if listing is None:
        abort(404)
    return render_template("detail.html", listing=listing)


if __name__ == "__main__":
    # debug=True gives auto-reload + helpful error pages during development.
    app.run(debug=True, port=5000)
