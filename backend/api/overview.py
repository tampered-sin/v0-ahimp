"""FastAPI route: GET /api/model-overview"""
import pickle
from fastapi import APIRouter, HTTPException
from config import PKL_DIR

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
