"""
backend/stats.py

Market statistics for the analytics page.

Two public functions:
    get_market_stats()  -> headline numbers + chart-ready breakdowns
    get_map_points()    -> per-listing coordinates + price band for the map

Both read the enriched listings from app.data (same predictions and deal grades
as the rest of the site). get_market_stats() is also the function the Week 3 AI
assistant will expose as a tool — so it lives here, reusable, not inside a route.
"""

from __future__ import annotations

import math

import pandas as pd

from app import data

# Price bands (EUR) used to colour the map and group listings.
# green -> amber -> orange -> red as price climbs.
PRICE_BANDS = [
    ("under_80k", 0, 80_000),
    ("80k_130k", 80_000, 130_000),
    ("130k_200k", 130_000, 200_000),
    ("over_200k", 200_000, float("inf")),
]


def _price_band(price: float) -> str:
    for name, low, high in PRICE_BANDS:
        if low <= price < high:
            return name
    return "over_200k"


def get_market_stats() -> dict:
    """Summary numbers and chart-ready breakdowns for the analytics page."""
    df = data._load()

    price = df["price_in_euro"].dropna()
    ppsqm = (df["price_in_euro"] / df["square_meters"]).replace(
        [math.inf, -math.inf], pd.NA).dropna()

    # Price distribution as histogram buckets (€50k-wide, capped for readability).
    capped = price.clip(upper=700_000)
    bins = list(range(0, 750_001, 50_000))
    hist = pd.cut(capped, bins=bins, right=False)
    distribution = [
        {"label": f"{int(interval.left/1000)}-{int(interval.right/1000)}k",
         "count": int(count)}
        for interval, count in hist.value_counts().sort_index().items()
    ]

    # Median price by bedroom count (1-4; rarer sizes grouped into "5+").
    beds = df.dropna(subset=["bedrooms"]).copy()
    beds["bed_group"] = beds["bedrooms"].apply(lambda b: "5+" if b >= 5 else str(int(b)))
    by_bedrooms = [
        {"bedrooms": grp,
         "median_price": int(sub["price_in_euro"].median()),
         "count": int(len(sub))}
        for grp, sub in beds.groupby("bed_group", sort=True)
    ]

    # Deal-grade split (the hero feature, summarised).
    grade_counts = df["deal_grade"].value_counts()
    by_grade = {g: int(grade_counts.get(g, 0)) for g in ["great", "good", "bad", "unknown"]}

    return {
        "total": int(len(df)),
        "median_price": int(price.median()),
        "median_ppsqm": int(ppsqm.median()),
        "min_price": int(price.min()),
        "max_price": int(price.max()),
        "distribution": distribution,
        "by_bedrooms": by_bedrooms,
        "by_grade": by_grade,
    }


def get_map_points() -> list[dict]:
    """One point per listing with valid coordinates, for the cluster map."""
    df = data._load()
    pts = df.dropna(subset=["latitude", "longitude", "price_in_euro"])
    points = []
    for _, row in pts.iterrows():
        points.append({
            "id": int(row["listing_id"]),
            "lat": float(row["latitude"]),
            "lng": float(row["longitude"]),
            "price": int(row["price_in_euro"]),
            "band": _price_band(float(row["price_in_euro"])),
            "grade": row["deal_grade"],
            "sqm": int(row["square_meters"]) if pd.notna(row["square_meters"]) else None,
        })
    return points
