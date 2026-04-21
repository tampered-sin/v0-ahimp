"""FastAPI routes for model explainability."""
from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from data.feature_engineering import build_demand_features, load_consumption_df
from database.db import get_db
from models import demand_model
from models.explainability import (
    LIMEExplainer,
    SHAPExplainer,
    build_item_explanation,
)

router = APIRouter()

_shap_explainer = SHAPExplainer()
_lime_explainer = LIMEExplainer()


def _prepare_features(db: Session) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw_df = load_consumption_df(db)
    feat_df = build_demand_features(raw_df)
    feat_df["item_name"] = (
        raw_df.groupby("item_id")["item_name"].first().reindex(feat_df["item_id"].values).values
    )
    return raw_df, feat_df


def _resolve_item_from_prediction_id(raw_df: pd.DataFrame, prediction_id: int) -> tuple[int, pd.Timestamp] | None:
    if raw_df.empty or "consumption_id" not in raw_df:
        return None

    row = raw_df[raw_df["consumption_id"] == prediction_id].sort_values("usage_date")
    if row.empty:
        return None

    resolved = row.iloc[-1]
    return int(resolved["item_id"]), pd.Timestamp(resolved["usage_date"])


@router.get("/explain/item/{item_id}")
def explain_item(
    item_id: int,
    top_k: int = Query(8, ge=3, le=20, description="Number of top explanation features"),
    db: Session = Depends(get_db),
):
    if not demand_model.is_trained():
        raise HTTPException(503, "Demand model not trained yet")

    raw_df, feat_df = _prepare_features(db)
    if raw_df.empty or feat_df.empty:
        raise HTTPException(404, "No feature data available for explainability")

    model = demand_model._load_lgbm()
    meta = demand_model._load_meta()
    feature_names = list(meta.get("feature_cols", demand_model.FEATURE_COLS))

    payload = build_item_explanation(
        model=model,
        feat_df=feat_df,
        item_id=item_id,
        feature_names=feature_names,
        shap_explainer=_shap_explainer,
        lime_explainer=_lime_explainer,
        top_k=top_k,
    )
    if payload.get("error"):
        raise HTTPException(404, payload["error"])

    forecast = demand_model.predict_forecast(feat_df, item_id)
    payload["model"] = "LightGBM"
    payload["forecast_preview"] = forecast.get("forecast", [])[:3]
    return payload


@router.get("/explain/prediction/{prediction_id}")
def explain_prediction(
    prediction_id: int,
    top_k: int = Query(8, ge=3, le=20, description="Number of top explanation features"),
    db: Session = Depends(get_db),
):
    if not demand_model.is_trained():
        raise HTTPException(503, "Demand model not trained yet")

    raw_df, feat_df = _prepare_features(db)
    resolved = _resolve_item_from_prediction_id(raw_df, prediction_id)
    if resolved is None:
        raise HTTPException(404, "Prediction reference not found")

    item_id, usage_date = resolved
    model = demand_model._load_lgbm()
    meta = demand_model._load_meta()
    feature_names = list(meta.get("feature_cols", demand_model.FEATURE_COLS))

    payload = build_item_explanation(
        model=model,
        feat_df=feat_df,
        item_id=item_id,
        feature_names=feature_names,
        shap_explainer=_shap_explainer,
        lime_explainer=_lime_explainer,
        top_k=top_k,
        target_usage_date=usage_date,
    )
    if payload.get("error"):
        raise HTTPException(404, payload["error"])

    payload["prediction_id"] = int(prediction_id)
    payload["model"] = "LightGBM"
    return payload
