"""
backend/tools.py

The tools an LLM can call. Each tool is a thin wrapper around functions we
already built — search, the price model, the deal scorer, the market stats —
so the assistant reuses the exact logic that powers the website. Nothing about
pricing or searching is reinvented here.

This file is provider-neutral and needs no API key:
    TOOL_SCHEMAS  - JSON-Schema description of each tool (what the LLM reads)
    TOOLS         - name -> python function (what actually runs)
    dispatch()    - run a tool by name with a dict of arguments

backend/llm.py converts TOOL_SCHEMAS into the specific format Gemini or
Anthropic expects; backend/chat.py uses dispatch() to run the chosen tool.
"""

from __future__ import annotations

from backend import model, stats
from app import data

# Cache the trained model so estimate_price doesn't reload it every call.
_model_cache = None


def _get_model():
    global _model_cache
    if _model_cache is None:
        _model_cache = model.load_model()
    return _model_cache


def _int_or_none(value):
    return int(value) if value is not None else None


def _compact(listing: dict) -> dict:
    """A small, LLM-friendly view of a listing (not the whole record)."""
    return {
        "id": listing["listing_id"],
        "price": listing.get("price_in_euro"),
        "estimated_price": listing.get("predicted_price"),
        "deal": listing.get("deal_grade"),
        "gap_pct": listing.get("gap_pct"),
        "bedrooms": _int_or_none(listing.get("bedrooms")),
        "square_meters": _int_or_none(listing.get("square_meters")),
        "address": listing.get("address"),
    }


# ---------------------------------------------------------------------------
# The tools
# ---------------------------------------------------------------------------
def search_properties(min_price=None, max_price=None, bedrooms=None,
                      min_sqm=None, max_sqm=None, deal_grade=None, limit=10):
    """Search listings by price, bedrooms, size, and deal grade."""
    results = data.search_listings(
        min_price=min_price, max_price=max_price, bedrooms=bedrooms,
        min_sqm=min_sqm, max_sqm=max_sqm, deal_grade=deal_grade, limit=limit,
    )
    return {"count": len(results), "results": [_compact(r) for r in results]}


def find_best_deals(limit=5, max_price=None, bedrooms=None):
    """The biggest bargains: 'great' listings ranked by how far below estimate."""
    results = data.search_listings(
        deal_grade="great", max_price=max_price, bedrooms=bedrooms,
    )
    results = [r for r in results if r.get("gap_pct") is not None]
    results.sort(key=lambda r: r["gap_pct"], reverse=True)
    return {"count": len(results), "results": [_compact(r) for r in results[:limit]]}


def get_property_details(property_id):
    """Full detail for one listing, including its deal verdict."""
    listing = data.get_listing(property_id)
    if listing is None:
        return {"error": f"No listing with id {property_id}"}
    detail = _compact(listing)
    detail.update({
        "bathrooms": _int_or_none(listing.get("bathrooms")),
        "floor": _int_or_none(listing.get("floor")),
        "furnishing": listing.get("furnishing_status"),
        "has_elevator": bool(listing.get("has_elevator")),
        "description": (listing.get("description") or "")[:400],
    })
    return detail


def estimate_price(square_meters, bedrooms=None, bathrooms=None, floor=None,
                   has_elevator=None, furnishing_status=None):
    """Estimate a fair price for a hypothetical flat described by its features."""
    listing = {
        "square_meters": square_meters,
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "floor": floor,
        "has_elevator": has_elevator,
        "furnishing_status": furnishing_status,
    }
    price = model.predict_price(_get_model(), listing)
    return {"estimated_price": round(price), "inputs": listing}


def get_market_stats():
    """Overall market summary: medians, price distribution, deal breakdown."""
    return stats.get_market_stats()


def compare_property_to_market(property_id):
    """Compare one listing's price and price/m² against the market medians."""
    listing = data.get_listing(property_id)
    if listing is None:
        return {"error": f"No listing with id {property_id}"}
    market = stats.get_market_stats()
    price = listing.get("price_in_euro")
    sqm = listing.get("square_meters")
    ppsqm = round(price / sqm) if price and sqm else None
    return {
        "id": listing["listing_id"],
        "price": price,
        "market_median_price": market["median_price"],
        "price_vs_median_pct": round((price - market["median_price"])
                                     / market["median_price"] * 100, 1) if price else None,
        "price_per_sqm": ppsqm,
        "market_median_per_sqm": market["median_ppsqm"],
        "deal": listing.get("deal_grade"),
    }


# ---------------------------------------------------------------------------
# Registry + schemas + dispatcher
# ---------------------------------------------------------------------------
TOOLS = {
    "search_properties": search_properties,
    "find_best_deals": find_best_deals,
    "get_property_details": get_property_details,
    "estimate_price": estimate_price,
    "get_market_stats": get_market_stats,
    "compare_property_to_market": compare_property_to_market,
}

TOOL_SCHEMAS = [
    {
        "name": "search_properties",
        "description": ("Search apartment listings in Tirana. Filter by price range, "
                        "exact bedroom count, size range, and deal grade. Returns matching "
                        "listings with asking price, the model's estimated price, and deal grade."),
        "parameters": {
            "type": "object",
            "properties": {
                "min_price": {"type": "integer", "description": "Minimum asking price in EUR."},
                "max_price": {"type": "integer", "description": "Maximum asking price in EUR."},
                "bedrooms": {"type": "integer", "description": "Exact number of bedrooms."},
                "min_sqm": {"type": "integer", "description": "Minimum size in square meters."},
                "max_sqm": {"type": "integer", "description": "Maximum size in square meters."},
                "deal_grade": {"type": "string", "enum": ["great", "good", "bad"],
                               "description": "Deal quality. 'great' = well below estimate; 'bad' = at/above market."},
                "limit": {"type": "integer", "description": "Max results (default 10)."},
            },
            "required": [],
        },
    },
    {
        "name": "find_best_deals",
        "description": ("Return the best bargains right now: listings graded 'great', "
                        "ranked by how far below the estimated price they are. "
                        "Use this when the user asks for the best deals or biggest discounts."),
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "How many deals to return (default 5)."},
                "max_price": {"type": "integer", "description": "Optional max asking price in EUR."},
                "bedrooms": {"type": "integer", "description": "Optional exact bedroom count."},
            },
            "required": [],
        },
    },
    {
        "name": "get_property_details",
        "description": "Full details for a single listing by its id, including the deal verdict and description.",
        "parameters": {
            "type": "object",
            "properties": {
                "property_id": {"type": "integer", "description": "The listing id."},
            },
            "required": ["property_id"],
        },
    },
    {
        "name": "estimate_price",
        "description": ("Estimate a fair price for a hypothetical apartment the user describes "
                        "(not necessarily a real listing). Requires at least the size."),
        "parameters": {
            "type": "object",
            "properties": {
                "square_meters": {"type": "number", "description": "Size in square meters (required)."},
                "bedrooms": {"type": "integer", "description": "Number of bedrooms."},
                "bathrooms": {"type": "integer", "description": "Number of bathrooms."},
                "floor": {"type": "integer", "description": "Floor number."},
                "has_elevator": {"type": "boolean", "description": "Whether the building has an elevator."},
                "furnishing_status": {"type": "string",
                                      "description": "e.g. fully_furnished, unfurnished, partially_furnished."},
            },
            "required": ["square_meters"],
        },
    },
    {
        "name": "get_market_stats",
        "description": ("Overall Tirana market summary: total listings, median price, median price "
                        "per square meter, price distribution, and the great/good/market deal breakdown."),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "compare_property_to_market",
        "description": "Compare one listing's price and price-per-m² against the market medians.",
        "parameters": {
            "type": "object",
            "properties": {
                "property_id": {"type": "integer", "description": "The listing id to compare."},
            },
            "required": ["property_id"],
        },
    },
]


def dispatch(name: str, arguments: dict | None = None):
    """Run a tool by name with a dict of arguments; never raises."""
    fn = TOOLS.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        return fn(**(arguments or {}))
    except TypeError as exc:
        return {"error": f"Bad arguments for {name}: {exc}"}
    except Exception as exc:  # keep the loop alive on any tool failure
        return {"error": f"{name} failed: {exc}"}


if __name__ == "__main__":
    # Quick offline poke — no API key needed.
    import json
    print("Available tools:", list(TOOLS.keys()))
    print("\nfind_best_deals(limit=3):")
    print(json.dumps(dispatch("find_best_deals", {"limit": 3}), indent=2)[:600])
