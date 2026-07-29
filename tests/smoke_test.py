"""
tests/smoke_test.py

A quick, dependency-free health check for the data + model pipeline.
Run it before class and re-run it live to prove everything still works:

    python tests/smoke_test.py

It exits with code 0 if all checks pass, 1 if any fail (handy for CI later).
No pytest required — just clear PASS/FAIL output.
"""

import math
import os
import sys
from pathlib import Path

# Make the project root importable and the working directory, so that
# "from backend import ..." and the "data/..." paths resolve no matter where
# this script is launched from.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from backend import preprocessing, model  # noqa: E402

# ---------------------------------------------------------------------------
# Tiny check runner (no test framework needed)
# ---------------------------------------------------------------------------
_passed = 0
_failed = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global _passed, _failed
    mark = "PASS" if condition else "FAIL"
    if condition:
        _passed += 1
    else:
        _failed += 1
    line = f"  [{mark}] {name}"
    if detail:
        line += f"  ({detail})"
    print(line)


def section(title: str) -> None:
    print(f"\n=== {title} ===")


# ---------------------------------------------------------------------------
# 1. Preprocessing
# ---------------------------------------------------------------------------
section("Preprocessing")
display_df, ml_df = preprocessing.run()

check("display_df has rows", len(display_df) > 0, f"{len(display_df)} rows")
check("ml_df has rows", len(ml_df) > 0, f"{len(ml_df)} rows")
check("ml_df <= display_df (outliers removed)", len(ml_df) <= len(display_df))
check("listing_id column exists", "listing_id" in display_df.columns)
check("listing_id is unique", display_df["listing_id"].is_unique)

# No negative values survived in the kept numeric columns.
for col in ["bedrooms", "bathrooms", "floor", "square_meters"]:
    if col in display_df.columns:
        check(f"no negative {col}", (display_df[col].dropna() >= 0).all())

# ML dataset must have no nulls in the columns the model actually uses.
ml_required = [c for c in model.FEATURES + [model.TARGET] if c in ml_df.columns]
no_nulls = ml_df[ml_required].isna().sum().sum() == 0
check("ml_df has no nulls in model features+target", no_nulls)

# Outlier bounds respected in ml_df.
check("ml_df price within bounds",
      ml_df["price_in_euro"].between(preprocessing.PRICE_MIN, preprocessing.PRICE_MAX).all())
check("ml_df size within bounds",
      ml_df["square_meters"].between(preprocessing.SQM_MIN, preprocessing.SQM_MAX).all())

# ---------------------------------------------------------------------------
# 2. Model training + persistence
# ---------------------------------------------------------------------------
section("Model training")
trained, metrics = model.train_model(ml_df)
print(f"  metrics: MAE={metrics['MAE']:,.0f}  RMSE={metrics['RMSE']:,.0f}  "
      f"R2={metrics['R2']:.3f}  ({metrics['n_train']} train / {metrics['n_test']} test)")

check("MAE is a positive number", metrics["MAE"] > 0 and math.isfinite(metrics["MAE"]))
check("RMSE >= MAE", metrics["RMSE"] >= metrics["MAE"])
check("R2 is finite", math.isfinite(metrics["R2"]))
check("R2 is reasonable (> 0.3)", metrics["R2"] > 0.3,
      "low R2 may mean too few rows or weak features")

section("Save / load")
model.save_model(trained)
check("model file written", model.MODEL_PATH.exists(), str(model.MODEL_PATH))
reloaded = model.load_model()
check("model reloads", reloaded is not None)

# ---------------------------------------------------------------------------
# 3. Prediction
# ---------------------------------------------------------------------------
section("Prediction")
sample = ml_df.iloc[0].to_dict()
pred = model.predict_price(reloaded, sample)
check("predict_price returns positive number", pred > 0, f"€{pred:,.0f}")

sparse = {"square_meters": 90, "bedrooms": 2}  # missing fields on purpose
pred_sparse = model.predict_price(reloaded, sparse)
check("predict works on a sparse listing", pred_sparse > 0, f"€{pred_sparse:,.0f}")

# ---------------------------------------------------------------------------
# 4. Deal scoring (pure logic — no model needed)
# ---------------------------------------------------------------------------
section("Deal scoring")
check("great deal (20% under)", model.score_deal(100_000, 80_000)["grade"] == "great")
check("good deal (8% under)", model.score_deal(100_000, 92_000)["grade"] == "good")
check("bad deal (fairly priced)", model.score_deal(100_000, 100_000)["grade"] == "bad")
check("unknown when listed price is 0", model.score_deal(100_000, 0)["grade"] == "unknown")
check("unknown when prediction missing", model.score_deal(None, 100_000)["grade"] == "unknown")
check("gap_pct sign is correct",
      model.score_deal(100_000, 80_000)["gap_pct"] == 20.0)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print(f"\n{'-' * 40}")
print(f"  {_passed} passed, {_failed} failed")
print(f"{'-' * 40}")
sys.exit(1 if _failed else 0)