"""
app/data.py

Data-access layer for the web app.

Loads the cleaned listings and trained model once, adds the location features
required by the model, attaches predicted prices and deal grades, and exposes
the functions used by the Flask routes.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path

import pandas as pd

from backend import preprocessing,model,poi

logger=logging.getLogger(__name__)
DISPLAY_PATH=preprocessing.CLEAN_PATH

# Cache: data and model predictions are loaded only once per app session.
_listings_df:pd.DataFrame|None=None

# ---------------------------------------------------------------------------
# Location features required by the trained model
# ---------------------------------------------------------------------------

def _add_location_features(df:pd.DataFrame)->pd.DataFrame:
    """Add zone, distance to center and location score before prediction."""
    out=df.copy()

    # Prevent duplicate columns if this function is called on enriched data.
    location_columns=["dist_to_center_km","location_score","zone"]
    out=out.drop(columns=[c for c in location_columns if c in out.columns])

    if "latitude" not in out.columns or "longitude" not in out.columns:
        out["dist_to_center_km"]=pd.NA
        out["location_score"]=pd.NA
        out["zone"]="unknown"
        return out

    out["latitude"]=pd.to_numeric(out["latitude"],errors="coerce")
    out["longitude"]=pd.to_numeric(out["longitude"],errors="coerce")

    valid=(
        out["latitude"].notna()
        &out["longitude"].notna()
        &(out["latitude"]!=0)
        &(out["longitude"]!=0)
    )

    location_df=out.loc[valid].copy()

    if location_df.empty:
        out["dist_to_center_km"]=pd.NA
        out["location_score"]=pd.NA
        out["zone"]="unknown"
        return out

    try:
        location_df=poi.add_city_center_distance(location_df)
        location_df=location_df[
            location_df["dist_to_center_km"]<=preprocessing.MAX_DISTANCE_KM
        ].copy()

        if location_df.empty:
            out["dist_to_center_km"]=pd.NA
            out["location_score"]=pd.NA
            out["zone"]="unknown"
            return out

        location_df=poi.assign_zones(location_df)
        location_df=poi.add_proximity_features(location_df)
        location_df=poi.compute_location_score(location_df)

        out=out.merge(
            location_df[["listing_id","dist_to_center_km","location_score","zone"]],
            on="listing_id",
            how="left"
        )

        out["zone"]=out["zone"].fillna("unknown")
        return out

    except Exception as exc:
        logger.warning("Could not calculate location features: %s",exc)
        out["dist_to_center_km"]=pd.NA
        out["location_score"]=pd.NA
        out["zone"]="unknown"
        return out

# ---------------------------------------------------------------------------
# Loading and enrichment
# ---------------------------------------------------------------------------

def _enrich(df:pd.DataFrame)->pd.DataFrame:
    """Add location features, predicted price, gap and deal grade."""
    df=_add_location_features(df)

    try:
        trained=model.load_model()
        features=model.build_features(df)
        df["predicted_price"]=trained.predict(features).round(0)
    except Exception as exc:
        logger.warning(
            "Could not load or run the model (%s). Run the final save cell in "
            "notebooks/02_modeling.ipynb to create models/model.joblib.",
            exc
        )
        df["predicted_price"]=None

    grades=[]
    gaps=[]

    for predicted,listed in zip(df["predicted_price"],df["price_in_euro"]):
        if pd.isna(predicted) or pd.isna(listed):
            grades.append("unknown")
            gaps.append(None)
            continue

        result=model.score_deal(float(predicted),float(listed))
        grades.append(result["grade"])
        gaps.append(result["gap_pct"])

    df["deal_grade"]=grades
    df["gap_pct"]=gaps

    return df


def _load()->pd.DataFrame:
    """Load and enrich listings once, then reuse the cached DataFrame."""
    global _listings_df

    if _listings_df is None:
        if not Path(DISPLAY_PATH).exists():
            logger.info("Clean dataset not found; running preprocessing...")
            preprocessing.run()

        raw=pd.read_parquet(DISPLAY_PATH)
        _listings_df=_enrich(raw)

        logger.info(
            "Loaded and enriched %d listings for the web app",
            len(_listings_df)
        )

    return _listings_df


def clear_cache()->None:
    """Force data and predictions to be reloaded on the next request."""
    global _listings_df
    _listings_df=None


def _clean_record(record:dict)->dict:
    """Convert pandas missing values to None for Flask templates."""
    cleaned={}

    for key,value in record.items():
        try:
            cleaned[key]=None if pd.isna(value) else value
        except (TypeError,ValueError):
            cleaned[key]=value

    return cleaned

# ---------------------------------------------------------------------------
# Public functions used by Flask routes
# ---------------------------------------------------------------------------

def get_all_listings(limit:int|None=None)->list[dict]:
    df=_load()
    records=[_clean_record(r) for r in df.to_dict(orient="records")]
    return records[:limit] if limit is not None else records


def get_listing(listing_id)->dict|None:
    df=_load()

    try:
        listing_id=int(listing_id)
    except (TypeError,ValueError):
        return None

    match=df[df["listing_id"]==listing_id]

    if match.empty:
        return None

    return _clean_record(match.iloc[0].to_dict())


def search_listings(min_price=None,max_price=None,bedrooms=None,
                    min_sqm=None,max_sqm=None,deal_grade=None,
                    limit=None)->list[dict]:
    """Filter listings; arguments left as None are ignored."""
    df=_load()
    mask=pd.Series(True,index=df.index)

    if min_price is not None:
        mask&=df["price_in_euro"]>=min_price
    if max_price is not None:
        mask&=df["price_in_euro"]<=max_price
    if bedrooms is not None:
        mask&=df["bedrooms"]==bedrooms
    if min_sqm is not None:
        mask&=df["square_meters"]>=min_sqm
    if max_sqm is not None:
        mask&=df["square_meters"]<=max_sqm
    if deal_grade:
        mask&=df["deal_grade"]==deal_grade

    records=[
        _clean_record(r)
        for r in df.loc[mask].to_dict(orient="records")
    ]

    return records[:limit] if limit is not None else records


def get_hero_stats()->dict:
    """Headline statistics shown on the home page."""
    df=_load()

    ppsqm=(
        df["price_in_euro"]/df["square_meters"]
    ).replace([float("inf"),float("-inf")],pd.NA).dropna()

    grades=df["deal_grade"].value_counts()

    return {
        "total":int(len(df)),
        "median_ppsqm":int(ppsqm.median()) if not ppsqm.empty else 0,
        "great_deals":int(grades.get("great",0)),
        "good_deals":int(grades.get("good",0))
    }


def get_filter_bounds()->dict:
    """Return sensible ranges for the website filter controls."""
    df=_load()

    return {
        "price_min":int(df["price_in_euro"].quantile(.01)),
        "price_max":int(df["price_in_euro"].quantile(.99)),
        "sqm_min":int(df["square_meters"].quantile(.01)),
        "sqm_max":int(df["square_meters"].quantile(.99)),
        "bedroom_options":sorted(
            int(value)
            for value in df["bedrooms"].dropna().unique()
        ),
        "total":int(len(df))
    }