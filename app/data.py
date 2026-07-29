"""
app/data.py

Data-access layer for the web app.

Loads the cleaned listings and the trained model ONCE, attaches a predicted
price + deal grade to every listing, and exposes the simple functions the Flask
routes call:

    get_all_listings(limit=None)      -> list of enriched listing dicts
    get_listing(listing_id)           -> one enriched listing dict, or None
    search_listings(...)              -> filtered list of enriched listing dicts
    get_filter_bounds()               -> sensible min/max values for the filter UI

It reuses backend.model (predict + score_deal) — the SAME functions built in
Week 1 — so the prices and badges on the website match the notebook exactly.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path

import pandas as pd

from backend import preprocessing, model

logger = logging.getLogger(__name__)

DISPLAY_PATH = preprocessing.CLEAN_PATH  # data/listings_clean.parquet

# Module-level cache so we load the data + model once, not on every request.
_listings_df: pd.DataFrame | None = None


# ---------------------------------------------------------------------------
# Loading + enrichment
# ---------------------------------------------------------------------------
def _enrich(df: pd.DataFrame) -> pd.DataFrame:
    """Add predicted_price, gap_pct, and deal_grade to every listing."""
    df = df.copy()

    try:
        trained = model.load_model()
        df["predicted_price"] = trained.predict(model.build_features(df)).round(0)
    except Exception as exc:  # model file missing or unreadable
        logger.warning(
            "Could not load the model (%s). Run `python tests/smoke_test.py` to "
            "create models/model.joblib. Listings will show without predictions.",
            exc,
        )
        df["predicted_price"] = None

    grades, gaps = [], []
    for predicted, listed in zip(df["predicted_price"], df["price_in_euro"]):
        if predicted is None or (isinstance(predicted, float) and math.isnan(predicted)):
            grades.append("unknown")
            gaps.append(None)
        else:
            result = model.score_deal(float(predicted), float(listed))
            grades.append(result["grade"])
            gaps.append(result["gap_pct"])
    df["deal_grade"] = grades
    df["gap_pct"] = gaps
    return df


def _load() -> pd.DataFrame:
    """Load + enrich the listings once, then reuse the cached result."""
    global _listings_df
    if _listings_df is None:
        if not Path(DISPLAY_PATH).exists():
            logger.info("Clean dataset not found; running preprocessing first...")
            preprocessing.run()
        raw = pd.read_parquet(DISPLAY_PATH)
        _listings_df = _enrich(raw)
        logger.info("Loaded %d listings into the web app", len(_listings_df))
    return _listings_df


def _clean_record(record: dict) -> dict:
    """Convert pandas NaN to None so templates render cleanly ('N/A')."""
    cleaned = {}
    for key, value in record.items():
        if isinstance(value, float) and math.isnan(value):
            cleaned[key] = None
        else:
            cleaned[key] = value
    return cleaned


# ---------------------------------------------------------------------------
# Public API used by the routes
# ---------------------------------------------------------------------------
def get_all_listings(limit: int | None = None) -> list[dict]:
    df = _load()
    records = [_clean_record(r) for r in df.to_dict(orient="records")]
    return records[:limit] if limit else records


def get_listing(listing_id) -> dict | None:
    df = _load()
    try:
        match = df[df["listing_id"] == int(listing_id)]
    except (TypeError, ValueError):
        return None
    if match.empty:
        return None
    return _clean_record(match.iloc[0].to_dict())


def search_listings(min_price=None, max_price=None, bedrooms=None,
                    min_sqm=None, max_sqm=None, deal_grade=None,
                    limit=None) -> list[dict]:
    """Filter listings. Any argument left as None is ignored."""
    df = _load()
    mask = pd.Series(True, index=df.index)

    if min_price is not None:
        mask &= df["price_in_euro"] >= min_price
    if max_price is not None:
        mask &= df["price_in_euro"] <= max_price
    if bedrooms is not None:
        mask &= df["bedrooms"] == bedrooms
    if min_sqm is not None:
        mask &= df["square_meters"] >= min_sqm
    if max_sqm is not None:
        mask &= df["square_meters"] <= max_sqm
    if deal_grade:
        mask &= df["deal_grade"] == deal_grade

    out = df[mask]
    records = [_clean_record(r) for r in out.to_dict(orient="records")]
    return records[:limit] if limit else records


def get_hero_stats() -> dict:
    """Headline numbers for the hero strip, computed from all listings."""
    df = _load()
    ppsqm = (df["price_in_euro"] / df["square_meters"]).replace(
        [float("inf"), float("-inf")], pd.NA).dropna()
    grades = df["deal_grade"].value_counts()
    return {
        "total": len(df),
        "median_ppsqm": int(ppsqm.median()),
        "great_deals": int(grades.get("great", 0)),
        "good_deals": int(grades.get("good", 0)),
    }


def get_filter_bounds() -> dict:
    """Sensible ranges for filter controls.

    Uses the 1st-99th percentile for price/size so a few extreme listings don't
    stretch the sliders into uselessness (display data still contains them).
    """
    df = _load()
    return {
        "price_min": int(df["price_in_euro"].quantile(0.01)),
        "price_max": int(df["price_in_euro"].quantile(0.99)),
        "sqm_min": int(df["square_meters"].quantile(0.01)),
        "sqm_max": int(df["square_meters"].quantile(0.99)),
        "bedroom_options": sorted(int(b) for b in df["bedrooms"].dropna().unique()),
        "total": len(df),
    }
