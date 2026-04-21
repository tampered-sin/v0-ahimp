"""FastAPI route: GET /api/anomalies/recent"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database.db import get_db
from data.feature_engineering import load_consumption_df
from models import anomaly_detector

router = APIRouter()


@router.get("/anomalies/recent")
def recent_anomalies(
    days: int = Query(default=7, ge=1, le=90),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    df = load_consumption_df(db)
    if df.empty:
        raise HTTPException(404, "No consumption data available")

    if not anomaly_detector.is_trained():
        anomaly_detector.train(df)

    result = anomaly_detector.predict_recent(df, days=days, limit=limit)
    return result
