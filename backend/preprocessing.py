"""
backend/preprocessing.py

Centralized preprocessing for the Tirana Deal Finder.
Implements the 7-step pipeline described in docs/concept/04-data-preprocessing.md.

It produces TWO views of the data:
  - display_df : all cleaned records (steps 1-4 + step 6). Used by the web app.
  - ml_df      : display_df minus outliers (step 5). Used to train/predict.

Run it directly to generate data/listings_clean.parquet:

    python -m backend.preprocessing

All cleaning logic lives here and nowhere else, so the SAME rules are used by
the web app, by model training, and by prediction.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd
pd.set_option("future.no_silent_downcasting", True)

# ---------------------------------------------------------------------------
# Constants  (edit these to change behaviour — keep thresholds in one place)
# ---------------------------------------------------------------------------

RAW_PATH = Path("data/tirana_house_prices.json")
CLEAN_PATH = Path("data/listings_clean.parquet")

# Step 5 — outlier bounds (Tirana residential market)
PRICE_MIN = 10_000
PRICE_MAX = 1_200_000
SQM_MIN = 10
SQM_MAX = 700
# Step 5b — price-per-m² sanity bounds (catches size/price ratio errors)
PPSQM_MIN = 300
PPSQM_MAX = 8_000

# Step 6 — source field name -> short, API-friendly name.
# Only the columns listed here survive into the final dataset.
RENAME_MAP = {
    "price_in_euro": "price_in_euro",
    "main_property_property_square": "square_meters",
    "main_property_property_composition_bedrooms": "bedrooms",
    "main_property_property_composition_bathrooms": "bathrooms",
    "main_property_floor": "floor",
    "main_property_furnishing_status": "furnishing_status",
    "main_property_has_elevator": "has_elevator",
    "main_property_has_terrace": "has_terrace",
    "main_property_has_carport": "has_carport",
    "main_property_has_garage": "has_garage",
    "main_property_has_garden": "has_garden",
    "main_property_has_parking_space": "has_parking_space",
    "main_property_location_city_zone_formatted_address": "address",
    "main_property_location_lat": "latitude",
    "main_property_location_lng": "longitude",
    "main_property_property_status": "property_status",
    "main_property_property_type": "property_type",
    "main_property_description_text_content_original_text": "description",
}

# Step 3 — numeric source fields where a negative value is a data-entry error.
# We take abs() of any negative (per the preprocessing doc).
NEGATIVE_FIX_FIELDS = [
    "main_property_property_composition_balconies",
    "main_property_property_composition_kitchens",
    "main_property_property_composition_living_rooms",
    "main_property_property_composition_bathrooms",
    "main_property_property_composition_bedrooms",
    "main_property_floor",
    "main_property_property_square",
]

# Step 4 — null handling groups, keyed by FINAL (renamed) column names.
BOOLEAN_FIELDS = [
    "has_elevator", "has_terrace", "has_carport",
    "has_garage", "has_garden", "has_parking_space",
]
CATEGORICAL_FIELDS = ["furnishing_status", "property_status", "property_type"]

# ML view rules.
ML_DROP_IF_NULL = ["price_in_euro", "square_meters"]   # essential -> drop row
ML_IMPUTE_MEDIAN = ["bedrooms", "bathrooms", "floor"]  # impute with median

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Step 1 — Load and parse
# ---------------------------------------------------------------------------
def load_raw(path: Path = RAW_PATH) -> pd.DataFrame:
    """Load the JSON array of listings into a DataFrame."""
    path = Path(path)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array in {path}, got {type(data).__name__}")
    df = pd.DataFrame(data)
    logger.info("Step 1: loaded %d raw listings from %s", len(df), path)
    return df


# ---------------------------------------------------------------------------
# Step 2 — Stable listing identifier (0-based row index)
# ---------------------------------------------------------------------------
def _add_listing_id(df: pd.DataFrame) -> pd.DataFrame:
    df = df.reset_index(drop=True)
    df.insert(0, "listing_id", df.index)
    logger.info("Step 2: added listing_id 0..%d", len(df) - 1)
    return df


# ---------------------------------------------------------------------------
# Step 3 — Fix negative values with abs()
# ---------------------------------------------------------------------------
def _fix_negatives(df: pd.DataFrame) -> pd.DataFrame:
    for col in NEGATIVE_FIX_FIELDS:
        if col not in df.columns:
            continue
        n_neg = (df[col] < 0).sum()
        if n_neg:
            df[col] = df[col].abs()
            logger.info("Step 3: %s had %d negative value(s) -> abs()", col, n_neg)
    return df


# ---------------------------------------------------------------------------
# Step 6 — Rename to API names and keep only mapped columns.
# (Run before Step 4 so null-handling can use the short names.)
# ---------------------------------------------------------------------------
def _rename_and_select(df: pd.DataFrame) -> pd.DataFrame:
    present = {src: dst for src, dst in RENAME_MAP.items() if src in df.columns}
    missing = [src for src in RENAME_MAP if src not in df.columns]
    if missing:
        logger.warning("Step 6: expected source columns missing: %s", missing)

    df = df.rename(columns=present)
    final_cols = ["listing_id"] + list(present.values())
    dropped = [c for c in df.columns if c not in final_cols]
    logger.info("Step 6: kept %d columns; dropped %d: %s",
                len(final_cols), len(dropped), dropped)
    return df[final_cols]


# ---------------------------------------------------------------------------
# Step 4 — Handle nulls for the DISPLAY view.
# Booleans -> False, categoricals -> "unknown".
# Numeric/text/location nulls are kept as-is (the UI shows N/A).
# ---------------------------------------------------------------------------
def _handle_nulls_display(df: pd.DataFrame) -> pd.DataFrame:
    for col in BOOLEAN_FIELDS:
        if col in df.columns:
            n = int(df[col].isna().sum())
            df[col] = df[col].fillna(False).infer_objects(copy=False).astype(bool)
            if n:
                logger.info("Step 4: %s filled %d null(s) -> False", col, n)

    for col in CATEGORICAL_FIELDS:
        if col in df.columns:
            n = int(df[col].isna().sum())
            df[col] = df[col].fillna("unknown")
            if n:
                logger.info("Step 4: %s filled %d null(s) -> 'unknown'", col, n)

    return df


# ---------------------------------------------------------------------------
# Build the DISPLAY dataset (steps 1-4 + 6)
# ---------------------------------------------------------------------------
def build_display_df(raw: pd.DataFrame) -> pd.DataFrame:
    df = _add_listing_id(raw)        # Step 2
    df = _fix_negatives(df)          # Step 3 (uses source column names)
    df = _rename_and_select(df)      # Step 6 (rename + drop unmapped columns)
    df = _handle_nulls_display(df)   # Step 4 (uses short names)
    logger.info("Display dataset ready: %d rows, %d columns", *df.shape)
    return df


# ---------------------------------------------------------------------------
# Build the ML dataset (display - outliers, with imputation)
# Steps 4 (ML branch) + 5
# ---------------------------------------------------------------------------
def build_ml_df(display_df: pd.DataFrame) -> pd.DataFrame:
    df = display_df.copy()

    # Drop rows missing the essentials (target + size).
    before = len(df)
    df = df.dropna(subset=[c for c in ML_DROP_IF_NULL if c in df.columns])
    logger.info("ML: dropped %d row(s) missing target/square_meters", before - len(df))

    # Impute remaining numeric nulls with the column median.
    for col in ML_IMPUTE_MEDIAN:
        if col in df.columns:
            n = int(df[col].isna().sum())
            if n:
                median = df[col].median()
                df[col] = df[col].fillna(median)
                logger.info("ML: imputed %d null(s) in %s with median %.2f", n, col, median)

    # Step 5 — remove outliers.
    before = len(df)
    df = df[(df["price_in_euro"] >= PRICE_MIN) & (df["price_in_euro"] <= PRICE_MAX)]
    df = df[(df["square_meters"] >= SQM_MIN) & (df["square_meters"] <= SQM_MAX)]
    logger.info("ML: removed %d outlier row(s) (price/size bounds)", before - len(df))

    # Step 5b — drop listings whose price-per-m² is implausible.
    before = len(df)
    ppsqm = df["price_in_euro"] / df["square_meters"]
    df = df[(ppsqm >= PPSQM_MIN) & (ppsqm <= PPSQM_MAX)]
    logger.info("ML: removed %d row(s) with implausible price/m²", before - len(df))

    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Step 7 — one call that returns both views.
# ---------------------------------------------------------------------------
def run(raw_path: Path = RAW_PATH, out_path: Path = CLEAN_PATH):
    """Run the full pipeline. Saves the display view and returns (display, ml)."""
    raw = load_raw(raw_path)
    display_df = build_display_df(raw)
    ml_df = build_ml_df(display_df)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    display_df.to_parquet(out_path, index=False)
    logger.info("Saved display dataset (%d rows) -> %s", len(display_df), out_path)

    return display_df, ml_df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    display_df, ml_df = run()
    print("\n--- Summary ---------------------------------------------")
    print(f"Display dataset : {len(display_df):>5} rows, {display_df.shape[1]} columns")
    print(f"ML dataset      : {len(ml_df):>5} rows  (outliers removed)")
    print(f"Columns         : {list(display_df.columns)}")