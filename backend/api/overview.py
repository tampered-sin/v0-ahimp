"""FastAPI route: GET /api/model-overview"""
import pickle
from datetime import timedelta

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from sqlalchemy.orm import Session

from config import PKL_DIR
from data.feature_engineering import build_demand_features, load_consumption_df
from database.db import get_db
from models import demand_model

router = APIRouter()

PKL_DEMAND_META   = PKL_DIR / "demand_meta.pkl"
PKL_STOCKOUT_META = PKL_DIR / "stockout_meta.pkl"
PKL_EXPIRY_META   = PKL_DIR / "expiry_meta.pkl"


@router.get("/model-overview")
def model_overview():
    if not (PKL_DEMAND_META.exists() and PKL_STOCKOUT_META.exists() and PKL_EXPIRY_META.exists()):
        raise HTTPException(503, "Models not trained yet.")

    with open(PKL_DEMAND_META,   "rb") as f: demand_meta   = pickle.load(f)
    with open(PKL_STOCKOUT_META, "rb") as f: stockout_meta = pickle.load(f)
    with open(PKL_EXPIRY_META,   "rb") as f: expiry_meta   = pickle.load(f)

    # SHAP-style feature importance from demand XGBoost (best proxy)
    shap_features = demand_meta.get("feature_importance", [])

    architecture = [
        {"step": 1, "name": "Data Generation",      "desc": "Synthea-inspired synthetic consumption records (~20 yrs)", "icon": "Database"},
        {"step": 2, "name": "Preprocessing",         "desc": "Null handling, type casting, date parsing",               "icon": "Filter"},
        {"step": 3, "name": "Feature Engineering",   "desc": "Rolling avg, lag, seasonality, velocity, stock ratio",    "icon": "Wrench"},
        {"step": 4, "name": "Demand Forecast",        "desc": "LightGBM Regressor – 14-day item demand prediction",      "icon": "TrendingUp"},
        {"step": 5, "name": "Stockout Risk",          "desc": "Random Forest Classifier – 7-day stockout probability",   "icon": "AlertTriangle"},
        {"step": 6, "name": "Expiry Risk",            "desc": "Logistic Regression – batch expiry probability",          "icon": "Clock"},
        {"step": 7, "name": "Cost Impact",            "desc": "Business savings simulation formula",                     "icon": "DollarSign"},
        {"step": 8, "name": "Dashboard & Reporting",  "desc": "Streamlit-style Next.js dashboard with live API",         "icon": "BarChart"},
    ]

    return {
        "demand_metrics":        demand_meta.get("xgb", {}),
        "demand_lr_metrics":     demand_meta.get("lr", {}),
        "demand_arima_metrics":  demand_meta.get("arima", {}),
        "stockout_metrics":      {k: v for k, v in stockout_meta.items() if k != "confusion_matrix"},
        "stockout_confusion_matrix": stockout_meta.get("confusion_matrix", []),
        "expiry_metrics":        {"auc": expiry_meta.get("auc")},
        "feature_importance":    shap_features,
        "architecture":          architecture,
    }


@router.get("/model-comparison")
def model_comparison():
    if not PKL_DEMAND_META.exists():
        raise HTTPException(503, "Demand model not trained yet.")

    with open(PKL_DEMAND_META, "rb") as f:
        demand_meta = pickle.load(f)

    return {
        "primary_model": demand_meta.get("primary_model", "LightGBM"),
        "lgbm": demand_meta.get("lgbm", demand_meta.get("xgb", {})),
        "lr": demand_meta.get("lr", {}),
        "arima": demand_meta.get("arima", {}),
        "feature_importance": demand_meta.get("feature_importance", []),
    }


@router.get("/model-backtest-2y")
def model_backtest_2y(db: Session = Depends(get_db)):
    if not demand_model.is_trained():
        raise HTTPException(503, "Demand model not trained yet.")

    try:
        raw_df = load_consumption_df(db)
        feat_df = build_demand_features(raw_df)
        if feat_df.empty:
            raise HTTPException(404, "No feature-engineered demand rows available.")

        feat_df["usage_date"] = pd.to_datetime(feat_df["usage_date"], errors="coerce")
        feat_df = feat_df.dropna(subset=["usage_date", "quantity_used"])
        if feat_df.empty:
            raise HTTPException(404, "No usable demand rows for backtest.")

        max_date = feat_df["usage_date"].max()
        cutoff = max_date - timedelta(days=730)
        test_df = feat_df[feat_df["usage_date"] >= cutoff].copy()
        if test_df.empty:
            raise HTTPException(404, "No rows available in 2-year testing window.")

        model = demand_model._load_lgbm()
        preds = model.predict(test_df[demand_model.FEATURE_COLS].to_numpy(dtype=float))

        test_df["predicted"] = np.clip(preds, a_min=0.0, a_max=None)
        test_df["actual"] = test_df["quantity_used"].astype(float)
        test_df["month_key"] = test_df["usage_date"].dt.strftime("%Y-%m")

        monthly = (
            test_df.groupby("month_key", as_index=False)
            .agg(actual=("actual", "sum"), predicted=("predicted", "sum"))
            .sort_values("month_key")
        )

        if monthly.empty:
            raise HTTPException(404, "Monthly aggregation for 2-year backtest is empty.")

        monthly["error"] = monthly["predicted"] - monthly["actual"]
        monthly["abs_error"] = monthly["error"].abs()
        monthly["pct_error"] = np.where(
            monthly["actual"].abs() > 1e-6,
            (monthly["abs_error"] / monthly["actual"].abs()) * 100.0,
            np.nan,
        )

        actual_vals = monthly["actual"].to_numpy(dtype=float)
        pred_vals = monthly["predicted"].to_numpy(dtype=float)
        abs_err = np.abs(pred_vals - actual_vals)

        mae = float(np.mean(abs_err))
        rmse = float(np.sqrt(np.mean((pred_vals - actual_vals) ** 2)))
        denom = np.where(np.abs(actual_vals) > 1e-6, np.abs(actual_vals), np.nan)
        mape = float(np.nanmean((abs_err / denom) * 100.0)) if np.isfinite(np.nanmean((abs_err / denom) * 100.0)) else None
        corr = float(np.corrcoef(actual_vals, pred_vals)[0, 1]) if len(actual_vals) > 1 else None

        ss_res = float(np.sum((actual_vals - pred_vals) ** 2))
        ss_tot = float(np.sum((actual_vals - np.mean(actual_vals)) ** 2))
        r2 = float(1.0 - (ss_res / ss_tot)) if ss_tot > 1e-9 else None

        similarity_components = []
        if mape is not None:
            similarity_components.append(max(0.0, 100.0 - mape))
        if corr is not None and np.isfinite(corr):
            similarity_components.append(max(0.0, min(100.0, ((corr + 1.0) / 2.0) * 100.0)))
        if r2 is not None and np.isfinite(r2):
            similarity_components.append(max(0.0, min(100.0, r2 * 100.0)))
        similarity_score = float(np.mean(similarity_components)) if similarity_components else None

        points = []
        for _, row in monthly.iterrows():
            points.append(
                {
                    "month": str(row["month_key"]),
                    "actual": round(float(row["actual"]), 2),
                    "predicted": round(float(row["predicted"]), 2),
                    "error": round(float(row["error"]), 2),
                    "pct_error": None if pd.isna(row["pct_error"]) else round(float(row["pct_error"]), 2),
                }
            )

        return {
            "window": {
                "label": "2-year testing window",
                "from": cutoff.date().isoformat(),
                "to": max_date.date().isoformat(),
                "months": int(len(monthly)),
                "rows_evaluated": int(len(test_df)),
            },
            "metrics": {
                "mae": round(mae, 4),
                "rmse": round(rmse, 4),
                "mape_pct": None if mape is None else round(mape, 4),
                "correlation": None if corr is None or not np.isfinite(corr) else round(corr, 6),
                "r2": None if r2 is None or not np.isfinite(r2) else round(r2, 6),
                "similarity_score_pct": None if similarity_score is None else round(similarity_score, 2),
            },
            "monthly_points": points,
            "notes": [
                "Predictions use persisted LightGBM demand model on feature-engineered daily rows.",
                "Similarity score blends 1-MAPE, Pearson correlation, and R2 into a 0-100 indicator.",
                "Monthly values are aggregated across all items in the 24-month testing window.",
            ],
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Backtest computation failed: {exc}")
