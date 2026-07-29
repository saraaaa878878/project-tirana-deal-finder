"""
tests/smoke_test.py

Run:
    python tests/smoke_test.py
"""

import os,sys
from pathlib import Path
import numpy as np
from sklearn.metrics import mean_absolute_error,mean_squared_error,r2_score
from sklearn.model_selection import train_test_split

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
os.chdir(ROOT)

from backend import preprocessing,model

_passed=0
_failed=0

def check(name,condition,detail=""):
    global _passed,_failed
    mark="PASS" if condition else "FAIL"
    _passed+=int(condition)
    _failed+=int(not condition)
    print(f"  [{mark}] {name}"+(f"  ({detail})" if detail else ""))

def section(title):
    print(f"\n=== {title} ===")

section("Preprocessing")
display_df,ml_df=preprocessing.run()

check("display_df has rows",len(display_df)>0,f"{len(display_df)} rows")
check("ml_df has rows",len(ml_df)>0,f"{len(ml_df)} rows")
check("ml_df <= display_df",len(ml_df)<=len(display_df))
check("listing_id exists","listing_id" in display_df.columns)
check("listing_id unique",display_df["listing_id"].is_unique)

for col in ["bedrooms","bathrooms","floor","square_meters"]:
    if col in display_df.columns:
        check(f"no negative {col}",(display_df[col].dropna()>=0).all())

required=model.FEATURES+[model.TARGET]
missing=[col for col in required if col not in ml_df.columns]
check("all model columns exist",not missing,f"missing: {missing}" if missing else "")

if not missing:
    check("no nulls in model data",ml_df[required].isna().sum().sum()==0)

check("price within bounds",ml_df["price_in_euro"].between(preprocessing.PRICE_MIN,preprocessing.PRICE_MAX).all())
check("size within bounds",ml_df["square_meters"].between(preprocessing.SQM_MIN,preprocessing.SQM_MAX).all())

section("Final model evaluation")
X=model.build_features(ml_df)
y=ml_df[model.TARGET].astype("float64")

X_train,X_test,y_train,y_test=train_test_split(
    X,y,test_size=.2,random_state=model.RANDOM_STATE
)

evaluation_model=model.build_final_model()
evaluation_model.fit(X_train,y_train)
predictions=evaluation_model.predict(X_test)

mae=float(mean_absolute_error(y_test,predictions))
rmse=float(mean_squared_error(y_test,predictions)**.5)
r2=float(r2_score(y_test,predictions))

print(f"  MAE: €{mae:,.0f}")
print(f"  RMSE: €{rmse:,.0f}")
print(f"  R²: {r2:.3f}")
print(f"  Train/Test: {len(X_train)}/{len(X_test)}")

check("MAE positive",mae>0 and np.isfinite(mae))
check("RMSE >= MAE",rmse>=mae)
check("R² finite",np.isfinite(r2))
check("R² reasonable",r2>.3,f"{r2:.3f}")

section("Final model training")
trained=model.fit_final_model(ml_df)
check("final model trains",trained is not None,type(trained).__name__)

section("Save / load")
model.save_model(trained)
check("model file written",model.MODEL_PATH.exists(),str(model.MODEL_PATH))
reloaded=model.load_model()
check("model reloads",reloaded is not None,type(reloaded).__name__)

section("Prediction")
sample=ml_df.iloc[0].to_dict()
prediction=model.predict_price(reloaded,sample)
check("prediction positive",prediction>0,f"€{prediction:,.0f}")

sparse={"square_meters":90,"bedrooms":2}
sparse_prediction=model.predict_price(reloaded,sparse)
check("sparse prediction works",sparse_prediction>0,f"€{sparse_prediction:,.0f}")

section("Deal scoring")
check("great deal",model.score_deal(100_000,80_000)["grade"]=="great")
check("good deal",model.score_deal(100_000,92_000)["grade"]=="good")
check("bad deal",model.score_deal(100_000,100_000)["grade"]=="bad")
check("unknown zero price",model.score_deal(100_000,0)["grade"]=="unknown")
check("unknown prediction",model.score_deal(None,100_000)["grade"]=="unknown")
check("gap percentage",model.score_deal(100_000,80_000)["gap_pct"]==20.0)

print(f"\n{'-'*40}")
print(f"  {_passed} passed, {_failed} failed")
print(f"{'-'*40}")

sys.exit(1 if _failed else 0)