"""FastAPI route: GET /api/ensemble-forecast?item_id=<int>"""
import importlib
import time

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from data.feature_engineering import build_demand_features, load_consumption_df
from database.db import get_db
from models import demand_model
from models.ensemble_model import VotingPredictor, select_best_single_model, tune_weights_via_grid

router = APIRouter()


def _extract_series(prediction_result: dict) -> np.ndarray | None:
    if not prediction_result or prediction_result.get("error"):
        return None
    forecast = prediction_result.get("forecast", [])
    if not forecast:
        return None
    return np.array([row.get("predicted", 0.0) for row in forecast], dtype=float)


@router.get("/ensemble-forecast")
def ensemble_forecast(
    item_id: int = Query(..., ge=1, description="Item ID to forecast"),
    db: Session = Depends(get_db),
):
    """
    Combine available model forecasts using weighted voting.

    Uses currently available models and gracefully falls back when some models
    are not trained/installed yet.
    """
    if not demand_model.is_trained():
        raise HTTPException(503, "Demand baseline model not trained yet")

    raw_df = load_consumption_df(db)
    feat_df = build_demand_features(raw_df)
    feat_df["item_name"] = (
        raw_df.groupby("item_id")["item_name"].first().reindex(feat_df["item_id"].values).values
    )

    model_outputs: dict[str, np.ndarray] = {}
    model_details: dict[str, dict] = {}

    # LightGBM/xgb-compatible primary forecast
    lgbm_pred = demand_model.predict_forecast(feat_df, item_id)
    lgbm_series = _extract_series(lgbm_pred)
    if lgbm_series is not None:
        model_outputs["lgbm"] = lgbm_series
        model_details["lgbm"] = {"model": "LightGBM", "metrics": lgbm_pred.get("metrics", {})}

    # Linear regression baseline forecast
    lr_pred = demand_model.predict_forecast_lr(feat_df, item_id)
    lr_series = _extract_series(lr_pred)
    if lr_series is not None:
        model_outputs["lr"] = lr_series
        model_details["lr"] = {"model": "LinearRegression", "metrics": lr_pred.get("metrics", {})}

    # Optional LSTM forecast if module exists and model is trained
    try:
        lstm_module = importlib.import_module("models.lstm_model")
        if getattr(lstm_module, "is_trained")(model_type="lstm"):
            lstm_pred = getattr(lstm_module, "predict_forecast")(feat_df, item_id, model_type="lstm")
            lstm_series = _extract_series(lstm_pred)
            if lstm_series is not None:
                model_outputs["lstm"] = lstm_series
                model_details["lstm"] = {"model": "LSTM", "metrics": lstm_pred.get("metrics", {})}

        if getattr(lstm_module, "is_trained")(model_type="gru"):
            gru_pred = getattr(lstm_module, "predict_forecast")(feat_df, item_id, model_type="gru")
            gru_series = _extract_series(gru_pred)
            if gru_series is not None:
                model_outputs["gru"] = gru_series
                model_details["gru"] = {"model": "GRU", "metrics": gru_pred.get("metrics", {})}
    except Exception:
        pass

    # Optional CatBoost forecast for comparison (not in current weighted map)
    try:
        cat_module = importlib.import_module("models.catboost_demand_model")
        if getattr(cat_module, "is_trained")():
            cb_pred = getattr(cat_module, "predict_forecast_catboost")(feat_df, item_id)
            cb_series = _extract_series(cb_pred)
            if cb_series is not None:
                model_details["catboost"] = {
                    "model": "CatBoost",
                    "note": "Available for comparison; not included in weighted voting map yet",
                    "sample_first_day": float(cb_series[0]),
                }
    except Exception:
        pass

    if not model_outputs:
        raise HTTPException(503, "No model forecasts available for ensemble")

    # Tune voting weights against most recent observed horizon when possible.
    tuned_weights = None
    try:
        item_history = (
            feat_df[feat_df["item_id"] == item_id]
            .sort_values("usage_date")
            .tail(len(next(iter(model_outputs.values()))))
        )
        y_recent = item_history["quantity_used"].to_numpy(dtype=float)
        if len(y_recent) == len(next(iter(model_outputs.values()))):
            tuned_weights = tune_weights_via_grid(model_outputs, y_recent, step=0.1)
    except Exception:
        tuned_weights = None

    if tuned_weights:
        voter = VotingPredictor(custom_weights=tuned_weights)
    else:
        voter = VotingPredictor()

    inference_start = time.perf_counter()
    fallback_model = None
    try:
        ensemble_values = voter.combine(model_outputs)
        confidence = voter.confidence(model_outputs)
    except Exception:
        fallback_model, ensemble_values = select_best_single_model(model_outputs)
        confidence = np.ones_like(ensemble_values, dtype=float)
    inference_ms = (time.perf_counter() - inference_start) * 1000.0

    start_date = np.datetime64("today", "D")
    forecast = []
    for idx, pred in enumerate(ensemble_values, start=1):
        day = start_date + np.timedelta64(idx, "D")
        conf = float(confidence[idx - 1])
        forecast.append(
            {
                "date": str(day),
                "predicted": round(float(pred), 1),
                "confidence": round(conf, 4),
                "lower": round(max(0.0, float(pred) * 0.8), 1),
                "upper": round(float(pred) * 1.2, 1),
            }
        )

    return {
        "item_id": item_id,
        "models_used": sorted(model_outputs.keys()),
        "model_details": model_details,
        "fallback_model": fallback_model,
        "weights": tuned_weights or {
            "xgb": 0.4,
            "lgbm": 0.3,
            "lstm": 0.2,
            "lr": 0.1,
        },
        "inference_ms": round(inference_ms, 3),
        "forecast": forecast,
    }
