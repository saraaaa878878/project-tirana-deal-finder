"""
backend/poi.py

Points of Interest (POI) proximity scoring for the Tirana Deal Finder.

Loads coordinates of major institutions (hospitals, schools, banks, parks,
malls) and computes, for every listing, how close it is to each category.
These proximity features feed into the model as additional location signal,
alongside the plain distance-to-center feature computed in preprocessing.py.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

POI_PATH = Path("data/tirana_pois.json")

# Default weights for the location score. Higher weight = matters more
# when judging how "well placed" a listing is. Tweak freely.
DEFAULT_WEIGHTS = {
    "hospital": 1.0,
    "school": 1.0,
    "bank": 0.5,
    "park": 0.7,
    "mall": 0.6,
}

# Distance (km) at which a category's contribution decays to ~37% (1/e).
# Smaller = only very close POIs matter. Larger = distance matters less.
DECAY_KM = 2.0


# ---------------------------------------------------------------------------
# Load POI data
# ---------------------------------------------------------------------------
def load_pois(path: Path = POI_PATH) -> dict:
    """Load the POI JSON file (categories -> list of {name, lat, lng})."""
    path = Path(path)
    with open(path, "r", encoding="utf-8") as f:
        pois = json.load(f)
    total = sum(len(v) for v in pois.values())
    logger.info("POI: loaded %d institution(s) across %d categories from %s",
                total, len(pois), path)
    return pois


# ---------------------------------------------------------------------------
# Haversine distance (great-circle distance between two GPS points, in km)
# ---------------------------------------------------------------------------
def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Air distance (km) between two GPS coordinates."""
    R = 6371.0
    lat1, lng1, lat2, lng2 = map(np.radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlng / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


def _nearest_distance(lat: float, lng: float, poi_list: list[dict]) -> float:
    """Distance (km) to the nearest POI in the list. NaN if no coordinates."""
    if pd.isna(lat) or pd.isna(lng) or not poi_list:
        return np.nan
    distances = [haversine_distance(lat, lng, p["lat"], p["lng"]) for p in poi_list]
    return float(min(distances))


# ---------------------------------------------------------------------------
# Zone centers (approximate GPS center of each Tirana neighborhood).
# Used to assign every listing to its nearest zone by coordinates, since most
# addresses in the raw data are street names and don't mention the zone/
# neighborhood by name (substring matching on address text misses ~90%,
# per Session 1 EDA).
# ---------------------------------------------------------------------------
TIRANA_ZONE_CENTERS = {
    "Blloku": (41.32222, 19.81444),
    "Komuna e Parisit": (41.32583, 19.82667),
    "21 Dhjetori": (41.33472, 19.82861),
    "Kombinat": (41.29889, 19.77694),
    "Don Bosko": (41.30861, 19.78889),
    "Ali Demi": (41.31417, 19.83833),
    "Fresk / Selitë": (41.35306, 19.84806),
    "Yzberisht": (41.34333, 19.75917),
    "Astir": (41.28861, 19.83500),
    "Laprakë": (41.32833, 19.78472),
    "Kinostudio": (41.31056, 19.78056),
    "Unaza e Re": (41.33056, 19.80167),
    "Paskuqan": (41.37500, 19.79028),
    "Sauk": (41.29306, 19.80417),
    "Qendra (Skenderbej)": (41.32778, 19.81861),
}

# Approximate city centre (Skanderbeg Square) — used for a continuous
# "distance from centre" feature, separate from the discrete zone label.
CITY_CENTER = (41.32778, 19.81861)


def _nearest_zone(lat: float, lng: float, zone_centers: dict) -> str:
    """Assign the nearest neighborhood (zone) by GPS coordinates."""
    if pd.isna(lat) or pd.isna(lng):
        return "unknown"
    best_zone, best_dist = "unknown", float("inf")
    for zone, (zlat, zlng) in zone_centers.items():
        dist = haversine_distance(lat, lng, zlat, zlng)
        if dist < best_dist:
            best_zone, best_dist = zone, dist
    return best_zone


def assign_zones(df: pd.DataFrame, zone_centers: dict | None = None) -> pd.DataFrame:
    """Adds a 'zone' column by assigning each listing to its geographically
    nearest neighborhood (rather than text-matching the address, which only
    catches ~23% of rows per Session 1 EDA)."""
    if zone_centers is None:
        zone_centers = TIRANA_ZONE_CENTERS

    if "latitude" not in df.columns or "longitude" not in df.columns:
        logger.warning("Zone: 'latitude'/'longitude' missing, skipping")
        df["zone"] = "unknown"
        return df

    df["zone"] = [
        _nearest_zone(lat, lng, zone_centers)
        for lat, lng in zip(df["latitude"], df["longitude"])
    ]
    logger.info("Zone: assignment done -> %s", df["zone"].value_counts().to_dict())
    return df


# ---------------------------------------------------------------------------
# Distance to city center
# ---------------------------------------------------------------------------
def add_city_center_distance(df: pd.DataFrame) -> pd.DataFrame:
    """Adds 'dist_to_center_km': distance (km) from each listing to the
    Tirana city center (Skanderbeg Square)."""
    if "latitude" not in df.columns or "longitude" not in df.columns:
        logger.warning("City centre: 'latitude'/'longitude' missing, skipping")
        df["dist_to_center_km"] = np.nan
        return df

    center_lat, center_lng = CITY_CENTER
    df["dist_to_center_km"] = [
        haversine_distance(lat, lng, center_lat, center_lng)
        if pd.notna(lat) and pd.notna(lng)
        else np.nan
        for lat, lng in zip(df["latitude"], df["longitude"])
    ]
    logger.info("City centre distance: mean %.2f km", df["dist_to_center_km"].mean())
    return df


# ---------------------------------------------------------------------------
# Proximity features (one column per POI category)
# ---------------------------------------------------------------------------
def add_proximity_features(df: pd.DataFrame, pois: dict | None = None) -> pd.DataFrame:
    """Adds a 'dist_to_<category>_km' column per POI category
    (e.g. dist_to_hospital_km, dist_to_school_km, ...).
    Requires df to already have 'latitude' and 'longitude'."""
    if pois is None:
        pois = load_pois()

    if "latitude" not in df.columns or "longitude" not in df.columns:
        logger.warning("Proximity: 'latitude'/'longitude' missing, skipping")
        return df

    for category, poi_list in pois.items():
        col_name = f"dist_to_{category}_km"
        df[col_name] = [
            _nearest_distance(lat, lng, poi_list)
            for lat, lng in zip(df["latitude"], df["longitude"])
        ]
        mean_dist = df[col_name].mean()
        logger.info("Proximity: %s done (mean: %.2f km)", col_name,
                    mean_dist if pd.notna(mean_dist) else float("nan"))

    return df


# ---------------------------------------------------------------------------
# Location score (0-1, where 1 = very close to key institutions)
# ---------------------------------------------------------------------------
def compute_location_score(df: pd.DataFrame,
                            weights: dict | None = None,
                            decay_km: float = DECAY_KM) -> pd.DataFrame:
    """Combines all dist_to_*_km columns into a 0-1 score with exponential
    decay: closer to institutions -> higher score."""
    if weights is None:
        weights = DEFAULT_WEIGHTS

    dist_cols = {cat: f"dist_to_{cat}_km" for cat in weights
                 if f"dist_to_{cat}_km" in df.columns}

    if not dist_cols:
        logger.warning("Location score: no dist_to_*_km columns found, skipping")
        df["location_score"] = np.nan
        return df

    total_weight = sum(weights[cat] for cat in dist_cols)
    score = pd.Series(0.0, index=df.index)

    for cat, col in dist_cols.items():
        cat_score = np.exp(-df[col] / decay_km)  # 1.0 at dist=0, ~0.37 at dist=decay_km
        score += weights[cat] * cat_score.fillna(0)

    df["location_score"] = (score / total_weight).clip(0, 1)
    logger.info("Location score: done (mean: %.3f)", df["location_score"].mean())
    return df