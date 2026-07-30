"""
backend/tools.py

Tools available to the Tirana Deal Finder AI assistant.

Each tool is a thin wrapper around the real data-access, pricing, and market
functions already used by the web app. TOOL_SCHEMAS describes the tools to the
LLM; TOOLS maps tool names to Python functions; dispatch() executes them safely.
"""

from __future__ import annotations

from statistics import median

from backend import model, stats
from app import data


# Cache the trained model so estimate_price does not reload it every call.
_model_cache = None


def _get_model():
    global _model_cache
    if _model_cache is None:
        _model_cache = model.load_model()
    return _model_cache


def _int_or_none(value):
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _float_or_none(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _safe_limit(value, default=10, maximum=25):
    """Return a positive, bounded result limit."""
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = default
    return max(1, min(value, maximum))


def _price_per_sqm(listing: dict):
    price = _float_or_none(listing.get("price_in_euro"))
    sqm = _float_or_none(listing.get("square_meters"))
    if price is None or sqm is None or sqm <= 0:
        return None
    return round(price / sqm)


def _compact(listing: dict) -> dict:
    """Return a concise, LLM-friendly representation of one listing."""
    return {
        "id": listing["listing_id"],
        "price": listing.get("price_in_euro"),
        "estimated_price": listing.get("predicted_price"),
        "deal": listing.get("deal_grade"),
        "gap_pct": listing.get("gap_pct"),
        "bedrooms": _int_or_none(listing.get("bedrooms")),
        "bathrooms": _int_or_none(listing.get("bathrooms")),
        "square_meters": _int_or_none(listing.get("square_meters")),
        "floor": _int_or_none(listing.get("floor")),
        "price_per_sqm": _price_per_sqm(listing),
        "address": listing.get("address"),
    }


# ---------------------------------------------------------------------------
# Core tools
# ---------------------------------------------------------------------------

def search_properties(
    min_price=None,
    max_price=None,
    bedrooms=None,
    min_sqm=None,
    max_sqm=None,
    deal_grade=None,
    limit=10,
):
    """Search listings by price, bedrooms, size, and deal grade."""
    limit = _safe_limit(limit)
    results = data.search_listings(
        min_price=min_price,
        max_price=max_price,
        bedrooms=bedrooms,
        min_sqm=min_sqm,
        max_sqm=max_sqm,
        deal_grade=deal_grade,
        limit=limit,
    )
    return {
        "count": len(results),
        "results": [_compact(r) for r in results],
    }


def find_best_deals(limit=5, max_price=None, bedrooms=None):
    """Return great deals ranked by how far they are below the estimate."""
    limit = _safe_limit(limit, default=5)
    results = data.search_listings(
        deal_grade="great",
        max_price=max_price,
        bedrooms=bedrooms,
    )
    results = [r for r in results if r.get("gap_pct") is not None]
    results.sort(key=lambda r: r["gap_pct"], reverse=True)
    selected = results[:limit]
    return {
        "count": len(selected),
        "results": [_compact(r) for r in selected],
    }


def get_property_details(property_id):
    """Return detailed information for one listing."""
    listing = data.get_listing(property_id)
    if listing is None:
        return {"error": f"No listing with id {property_id}"}

    detail = _compact(listing)
    detail.update({
        "furnishing": listing.get("furnishing_status"),
        "has_elevator": bool(listing.get("has_elevator")),
        "has_terrace": bool(listing.get("has_terrace")),
        "has_garage": bool(listing.get("has_garage")),
        "has_parking_space": bool(listing.get("has_parking_space")),
        "description": (listing.get("description") or "")[:600],
    })
    return detail


def estimate_price(
    square_meters,
    bedrooms=None,
    bathrooms=None,
    floor=None,
    has_elevator=None,
    furnishing_status=None,
):
    """Estimate a fair price for a hypothetical apartment."""
    listing = {
        "square_meters": square_meters,
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "floor": floor,
        "has_elevator": has_elevator,
        "furnishing_status": furnishing_status,
    }

    price = model.predict_price(_get_model(), listing)
    return {
        "estimated_price": round(price),
        "inputs": listing,
    }


def get_market_stats():
    """Return the overall Tirana market summary."""
    return stats.get_market_stats()


def compare_property_to_market(property_id):
    """Compare one listing with overall Tirana market medians."""
    listing = data.get_listing(property_id)
    if listing is None:
        return {"error": f"No listing with id {property_id}"}

    market = stats.get_market_stats()
    price = _float_or_none(listing.get("price_in_euro"))
    sqm = _float_or_none(listing.get("square_meters"))
    market_price = _float_or_none(market.get("median_price"))
    market_ppsqm = _float_or_none(market.get("median_ppsqm"))
    ppsqm = price / sqm if price and sqm and sqm > 0 else None

    return {
        "id": listing["listing_id"],
        "price": round(price) if price is not None else None,
        "market_median_price": round(market_price) if market_price is not None else None,
        "price_vs_median_pct": (
            round((price - market_price) / market_price * 100, 1)
            if price is not None and market_price
            else None
        ),
        "price_per_sqm": round(ppsqm) if ppsqm is not None else None,
        "market_median_per_sqm": (
            round(market_ppsqm) if market_ppsqm is not None else None
        ),
        "price_per_sqm_vs_market_pct": (
            round((ppsqm - market_ppsqm) / market_ppsqm * 100, 1)
            if ppsqm is not None and market_ppsqm
            else None
        ),
        "deal": listing.get("deal_grade"),
        "gap_pct": listing.get("gap_pct"),
    }


# ---------------------------------------------------------------------------
# Added tools
# ---------------------------------------------------------------------------

def search_by_location(
    location,
    max_price=None,
    bedrooms=None,
    deal_grade=None,
    limit=10,
):
    """Search listings whose address contains a neighbourhood or street name."""
    location = str(location or "").strip()
    if not location:
        return {"error": "location must not be empty"}

    limit = _safe_limit(limit)
    query = location.casefold()
    matches = []

    for listing in data.get_all_listings():
        address = str(listing.get("address") or "")
        if query not in address.casefold():
            continue

        price = _float_or_none(listing.get("price_in_euro"))
        listing_bedrooms = _int_or_none(listing.get("bedrooms"))

        if max_price is not None and (price is None or price > float(max_price)):
            continue
        if bedrooms is not None and listing_bedrooms != int(bedrooms):
            continue
        if deal_grade and listing.get("deal_grade") != deal_grade:
            continue

        matches.append(listing)

    # Put the strongest discounts first.
    matches.sort(
        key=lambda r: (
            r.get("gap_pct") is None,
            -(r.get("gap_pct") or 0),
            r.get("price_in_euro") or float("inf"),
        )
    )

    selected = matches[:limit]
    return {
        "location": location,
        "count": len(selected),
        "total_matches": len(matches),
        "results": [_compact(r) for r in selected],
    }


def find_cheapest_per_sqm(
    limit=5,
    max_price=None,
    bedrooms=None,
    deal_grade=None,
):
    """Find listings with the lowest asking price per square metre."""
    limit = _safe_limit(limit, default=5)
    candidates = data.search_listings(
        max_price=max_price,
        bedrooms=bedrooms,
        deal_grade=deal_grade,
    )

    candidates = [
        listing
        for listing in candidates
        if _price_per_sqm(listing) is not None
    ]
    candidates.sort(key=_price_per_sqm)

    selected = candidates[:limit]
    return {
        "count": len(selected),
        "results": [_compact(r) for r in selected],
    }


def find_similar_properties(property_id, limit=5):
    """Find listings similar in size, bedrooms, type, and asking price."""
    source = data.get_listing(property_id)
    if source is None:
        return {"error": f"No listing with id {property_id}"}

    limit = _safe_limit(limit, default=5)
    source_id = int(source["listing_id"])
    source_sqm = _float_or_none(source.get("square_meters"))
    source_price = _float_or_none(source.get("price_in_euro"))
    source_bedrooms = _int_or_none(source.get("bedrooms"))
    source_type = source.get("property_type")

    ranked = []

    for listing in data.get_all_listings():
        if int(listing["listing_id"]) == source_id:
            continue

        if (
            source_type
            and listing.get("property_type")
            and listing.get("property_type") != source_type
        ):
            continue

        sqm = _float_or_none(listing.get("square_meters"))
        price = _float_or_none(listing.get("price_in_euro"))
        bedrooms = _int_or_none(listing.get("bedrooms"))

        size_difference = (
            abs(sqm - source_sqm) / source_sqm
            if sqm is not None and source_sqm
            else 1.0
        )
        price_difference = (
            abs(price - source_price) / source_price
            if price is not None and source_price
            else 1.0
        )
        bedroom_difference = (
            abs(bedrooms - source_bedrooms)
            if bedrooms is not None and source_bedrooms is not None
            else 2
        )

        similarity_score = (
            size_difference * 0.55
            + price_difference * 0.25
            + bedroom_difference * 0.20
        )
        ranked.append((similarity_score, listing))

    ranked.sort(key=lambda item: item[0])
    selected = ranked[:limit]

    return {
        "source": _compact(source),
        "count": len(selected),
        "results": [
            {
                **_compact(listing),
                "similarity_score": round(score, 3),
            }
            for score, listing in selected
        ],
    }


def compare_properties(first_property_id, second_property_id):
    """Compare two listings side by side."""
    first = data.get_listing(first_property_id)
    second = data.get_listing(second_property_id)

    missing = []
    if first is None:
        missing.append(first_property_id)
    if second is None:
        missing.append(second_property_id)
    if missing:
        return {"error": f"Listing id(s) not found: {missing}"}

    first_price = _float_or_none(first.get("price_in_euro"))
    second_price = _float_or_none(second.get("price_in_euro"))
    first_sqm = _float_or_none(first.get("square_meters"))
    second_sqm = _float_or_none(second.get("square_meters"))

    return {
        "first": _compact(first),
        "second": _compact(second),
        "differences": {
            "price": (
                round(first_price - second_price)
                if first_price is not None and second_price is not None
                else None
            ),
            "square_meters": (
                round(first_sqm - second_sqm, 1)
                if first_sqm is not None and second_sqm is not None
                else None
            ),
            "price_per_sqm": (
                _price_per_sqm(first) - _price_per_sqm(second)
                if _price_per_sqm(first) is not None
                and _price_per_sqm(second) is not None
                else None
            ),
        },
    }


def get_location_summary(location):
    """Summarise prices and deal grades for addresses matching a location."""
    location = str(location or "").strip()
    if not location:
        return {"error": "location must not be empty"}

    query = location.casefold()
    matches = [
        listing
        for listing in data.get_all_listings()
        if query in str(listing.get("address") or "").casefold()
    ]

    if not matches:
        return {
            "location": location,
            "count": 0,
            "error": "No listings matched that location.",
        }

    prices = [
        float(r["price_in_euro"])
        for r in matches
        if _float_or_none(r.get("price_in_euro")) is not None
    ]
    prices_per_sqm = [
        _price_per_sqm(r)
        for r in matches
        if _price_per_sqm(r) is not None
    ]

    grades = {"great": 0, "good": 0, "bad": 0, "unknown": 0}
    for listing in matches:
        grade = listing.get("deal_grade") or "unknown"
        grades[grade if grade in grades else "unknown"] += 1

    return {
        "location": location,
        "count": len(matches),
        "median_price": round(median(prices)) if prices else None,
        "median_price_per_sqm": (
            round(median(prices_per_sqm)) if prices_per_sqm else None
        ),
        "deal_breakdown": grades,
    }


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

TOOLS = {
    "search_properties": search_properties,
    "find_best_deals": find_best_deals,
    "get_property_details": get_property_details,
    "estimate_price": estimate_price,
    "get_market_stats": get_market_stats,
    "compare_property_to_market": compare_property_to_market,
    "search_by_location": search_by_location,
    "find_cheapest_per_sqm": find_cheapest_per_sqm,
    "find_similar_properties": find_similar_properties,
    "compare_properties": compare_properties,
    "get_location_summary": get_location_summary,
}


TOOL_SCHEMAS = [
    {
        "name": "search_properties",
        "description": (
            "Search Tirana property listings by asking-price range, exact bedroom "
            "count, size range, and deal grade."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "min_price": {
                    "type": "integer",
                    "description": "Minimum asking price in EUR.",
                },
                "max_price": {
                    "type": "integer",
                    "description": "Maximum asking price in EUR.",
                },
                "bedrooms": {
                    "type": "integer",
                    "description": "Exact bedroom count.",
                },
                "min_sqm": {
                    "type": "integer",
                    "description": "Minimum size in square metres.",
                },
                "max_sqm": {
                    "type": "integer",
                    "description": "Maximum size in square metres.",
                },
                "deal_grade": {
                    "type": "string",
                    "enum": ["great", "good", "bad"],
                    "description": "great, good, or market-price/bad.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results, default 10 and maximum 25.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "find_best_deals",
        "description": (
            "Return great deals ranked by how far their asking price is below "
            "the model estimate."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of results, default 5.",
                },
                "max_price": {
                    "type": "integer",
                    "description": "Optional maximum asking price in EUR.",
                },
                "bedrooms": {
                    "type": "integer",
                    "description": "Optional exact bedroom count.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_property_details",
        "description": (
            "Get detailed information about one real listing, including price, "
            "model estimate, features, amenities, and description."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "property_id": {
                    "type": "integer",
                    "description": "Listing id.",
                },
            },
            "required": ["property_id"],
        },
    },
    {
        "name": "estimate_price",
        "description": (
            "Estimate a fair price for a hypothetical apartment. Square metres "
            "is required; the other characteristics are optional."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "square_meters": {
                    "type": "number",
                    "description": "Apartment size in square metres.",
                },
                "bedrooms": {
                    "type": "integer",
                    "description": "Bedroom count.",
                },
                "bathrooms": {
                    "type": "integer",
                    "description": "Bathroom count.",
                },
                "floor": {
                    "type": "integer",
                    "description": "Floor number.",
                },
                "has_elevator": {
                    "type": "boolean",
                    "description": "Whether the building has an elevator.",
                },
                "furnishing_status": {
                    "type": "string",
                    "description": (
                        "fully_furnished, partially_furnished, or unfurnished."
                    ),
                },
            },
            "required": ["square_meters"],
        },
    },
    {
        "name": "get_market_stats",
        "description": (
            "Get the overall Tirana market summary, including medians, price "
            "distribution, and deal-grade breakdown."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "compare_property_to_market",
        "description": (
            "Compare one listing's asking price and price per square metre with "
            "the overall Tirana market medians."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "property_id": {
                    "type": "integer",
                    "description": "Listing id.",
                },
            },
            "required": ["property_id"],
        },
    },
    {
        "name": "search_by_location",
        "description": (
            "Search listings by a neighbourhood, road, complex, or other text "
            "contained in the address. Optional price, bedroom, and deal filters."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "Location text such as Blloku, Astir, or Don Bosko.",
                },
                "max_price": {
                    "type": "integer",
                    "description": "Optional maximum asking price in EUR.",
                },
                "bedrooms": {
                    "type": "integer",
                    "description": "Optional exact bedroom count.",
                },
                "deal_grade": {
                    "type": "string",
                    "enum": ["great", "good", "bad"],
                    "description": "Optional deal grade.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results, default 10.",
                },
            },
            "required": ["location"],
        },
    },
    {
        "name": "find_cheapest_per_sqm",
        "description": (
            "Find listings with the lowest asking price per square metre. Use "
            "this for questions about the cheapest value per m²."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of results, default 5.",
                },
                "max_price": {
                    "type": "integer",
                    "description": "Optional maximum total asking price in EUR.",
                },
                "bedrooms": {
                    "type": "integer",
                    "description": "Optional exact bedroom count.",
                },
                "deal_grade": {
                    "type": "string",
                    "enum": ["great", "good", "bad"],
                    "description": "Optional deal grade.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "find_similar_properties",
        "description": (
            "Find real listings similar to a chosen listing in size, bedrooms, "
            "property type, and asking price."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "property_id": {
                    "type": "integer",
                    "description": "Source listing id.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of similar listings, default 5.",
                },
            },
            "required": ["property_id"],
        },
    },
    {
        "name": "compare_properties",
        "description": (
            "Compare two real listings side by side, including total price, "
            "size, price per square metre, estimate, and deal grade."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "first_property_id": {
                    "type": "integer",
                    "description": "First listing id.",
                },
                "second_property_id": {
                    "type": "integer",
                    "description": "Second listing id.",
                },
            },
            "required": ["first_property_id", "second_property_id"],
        },
    },
    {
        "name": "get_location_summary",
        "description": (
            "Summarise listings whose addresses contain a location name, "
            "including median price, median price per m², and deal breakdown."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "Neighbourhood, street, or complex name.",
                },
            },
            "required": ["location"],
        },
    },
]


def dispatch(name: str, arguments: dict | None = None):
    """Run a registered tool safely and return errors as data."""
    fn = TOOLS.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}

    try:
        return fn(**(arguments or {}))
    except TypeError as exc:
        return {"error": f"Bad arguments for {name}: {exc}"}
    except Exception as exc:
        return {"error": f"{name} failed: {exc}"}


if __name__ == "__main__":
    import json

    print("Available tools:", list(TOOLS.keys()))
    print("\nfind_best_deals(limit=3):")
    print(
        json.dumps(
            dispatch("find_best_deals", {"limit": 3}),
            indent=2,
        )[:1000]
    )