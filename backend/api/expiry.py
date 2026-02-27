"""FastAPI route: GET /api/expiry-risk"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database.db import get_db
from data.feature_engineering import load_consumption_df, build_expiry_features
from models import expiry_model

router = APIRouter()


@router.get("/expiry-risk")
def expiry_risk(db: Session = Depends(get_db)):
    if not expiry_model.is_trained():
        raise HTTPException(503, "Model not trained yet – please wait for boot training.")
    df      = load_consumption_df(db)
    feat_df = build_expiry_features(df)
    if feat_df.empty:
        return {"items": [], "metrics": {}}
    # attach item_name
    name_map = df.groupby("item_id")["item_name"].first()
    feat_df["item_name"] = feat_df["item_id"].map(name_map)
    result  = expiry_model.predict_all(feat_df)
    return result
