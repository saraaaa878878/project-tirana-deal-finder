"""
backend/model.py

Price model and deal scorer for the Tirana Deal Finder.

- train_model: trains Random Forest by default or another supplied candidate
- build_final_model: creates the final ExtraTrees + HistGB 50/50 blend
- fit_final_model: trains the final blend on all available data
- save_model/load_model: saves and loads models/model.joblib
- predict_price: predicts one listing's price
- score_deal: classifies a listing as great/good/bad

Train and save the final model from notebooks/02_modeling.ipynb.
"""

from __future__ import annotations

from pathlib import Path
import joblib
import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer,TransformedTargetRegressor
from sklearn.ensemble import RandomForestRegressor,ExtraTreesRegressor,HistGradientBoostingRegressor,VotingRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error,mean_squared_error,r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODEL_PATH=Path("models/model.joblib")
TARGET="price_in_euro"
RANDOM_STATE=42
USE_LOG_TARGET=True

NUMERIC_FEATURES=["square_meters","bedrooms","bathrooms","floor","has_elevator","dist_to_center_km","location_score"]
CATEGORICAL_FEATURES=["furnishing_status","zone"]
FEATURES=NUMERIC_FEATURES+CATEGORICAL_FEATURES

GREAT_DEAL_GAP=.15
GOOD_DEAL_GAP=.05

# ---------------------------------------------------------------------------
# Feature preparation
# ---------------------------------------------------------------------------

def build_features(df:pd.DataFrame)->pd.DataFrame:
    """Select and normalize the features expected by the model."""
    X=df.reindex(columns=FEATURES).copy()

    for column in NUMERIC_FEATURES:
        X[column]=pd.to_numeric(X[column],errors="coerce")

    for column in CATEGORICAL_FEATURES:
        X[column]=X[column].astype("object")

    return X


def _make_onehot_encoder():
    """Create a dense OneHotEncoder compatible with sklearn versions."""
    try:
        return OneHotEncoder(handle_unknown="ignore",sparse_output=False)
    except TypeError:
        return OneHotEncoder(handle_unknown="ignore",sparse=False)


def _build_pipeline(estimator,use_log_target:bool=USE_LOG_TARGET):
    """Create the preprocessing and regression pipeline."""
    numeric=Pipeline([
        ("impute",SimpleImputer(strategy="median"))
    ])

    categorical=Pipeline([
        ("impute",SimpleImputer(strategy="constant",fill_value="unknown")),
        ("onehot",_make_onehot_encoder())
    ])

    preprocess=ColumnTransformer([
        ("num",numeric,NUMERIC_FEATURES),
        ("cat",categorical,CATEGORICAL_FEATURES)
    ],remainder="drop",sparse_threshold=0)

    pipeline=Pipeline([
        ("prep",preprocess),
        ("model",estimator)
    ])

    if use_log_target:
        return TransformedTargetRegressor(
            regressor=pipeline,
            func=np.log1p,
            inverse_func=np.expm1
        )

    return pipeline

# ---------------------------------------------------------------------------
# Final Blend 50/50
# ---------------------------------------------------------------------------

def build_final_model(random_state:int=RANDOM_STATE):
    """Create the selected ExtraTrees + HistGB 50/50 blend."""
    extra_trees=_build_pipeline(
        ExtraTreesRegressor(
            n_estimators=800,
            max_depth=None,
            min_samples_leaf=1,
            max_features=.6,
            random_state=random_state,
            n_jobs=-1
        ),
        use_log_target=True
    )

    hist_gradient_boosting=_build_pipeline(
        HistGradientBoostingRegressor(
            max_iter=800,
            max_depth=None,
            learning_rate=.02,
            l2_regularization=1.0,
            random_state=random_state
        ),
        use_log_target=True
    )

    return VotingRegressor(
        estimators=[
            ("extra_trees",extra_trees),
            ("hist_gradient_boosting",hist_gradient_boosting)
        ],
        weights=[.5,.5]
    )

# ---------------------------------------------------------------------------
# Training and evaluation
# ---------------------------------------------------------------------------

def train_model(ml_df:pd.DataFrame,estimator=None,test_size:float=.2,random_state:int=RANDOM_STATE):
    """Train Random Forest by default or another supplied candidate model."""
    X=build_features(ml_df)
    y=ml_df[TARGET].astype("float64")

    X_train,X_test,y_train,y_test=train_test_split(
        X,y,test_size=test_size,random_state=random_state
    )

    if estimator is None:
        estimator=RandomForestRegressor(
            n_estimators=300,
            random_state=random_state,
            n_jobs=-1
        )

    fitted_model=_build_pipeline(estimator,use_log_target=USE_LOG_TARGET)
    fitted_model.fit(X_train,y_train)
    predictions=fitted_model.predict(X_test)

    metrics={
        "MAE":float(mean_absolute_error(y_test,predictions)),
        "RMSE":float(mean_squared_error(y_test,predictions)**.5),
        "R2":float(r2_score(y_test,predictions)),
        "n_train":int(len(X_train)),
        "n_test":int(len(X_test))
    }

    return fitted_model,metrics


def fit_final_model(ml_df:pd.DataFrame,random_state:int=RANDOM_STATE):
    """Train the final Blend 50/50 on all available ML data."""
    X=build_features(ml_df)
    y=ml_df[TARGET].astype("float64")

    final_model=build_final_model(random_state)
    final_model.fit(X,y)

    return final_model

# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_model(trained_model,path:Path=MODEL_PATH)->Path:
    """Save the complete fitted model to disk."""
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    joblib.dump(trained_model,path)
    return path


def load_model(path:Path=MODEL_PATH):
    """Load the saved model from disk."""
    path=Path(path)

    if not path.exists():
        raise FileNotFoundError(
            f"Model not found at {path}. Run the final save cell in 02_modeling.ipynb."
        )

    return joblib.load(path)

# ---------------------------------------------------------------------------
# Prediction and deal scoring
# ---------------------------------------------------------------------------

def predict_price(trained_model,listing)->float:
    """Predict the price of one listing."""
    if isinstance(listing,dict):
        listing=pd.DataFrame([listing])

    if not isinstance(listing,pd.DataFrame):
        raise TypeError("listing must be a dictionary or pandas DataFrame")

    prediction=float(trained_model.predict(build_features(listing))[0])

    if not np.isfinite(prediction):
        raise ValueError("The model returned an invalid prediction")

    return prediction


def score_deal(predicted_price:float,listed_price:float)->dict:
    """Classify a listing as great, good or bad."""
    try:
        predicted_price=float(predicted_price)
        listed_price=float(listed_price)
    except (TypeError,ValueError):
        return {"grade":"unknown","gap_pct":None}

    if not np.isfinite(predicted_price) or not np.isfinite(listed_price) or predicted_price<=0 or listed_price<=0:
        return {"grade":"unknown","gap_pct":None}

    gap=(predicted_price-listed_price)/predicted_price

    if gap>=GREAT_DEAL_GAP:
        grade="great"
    elif gap>=GOOD_DEAL_GAP:
        grade="good"
    else:
        grade="bad"

    return {"grade":grade,"gap_pct":round(gap*100,1)}