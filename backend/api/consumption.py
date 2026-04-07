"""FastAPI route: POST /api/consumption/ingest"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from data.feature_engineering import load_consumption_df
from database.db import get_db
from database.models import ConsumptionRecord
from models import anomaly_detector

router = APIRouter()


class ConsumptionIn(BaseModel):
    item_id: int = Field(..., ge=1)
    department_id: int = Field(..., ge=1)
    quantity_used: int = Field(..., ge=0, le=100000)
    usage_date: date
    patient_type: str = "general"
    batch_id: int | None = None


class ConsumptionIngestRequest(BaseModel):
    records: list[ConsumptionIn] = Field(..., min_length=1)
    run_anomaly_detection: bool = True


@router.post("/consumption/ingest")
def ingest_consumption(payload: ConsumptionIngestRequest, db: Session = Depends(get_db)):
    """
    Ingest consumption records and run anomaly checks as part of the pipeline.

    Returns inserted count and alert summary for suspicious records.
    """
    rows = []
    for rec in payload.records:
        rows.append(
            ConsumptionRecord(
                item_id=rec.item_id,
                batch_id=rec.batch_id,
                department_id=rec.department_id,
                quantity_used=rec.quantity_used,
                usage_date=rec.usage_date,
                patient_type=rec.patient_type,
            )
        )

    try:
        db.add_all(rows)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Ingestion failed: {exc}") from exc

    result: dict = {
        "inserted": len(rows),
        "anomaly_detection_run": False,
        "alerts": {
            "red": 0,
            "yellow": 0,
        },
    }

    if payload.run_anomaly_detection:
        full_df = load_consumption_df(db)
        if not anomaly_detector.is_trained():
            anomaly_detector.train(full_df)

        recent = anomaly_detector.predict_recent(
            full_df,
            days=7,
            limit=min(200, max(20, len(rows) * 5)),
        )
        result["anomaly_detection_run"] = True
        result["alerts"] = {
            "red": recent["red_alerts"],
            "yellow": recent["yellow_alerts"],
        }
        result["anomalies_sample"] = recent["anomalies"][:10]

    return result
