"""FastAPI routes for AI agent operations."""
from __future__ import annotations

import csv
from collections import deque
from datetime import datetime, timezone
import io
import os
from threading import Lock
import time
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from agents.config import AgentTask
from agents.data_ingestion_agent import DataIngestionAgent, build_ingestion_payload
from agents.supply_chain_agent import SupplyChainAgent, build_supply_chain_payload
from database.agent_logs import create_agent_log, list_agent_logs, summarize_agent_logs
from database.data_validation import list_audit_records, review_audit_record
from database.db import SessionLocal, get_db

router = APIRouter()

_API_KEY_ENV = "AGENTS_API_KEY"
_RATE_LIMIT_REQUESTS = 100
_RATE_LIMIT_WINDOW_SEC = 60

_RATE_LIMIT_LOCK = Lock()
_RATE_LIMIT_BUCKETS: dict[str, deque[float]] = {}

_JOBS_LOCK = Lock()
_JOBS: dict[str, dict] = {}


class AgentIngestionRequest(BaseModel):
    source_type: str = Field("records", pattern="^(records|csv|api)$")
    csv_path: str | None = None
    api_url: str | None = None
    api_format: str = Field("json", pattern="^(json|xml)$")
    records: list[dict] = Field(default_factory=list)
    allow_partial: bool = True
    run_async: bool = True
    max_retries: int = Field(2, ge=0, le=5)


class AuditReviewRequest(BaseModel):
    action: str = Field(..., pattern="^(approve|reject)$")
    reviewed_by: str = Field(..., min_length=1, max_length=100)
    comment: str | None = Field(None, max_length=255)
    create_consumption_record: bool = False


class SupplyChainRequest(BaseModel):
    risk_threshold: float = Field(0.7, ge=0.0, le=1.0)
    max_items: int = Field(10, ge=1, le=200)
    cadence_hours: int = Field(1, ge=1, le=24)
    supplier_overrides: dict[int, list[dict]] = Field(default_factory=dict)


def require_agent_auth(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    expected = os.getenv(_API_KEY_ENV)
    if not expected:
        return
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


def _rate_limit_key(request: Request, x_api_key: str | None) -> str:
    host = request.client.host if request.client else "unknown"
    identity = x_api_key or host
    return f"{identity}:{request.url.path}"


def enforce_rate_limit(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    now = time.monotonic()
    key = _rate_limit_key(request, x_api_key)

    with _RATE_LIMIT_LOCK:
        bucket = _RATE_LIMIT_BUCKETS.setdefault(key, deque())
        while bucket and now - bucket[0] >= _RATE_LIMIT_WINDOW_SEC:
            bucket.popleft()

        if len(bucket) >= _RATE_LIMIT_REQUESTS:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {_RATE_LIMIT_REQUESTS} requests per minute",
            )
        bucket.append(now)


def _log_agent_event(
    agent_name: str,
    task_description: str,
    status: str,
    result: dict | None = None,
    error: str | None = None,
    metadata: dict | None = None,
) -> None:
    db = SessionLocal()
    try:
        level = "ERROR" if status in {"failed", "error"} else "INFO"
        payload_result = None if result is None else {"result": result, "metadata": metadata or {}}
        payload_errors = None if error is None else {"message": error, "metadata": metadata or {}}

        completed_at = None
        if status in {"succeeded", "failed", "completed", "error"}:
            completed_at = datetime.now(tz=timezone.utc)

        create_agent_log(
            db,
            agent_name=agent_name,
            task_description=task_description,
            status=status,
            level=level,
            result=payload_result,
            errors=payload_errors,
            completed_at=completed_at,
        )
    except Exception:
        # Never block API requests if logging persistence fails.
        pass
    finally:
        db.close()


def _update_job(job_id: str, **updates) -> None:
    with _JOBS_LOCK:
        if job_id not in _JOBS:
            return
        _JOBS[job_id].update(updates)


def run_data_ingestion_task(payload: AgentIngestionRequest, db: Session) -> dict:
    agent = DataIngestionAgent()
    task_payload = build_ingestion_payload(
        source_type=payload.source_type,
        csv_path=payload.csv_path,
        api_url=payload.api_url,
        api_format=payload.api_format,
        records=payload.records,
        allow_partial=payload.allow_partial,
        max_retries=payload.max_retries,
    )
    task = AgentTask(
        name="data_ingestion",
        description="Ingest external consumption records into AHIMP",
        payload=task_payload,
    )
    result = agent.run(task=task, context={"db": db})
    return result


def run_supply_chain_task(payload: SupplyChainRequest, db: Session, auto_purchase: bool) -> dict:
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


def _run_data_ingestion_background(job_id: str, payload: AgentIngestionRequest) -> None:
    _update_job(job_id, status="running", started_at=datetime.now(tz=timezone.utc).isoformat())
    _log_agent_event(
        agent_name="data-ingestion-agent",
        task_description="data_ingestion",
        status="running",
        metadata={"job_id": job_id},
    )
    db = SessionLocal()
    try:
        result = run_data_ingestion_task(payload, db)
        status = "succeeded" if result.get("ok") else "failed"
        _update_job(
            job_id,
            status=status,
            completed_at=datetime.now(tz=timezone.utc).isoformat(),
            result=result,
        )
        _log_agent_event(
            agent_name="data-ingestion-agent",
            task_description="data_ingestion",
            status=status,
            result=result,
            metadata={"job_id": job_id},
        )
    except Exception as exc:
        _update_job(
            job_id,
            status="failed",
            completed_at=datetime.now(tz=timezone.utc).isoformat(),
            error=str(exc),
        )
        _log_agent_event(
            agent_name="data-ingestion-agent",
            task_description="data_ingestion",
            status="failed",
            error=str(exc),
            metadata={"job_id": job_id},
        )
    finally:
        db.close()


@router.post("/agents/data-ingestion")
def trigger_data_ingestion(
    payload: AgentIngestionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: None = Depends(require_agent_auth),
    __: None = Depends(enforce_rate_limit),
):
    if payload.source_type == "csv" and not payload.csv_path:
        raise HTTPException(status_code=400, detail="csv_path is required for source_type=csv")
    if payload.source_type == "api" and not payload.api_url:
        raise HTTPException(status_code=400, detail="api_url is required for source_type=api")
    if payload.source_type == "records" and not payload.records:
        raise HTTPException(status_code=400, detail="records are required for source_type=records")

    if payload.run_async:
        job_id = str(uuid4())
        with _JOBS_LOCK:
            _JOBS[job_id] = {
                "job_id": job_id,
                "status": "queued",
                "created_at": datetime.now(tz=timezone.utc).isoformat(),
                "payload": payload.model_dump(exclude={"records"}),
            }
        _log_agent_event(
            agent_name="data-ingestion-agent",
            task_description="data_ingestion",
            status="queued",
            metadata={"job_id": job_id},
        )
        background_tasks.add_task(_run_data_ingestion_background, job_id, payload)
        return {
            "job_id": job_id,
            "status": "queued",
            "status_endpoint": f"/api/agents/data-ingestion/status/{job_id}",
        }

    result = run_data_ingestion_task(payload, db)
    if not result.get("ok"):
        _log_agent_event(
            agent_name="data-ingestion-agent",
            task_description="data_ingestion",
            status="failed",
            result=result,
        )
        raise HTTPException(status_code=500, detail=result.get("error", "Ingestion failed"))

    _log_agent_event(
        agent_name="data-ingestion-agent",
        task_description="data_ingestion",
        status="succeeded",
        result=result,
    )
    return {
        "job_id": None,
        "status": "completed",
        "result": result,
    }


@router.get("/agents/data-ingestion/status/{job_id}")
def data_ingestion_status(
    job_id: str,
    _: None = Depends(require_agent_auth),
    __: None = Depends(enforce_rate_limit),
):
    with _JOBS_LOCK:
        payload = _JOBS.get(job_id)
    if not payload:
        raise HTTPException(status_code=404, detail="Job not found")
    return payload


@router.get("/agents/supply-chain/at-risk")
def get_supply_chain_at_risk(
    risk_threshold: float = Query(0.7, ge=0.0, le=1.0),
    max_items: int = Query(10, ge=1, le=200),
    cadence_hours: int = Query(1, ge=1, le=24),
    db: Session = Depends(get_db),
    _: None = Depends(require_agent_auth),
    __: None = Depends(enforce_rate_limit),
):
    payload = SupplyChainRequest(
        risk_threshold=risk_threshold,
        max_items=max_items,
        cadence_hours=cadence_hours,
    )
    result = run_supply_chain_task(payload, db, auto_purchase=False)
    if not result.get("ok"):
        _log_agent_event(
            agent_name="supply-chain-agent",
            task_description="supply_chain_at_risk",
            status="failed",
            result=result,
        )
        raise HTTPException(status_code=500, detail=result.get("error", "Supply chain analysis failed"))

    _log_agent_event(
        agent_name="supply-chain-agent",
        task_description="supply_chain_at_risk",
        status="succeeded",
        result=result,
    )
    return result


@router.post("/agents/supply-chain/optimize")
def optimize_supply_chain(
    payload: SupplyChainRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_agent_auth),
    __: None = Depends(enforce_rate_limit),
):
    result = run_supply_chain_task(payload, db, auto_purchase=True)
    if not result.get("ok"):
        _log_agent_event(
            agent_name="supply-chain-agent",
            task_description="supply_chain_optimize",
            status="failed",
            result=result,
        )
        raise HTTPException(status_code=500, detail=result.get("error", "Supply chain optimization failed"))

    _log_agent_event(
        agent_name="supply-chain-agent",
        task_description="supply_chain_optimize",
        status="succeeded",
        result=result,
    )
    return result


@router.get("/agents/logs")
def get_agent_logs(
    db: Session = Depends(get_db),
    agent_name: str | None = Query(default=None, max_length=100),
    status: str | None = Query(default=None, max_length=40),
    level: str | None = Query(default=None, max_length=10),
    q: str | None = Query(default=None, max_length=255),
    export: str = Query(default="json", pattern="^(json|csv)$"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: None = Depends(require_agent_auth),
    __: None = Depends(enforce_rate_limit),
):
    payload = list_agent_logs(
        db,
        agent_name=agent_name,
        status=status,
        level=level,
        search=q,
        limit=limit,
        offset=offset,
    )

    if export == "csv":
        buffer = io.StringIO()
        writer = csv.DictWriter(
            buffer,
            fieldnames=[
                "log_id",
                "agent_name",
                "task_description",
                "status",
                "level",
                "created_at",
                "completed_at",
                "result",
                "errors",
            ],
        )
        writer.writeheader()
        for row in payload["records"]:
            writer.writerow(row)
        return PlainTextResponse(buffer.getvalue(), media_type="text/csv")

    return payload


@router.get("/agents/dashboard")
def get_agents_dashboard(
    db: Session = Depends(get_db),
    _: None = Depends(require_agent_auth),
    __: None = Depends(enforce_rate_limit),
):
    with _JOBS_LOCK:
        jobs = list(_JOBS.values())

    job_counts = {
        "total": len(jobs),
        "queued": sum(1 for row in jobs if row.get("status") == "queued"),
        "running": sum(1 for row in jobs if row.get("status") == "running"),
        "succeeded": sum(1 for row in jobs if row.get("status") == "succeeded"),
        "failed": sum(1 for row in jobs if row.get("status") == "failed"),
    }

    pending_records = list_audit_records(db, status="PENDING", limit=1000, offset=0)
    log_summary = summarize_agent_logs(db, preview_limit=20)

    return {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "jobs": job_counts,
        "log_counts": log_summary["counts"],
        "audit": {
            "pending_count": len(pending_records),
        },
        "logs_preview": log_summary["preview"],
    }


@router.get("/admin/ingestion-audit")
def get_ingestion_audit_records(
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    _: None = Depends(require_agent_auth),
    __: None = Depends(enforce_rate_limit),
):
    records = list_audit_records(
        db,
        status=status,
        limit=limit,
        offset=offset,
    )
    return {
        "count": len(records),
        "records": records,
    }


@router.post("/admin/ingestion-audit/{audit_id}/review")
def review_ingestion_audit(
    audit_id: int,
    payload: AuditReviewRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_agent_auth),
    __: None = Depends(enforce_rate_limit),
):
    try:
        result = review_audit_record(
            db,
            audit_id=audit_id,
            action=payload.action,
            reviewed_by=payload.reviewed_by,
            comment=payload.comment,
            create_consumption_record=payload.create_consumption_record,
        )
        _log_agent_event(
            agent_name="data-ingestion-agent",
            task_description="ingestion_audit_review",
            status="succeeded",
            result=result,
        )
        return result
    except ValueError as exc:
        message = str(exc)
        _log_agent_event(
            agent_name="data-ingestion-agent",
            task_description="ingestion_audit_review",
            status="failed",
            error=message,
        )
        if "not found" in message.lower():
            raise HTTPException(status_code=404, detail=message) from exc
        raise HTTPException(status_code=400, detail=message) from exc
