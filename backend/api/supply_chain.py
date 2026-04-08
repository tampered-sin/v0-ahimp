"""FastAPI routes for supply chain agent operations."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from agents.config import AgentTask
from agents.supply_chain_agent import SupplyChainAgent, build_supply_chain_payload
from database.db import get_db

router = APIRouter()


class SupplyChainRequest(BaseModel):
    risk_threshold: float = Field(0.7, ge=0.0, le=1.0)
    max_items: int = Field(10, ge=1, le=200)
    cadence_hours: int = Field(1, ge=1, le=24)
    supplier_overrides: dict[int, list[dict]] = Field(default_factory=dict)


def _run_supply_chain_task(payload: SupplyChainRequest, db: Session, auto_purchase: bool) -> dict:
    agent = SupplyChainAgent()
    task_payload = build_supply_chain_payload(
        risk_threshold=payload.risk_threshold,
        max_items=payload.max_items,
        auto_purchase=auto_purchase,
        cadence_hours=payload.cadence_hours,
        supplier_overrides=payload.supplier_overrides,
    )
    task = AgentTask(
        name="supply_chain_monitor",
        description="Monitor stockout risk and coordinate supplier purchasing",
        payload=task_payload,
    )
    return agent.run(task=task, context={"db": db})


@router.post("/agents/supply-chain/at-risk")
def supply_chain_at_risk(payload: SupplyChainRequest, db: Session = Depends(get_db)):
    result = _run_supply_chain_task(payload, db, auto_purchase=False)
    if not result.get("ok"):
        raise HTTPException(status_code=500, detail=result.get("error", "Supply chain analysis failed"))
    return result


@router.post("/agents/supply-chain/auto-purchase")
def supply_chain_auto_purchase(payload: SupplyChainRequest, db: Session = Depends(get_db)):
    result = _run_supply_chain_task(payload, db, auto_purchase=True)
    if not result.get("ok"):
        raise HTTPException(status_code=500, detail=result.get("error", "Auto purchase failed"))
    return result
