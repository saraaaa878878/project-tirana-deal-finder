"""
backend/model.py

Price model + deal scorer for the Tirana Deal Finder.

This module is the single source of truth for the model side of the project:
  - build_features : turn listings into model input (used at train AND predict time)
  - train_model    : fit a price model and report MAE / RMSE / R2
  - save_model / load_model
  - predict_price  : estimate the price of one listing
  - score_deal     : grade a listing as great / good / bad

The web app (Week 2) and the AI tools (Week 3) import predict_price and score_deal
from here, so the same logic runs in the notebook, the website, and the assistant.
Train and save the model from notebooks/02_modeling.ipynb.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import joblib

from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# ---------------------------------------------------------------------------
# Configuration  (edit here — these encode the Session 1 EDA decisions)
# ---------------------------------------------------------------------------
MODEL_PATH = Path("models/model.joblib")

TARGET = "price_in_euro"

# Evidence-based feature shortlist from Session 1.
# has_elevator is treated as numeric 0/1 (the only balanced amenity flag).
NUMERIC_FEATURES = ["square_meters", "bedrooms", "bathrooms", "floor", "has_elevator"]
CATEGORICAL_FEATURES = ["furnishing_status"]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

# Price is right-skewed (Session 1) -> model log(price), invert when predicting.
USE_LOG_TARGET = True

# Deal thresholds. gap = (predicted - listed) / predicted.
# A listing priced BELOW its prediction is a deal; how far below sets the grade.
GREAT_DEAL_GAP = 0.15   # listed >= 15% under prediction -> great
GOOD_DEAL_GAP = 0.05    # listed 5-15% under prediction  -> good
# everything else -> "bad" (fairly priced or overpriced)


# ---------------------------------------------------------------------------
# Feature preparation — used by BOTH training and prediction (parity guarantee)
# ---------------------------------------------------------------------------
def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Select the model's input columns from a listings DataFrame.

    Missing columns are created as NaN; the pipeline's imputers fill them, so
    this works whether the input is the full ML dataset or a single listing
    dict that happens to lack a field.
    """
    X = df.reindex(columns=FEATURES).copy()
    # Booleans -> float so they flow through the numeric imputer (True/False/NaN).
    if "has_elevator" in X.columns:
        X["has_elevator"] = X["has_elevator"].astype("float64")
    return X


def _build_pipeline(estimator) -> Pipeline | TransformedTargetRegressor:
    """Preprocessing + model. The pipeline is what guarantees that the exact
    same transformations happen at train and predict time."""
    numeric = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
    ])
    categorical = Pipeline([
        ("impute", SimpleImputer(strategy="constant", fill_value="unknown")),
        ("onehot", OneHotEncoder(handle_unknown="ignore")),
    ])
    preprocess = ColumnTransformer([
        ("num", numeric, NUMERIC_FEATURES),
        ("cat", categorical, CATEGORICAL_FEATURES),
    ])

    pipe = Pipeline([("prep", preprocess), ("model", estimator)])

    if USE_LOG_TARGET:
        # log1p/expm1 handle the skew; inversion happens automatically on predict.
        pipe = TransformedTargetRegressor(
            regressor=pipe, func=np.log1p, inverse_func=np.expm1
        )
    return pipe


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------
def train_model(ml_df: pd.DataFrame, estimator=None,
                test_size: float = 0.2, random_state: int = 42):
    """Train on the ML dataset and return (fitted_model, metrics).

    Pass a different `estimator` (e.g. LinearRegression) from the notebook to
    compare models — feature prep stays identical.
    """
    if estimator is None:
        estimator = RandomForestRegressor(
            n_estimators=300, random_state=random_state, n_jobs=-1
        )

    X = build_features(ml_df)
    y = ml_df[TARGET].astype("float64")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state
    )

    model = _build_pipeline(estimator)
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    metrics = {
        "MAE": float(mean_absolute_error(y_test, preds)),
        "RMSE": float(mean_squared_error(y_test, preds) ** 0.5),
        "R2": float(r2_score(y_test, preds)),
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
    }
    return model, metrics


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------
def save_model(model, path: Path = MODEL_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)


def load_model(path: Path = MODEL_PATH):
    return joblib.load(path)


# ---------------------------------------------------------------------------
# Prediction + deal scoring  (imported by the web app and the AI tools)
# ---------------------------------------------------------------------------
def predict_price(model, listing) -> float:
    """Estimate the price of ONE listing (a dict or a single-row DataFrame)."""
    if isinstance(listing, dict):
        listing = pd.DataFrame([listing])
    X = build_features(listing)
    return float(model.predict(X)[0])


def score_deal(predicted_price: float, listed_price: float) -> dict:
    """Grade a listing by comparing its asking price to the predicted price.

    Returns {"grade": great|good|bad|unknown, "gap_pct": float|None}.
    Positive gap_pct = listed below prediction (cheaper than expected).
    """
    if not predicted_price or not listed_price or listed_price <= 0:
        return {"grade": "unknown", "gap_pct": None}

    gap = (predicted_price - listed_price) / predicted_price
    if gap >= GREAT_DEAL_GAP:
        grade = "great"
    elif gap >= GOOD_DEAL_GAP:
        grade = "good"
    else:
        grade = "bad"
    return {"grade": grade, "gap_pct": round(gap * 100, 1)}
