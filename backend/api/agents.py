"""FastAPI routes for AI agent operations."""
from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from agents.config import AgentTask
from agents.data_ingestion_agent import DataIngestionAgent, build_ingestion_payload
from database.data_validation import list_audit_records, review_audit_record
from database.db import SessionLocal, get_db

router = APIRouter()

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


def _run_data_ingestion_background(job_id: str, payload: AgentIngestionRequest) -> None:
    _update_job(job_id, status="running", started_at=datetime.now(tz=timezone.utc).isoformat())
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
    except Exception as exc:
        _update_job(
            job_id,
            status="failed",
            completed_at=datetime.now(tz=timezone.utc).isoformat(),
            error=str(exc),
        )
    finally:
        db.close()


@router.post("/agents/data-ingestion")
def trigger_data_ingestion(
    payload: AgentIngestionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
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
        background_tasks.add_task(_run_data_ingestion_background, job_id, payload)
        return {
            "job_id": job_id,
            "status": "queued",
            "status_endpoint": f"/api/agents/data-ingestion/status/{job_id}",
        }

    result = run_data_ingestion_task(payload, db)
    if not result.get("ok"):
        raise HTTPException(status_code=500, detail=result.get("error", "Ingestion failed"))
    return {
        "job_id": None,
        "status": "completed",
        "result": result,
    }


@router.get("/agents/data-ingestion/status/{job_id}")
def data_ingestion_status(job_id: str):
    with _JOBS_LOCK:
        payload = _JOBS.get(job_id)
    if not payload:
        raise HTTPException(status_code=404, detail="Job not found")
    return payload


@router.get("/admin/ingestion-audit")
def get_ingestion_audit_records(
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
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
        return result
    except ValueError as exc:
        message = str(exc)
        if "not found" in message.lower():
            raise HTTPException(status_code=404, detail=message) from exc
        raise HTTPException(status_code=400, detail=message) from exc
