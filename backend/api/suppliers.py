"""FastAPI routes for supplier scoring workflows."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from agents.supplier_scoring import score_suppliers
from database.db import get_db

router = APIRouter()


class SupplierOverrideIn(BaseModel):
    supplier_id: int = Field(..., ge=1)
    distance_km: float | None = Field(None, ge=0.0)
    sentiment_score: float | None = Field(None, ge=-1.0, le=1.0)
    review_text: str | None = Field(None, max_length=2000)


class SupplierScoringRequest(BaseModel):
    item_id: int = Field(..., ge=1)
    supplier_overrides: list[SupplierOverrideIn] = Field(default_factory=list)


@router.post("/suppliers/scoring")
def supplier_scoring(payload: SupplierScoringRequest, db: Session = Depends(get_db)):
    try:
        return score_suppliers(
            db,
            item_id=payload.item_id,
            supplier_overrides=[entry.model_dump() for entry in payload.supplier_overrides],
        )
    except ValueError as exc:
        message = str(exc)
        if "not found" in message.lower():
            raise HTTPException(status_code=404, detail=message) from exc
        raise HTTPException(status_code=400, detail=message) from exc
