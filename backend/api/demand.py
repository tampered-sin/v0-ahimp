"""FastAPI route: GET /api/demand-forecast?item_id=<int>"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database.db import get_db
from data.feature_engineering import load_consumption_df, build_demand_features
from models import demand_model

router = APIRouter()


@router.get("/demand-forecast")
def demand_forecast(item_id: int = Query(..., description="Item ID to forecast"),
                    db: Session = Depends(get_db)):
    if not demand_model.is_trained():
        raise HTTPException(503, "Model not trained yet – please wait for boot training.")
    df      = load_consumption_df(db)
    feat_df = build_demand_features(df)
    feat_df["item_name"] = df.groupby("item_id")["item_name"].first().reindex(feat_df["item_id"].values).values
    result  = demand_model.predict_forecast(feat_df, item_id)
    return result


@router.get("/demand-items")
def demand_items(db: Session = Depends(get_db)):
    """Return list of available items for the item selector dropdown."""
    df = load_consumption_df(db)
    items = (
        df.groupby("item_id")["item_name"].first()
        .reset_index()
        .rename(columns={"item_id": "id", "item_name": "name"})
        .to_dict(orient="records")
    )
    return {"items": items}
