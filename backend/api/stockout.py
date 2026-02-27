"""FastAPI route: GET /api/stockout-risk"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database.db import get_db
from data.feature_engineering import load_consumption_df, build_demand_features, build_stockout_features
from models import stockout_model

router = APIRouter()


@router.get("/stockout-risk")
def stockout_risk(db: Session = Depends(get_db)):
    if not stockout_model.is_trained():
        raise HTTPException(503, "Model not trained yet – please wait for boot training.")
    df      = load_consumption_df(db)
    feat_df = build_stockout_features(df)
    # attach item_name
    name_map = df.groupby("item_id")["item_name"].first()
    feat_df["item_name"] = feat_df["item_id"].map(name_map)
    result  = stockout_model.predict_all(feat_df)
    return result
