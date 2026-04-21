"""FastAPI routes for supply chain agent operations."""
from __future__ import annotations

import csv
from collections import deque
from datetime import datetime, timezone
import io
import json
import os
from threading import Lock
import time
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from agents.config import AgentTask
from agents.supply_chain_agent import SupplyChainAgent, build_supply_chain_payload
from database.agent_logs import create_agent_log, list_agent_logs
from database.escalations import list_escalations, resolve_escalation
from database.db import get_db

router = APIRouter()

AUDIT_POLICY = {
    "append_only": True,
    "mutable": False,
    "allowed_operations": ["read", "create"],
    "disallowed_operations": ["update", "delete"],
}

_API_KEY_ENV = "AGENTS_API_KEY"
_RATE_LIMIT_REQUESTS = 100
_RATE_LIMIT_WINDOW_SEC = 60

_RATE_LIMIT_LOCK = Lock()
_RATE_LIMIT_BUCKETS: dict[str, deque[float]] = {}


class SupplyChainRequest(BaseModel):
    risk_threshold: float = Field(0.7, ge=0.0, le=1.0)
    max_items: int = Field(10, ge=1, le=200)
    cadence_hours: int = Field(1, ge=1, le=24)
    supplier_overrides: dict[int, list[dict]] = Field(default_factory=dict)
    critical_item_ids: list[int] = Field(default_factory=list)
    critical_categories: list[str] = Field(default_factory=list)
    search_location: str | None = Field(None, max_length=120)
    max_distance_km: float = Field(50.0, ge=1.0, le=1000.0)
    min_supplier_reliability: float = Field(0.60, ge=0.0, le=1.0)


class SupplyChainSupplierSearchRequest(BaseModel):
    medicine_name: str = Field(..., min_length=1, max_length=200)
    quantity: int = Field(..., ge=1, le=1000000)
    location: str | None = Field(None, max_length=120)
    max_distance_km: float = Field(50.0, ge=1.0, le=1000.0)
    min_reliability: float = Field(0.60, ge=0.0, le=1.0)
    supplier_overrides: list[dict] = Field(default_factory=list)


class EscalationResolveRequest(BaseModel):
    action: str = Field(..., pattern="^(RESOLVED|DISMISSED)$")
    resolution_note: str = Field(..., min_length=3, max_length=1000)
    resolved_by: str = Field("system", min_length=1, max_length=120)


class SupplyChainAuditTraceQuery(BaseModel):
    status: str | None = Field(default=None, max_length=40)
    q: str | None = Field(default=None, max_length=255)
    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class SupplyChainAuditSummaryQuery(BaseModel):
    decision_type: str | None = Field(default=None, pattern="^(AUTO_ORDER|SUGGEST_HUMAN_APPROVAL|ESCALATE)$")
    medicine: str | None = Field(default=None, max_length=150)
    from_ts: str | None = None
    to_ts: str | None = None
    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


def _build_human_explanation(record: dict) -> str:
    reasoning_trace = record.get("reasoning_trace") or []
    if not reasoning_trace:
        return "No reasoning trace was captured for this decision."

    lines = []
    for step in reasoning_trace:
        kind = str(step.get("type", "step")).upper()
        item_id = step.get("item_id")
        action = step.get("action")
        reason = step.get("reason")
        lines.append(f"[{kind}] item={item_id} action={action} reason={reason}")
    return "\n".join(lines)


def _parse_iso_datetime(value: str | None, field_name: str) -> datetime | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name} datetime format") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _record_within_range(
    record: dict,
    from_ts: datetime | None,
    to_ts: datetime | None,
) -> bool:
    created_raw = record.get("created_at")
    if not created_raw:
        return from_ts is None and to_ts is None
    try:
        created = datetime.fromisoformat(str(created_raw).replace("Z", "+00:00"))
    except ValueError:
        return False
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    created = created.astimezone(timezone.utc)

    if from_ts and created < from_ts:
        return False
    if to_ts and created > to_ts:
        return False
    return True


def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


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


def _build_reasoning_trace(result_payload: dict | None) -> list[dict]:
    trace: list[dict] = []
    if not isinstance(result_payload, dict):
        return trace

    result = result_payload.get("result") if "result" in result_payload else result_payload
    if not isinstance(result, dict):
        return trace

    for idx, decision in enumerate(result.get("decisions", []), start=1):
        trace.append(
            {
                "step": idx,
                "type": "decision",
                "item_id": decision.get("item_id"),
                "action": decision.get("action"),
                "reason": decision.get("reason"),
            }
        )

    for idx, escalation in enumerate(result.get("escalations", []), start=1):
        trace.append(
            {
                "step": idx,
                "type": "escalation",
                "item_id": escalation.get("item_id"),
                "action": escalation.get("action"),
                "reason": escalation.get("reason"),
            }
        )
    return trace


def _log_supply_chain_audit(
    db: Session,
    *,
    task_description: str,
    status: str,
    tool_called: str,
    input_payload: dict,
    output_payload: dict | None = None,
    error: str | None = None,
) -> None:
    session_id = str(uuid4())
    level = "ERROR" if status in {"failed", "error"} else "INFO"

    result_payload = {
        "session_id": session_id,
        "tool_called": tool_called,
        "input_payload": input_payload,
        "output_payload": output_payload,
        "reasoning_trace": _build_reasoning_trace(output_payload),
        "timestamp": _utc_now_iso(),
    }
    error_payload = None if error is None else {"session_id": session_id, "message": error}

    try:
        create_agent_log(
            db,
            agent_name="supply-chain-agent",
            task_description=task_description,
            status=status,
            level=level,
            result=result_payload,
            errors=error_payload,
            completed_at=datetime.now(tz=timezone.utc),
        )
    except Exception:
        # Audit persistence should not block API responses.
        return


def _run_supply_chain_task(payload: SupplyChainRequest, db: Session, auto_purchase: bool) -> dict:
    agent = SupplyChainAgent()
    task_payload = build_supply_chain_payload(
        risk_threshold=payload.risk_threshold,
        max_items=payload.max_items,
        auto_purchase=auto_purchase,
        cadence_hours=payload.cadence_hours,
        supplier_overrides=payload.supplier_overrides,
        critical_item_ids=payload.critical_item_ids,
        critical_categories=payload.critical_categories,
        search_location=payload.search_location,
        max_distance_km=payload.max_distance_km,
        min_supplier_reliability=payload.min_supplier_reliability,
    )
    task = AgentTask(
        name="supply_chain_monitor",
        description="Monitor stockout risk and coordinate supplier purchasing",
        payload=task_payload,
    )
    return agent.run(task=task, context={"db": db})


def _extract_supply_chain_trace_row(row: dict) -> dict:
    result_payload = row.get("result") or {}
    return {
        "log_id": row.get("log_id"),
        "created_at": row.get("created_at"),
        "task_description": row.get("task_description"),
        "status": row.get("status"),
        "session_id": result_payload.get("session_id"),
        "tool_called": result_payload.get("tool_called"),
        "input_payload": result_payload.get("input_payload"),
        "output_payload": result_payload.get("output_payload"),
        "reasoning_trace": result_payload.get("reasoning_trace") or [],
        "timestamp": result_payload.get("timestamp"),
        "errors": row.get("errors"),
    }


def _extract_decision_rows(records: list[dict]) -> list[dict]:
    flattened: list[dict] = []
    for record in records:
        output_payload = record.get("output_payload") or {}
        result_payload = output_payload.get("result", output_payload) if isinstance(output_payload, dict) else {}

        for decision in (result_payload.get("decisions", []) if isinstance(result_payload, dict) else []):
            flattened.append(
                {
                    "log_id": record.get("log_id"),
                    "session_id": record.get("session_id"),
                    "created_at": record.get("created_at"),
                    "task_description": record.get("task_description"),
                    "decision_type": decision.get("action"),
                    "item_id": decision.get("item_id"),
                    "medicine": decision.get("item_name"),
                    "reason": decision.get("reason"),
                    "risk_prob": decision.get("risk_prob"),
                }
            )

        for escalation in (result_payload.get("escalations", []) if isinstance(result_payload, dict) else []):
            flattened.append(
                {
                    "log_id": record.get("log_id"),
                    "session_id": record.get("session_id"),
                    "created_at": record.get("created_at"),
                    "task_description": record.get("task_description"),
                    "decision_type": "ESCALATE",
                    "item_id": escalation.get("item_id"),
                    "medicine": escalation.get("item_name"),
                    "reason": escalation.get("reason"),
                    "risk_prob": escalation.get("risk_prob"),
                }
            )
    return flattened


def _search_suppliers(payload: SupplyChainSupplierSearchRequest, db: Session) -> dict:
    agent = SupplyChainAgent()
    suppliers = agent.search_suppliers_tool(
        db,
        medicine_name=payload.medicine_name,
        quantity=payload.quantity,
        location=payload.location,
        max_distance_km=payload.max_distance_km,
        min_reliability=payload.min_reliability,
        supplier_overrides=payload.supplier_overrides,
    )
    return {
        "ok": True,
        "agent": "supply-chain-agent",
        "result": {
            "query": {
                "medicine_name": payload.medicine_name,
                "quantity": payload.quantity,
                "location": payload.location,
                "max_distance_km": payload.max_distance_km,
                "min_reliability": payload.min_reliability,
            },
            "suppliers": suppliers,
        },
    }


@router.post("/agents/supply-chain/at-risk")
def supply_chain_at_risk(
    payload: SupplyChainRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_agent_auth),
    __: None = Depends(enforce_rate_limit),
):
    result = _run_supply_chain_task(payload, db, auto_purchase=False)
    if not result.get("ok"):
        _log_supply_chain_audit(
            db,
            task_description="supply_chain_at_risk",
            status="failed",
            tool_called="run_supply_chain_task",
            input_payload=payload.model_dump(),
            output_payload=result,
            error=str(result.get("error", "Supply chain analysis failed")),
        )
        raise HTTPException(status_code=500, detail=result.get("error", "Supply chain analysis failed"))
    _log_supply_chain_audit(
        db,
        task_description="supply_chain_at_risk",
        status="succeeded",
        tool_called="run_supply_chain_task",
        input_payload=payload.model_dump(),
        output_payload=result,
    )
    return result


@router.post("/agents/supply-chain/auto-purchase")
def supply_chain_auto_purchase(
    payload: SupplyChainRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_agent_auth),
    __: None = Depends(enforce_rate_limit),
):
    result = _run_supply_chain_task(payload, db, auto_purchase=True)
    if not result.get("ok"):
        _log_supply_chain_audit(
            db,
            task_description="supply_chain_auto_purchase",
            status="failed",
            tool_called="run_supply_chain_task",
            input_payload=payload.model_dump(),
            output_payload=result,
            error=str(result.get("error", "Auto purchase failed")),
        )
        raise HTTPException(status_code=500, detail=result.get("error", "Auto purchase failed"))
    _log_supply_chain_audit(
        db,
        task_description="supply_chain_auto_purchase",
        status="succeeded",
        tool_called="run_supply_chain_task",
        input_payload=payload.model_dump(),
        output_payload=result,
    )
    return result


@router.post("/agents/supply-chain/search-suppliers")
def search_suppliers(
    payload: SupplyChainSupplierSearchRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_agent_auth),
    __: None = Depends(enforce_rate_limit),
):
    try:
        result = _search_suppliers(payload, db)
        _log_supply_chain_audit(
            db,
            task_description="supply_chain_search_suppliers",
            status="succeeded",
            tool_called="search_suppliers_tool",
            input_payload=payload.model_dump(),
            output_payload=result,
        )
        return result
    except ValueError as exc:
        _log_supply_chain_audit(
            db,
            task_description="supply_chain_search_suppliers",
            status="failed",
            tool_called="search_suppliers_tool",
            input_payload=payload.model_dump(),
            error=str(exc),
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        _log_supply_chain_audit(
            db,
            task_description="supply_chain_search_suppliers",
            status="failed",
            tool_called="search_suppliers_tool",
            input_payload=payload.model_dump(),
            error=str(exc),
        )
        raise HTTPException(status_code=500, detail=f"Supplier search failed: {exc}") from exc


@router.get("/agents/supply-chain/escalations")
def get_supply_chain_escalations(
    status: str = "OPEN",
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    _: None = Depends(require_agent_auth),
    __: None = Depends(enforce_rate_limit),
):
    normalized_status = str(status or "OPEN").upper()
    if normalized_status not in {"OPEN", "RESOLVED", "DISMISSED", "ALL"}:
        raise HTTPException(status_code=400, detail="status must be OPEN, RESOLVED, DISMISSED, or ALL")
    result = list_escalations(
        db,
        status=normalized_status,
        limit=max(1, min(int(limit), 500)),
        offset=max(0, int(offset)),
    )
    _log_supply_chain_audit(
        db,
        task_description="supply_chain_escalations_list",
        status="succeeded",
        tool_called="list_escalations",
        input_payload={"status": normalized_status, "limit": limit, "offset": offset},
        output_payload=result,
    )
    return result


@router.post("/agents/supply-chain/escalations/{escalation_id}/resolve")
def resolve_supply_chain_escalation(
    escalation_id: int,
    payload: EscalationResolveRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_agent_auth),
    __: None = Depends(enforce_rate_limit),
):
    try:
        result = resolve_escalation(
            db,
            escalation_id=int(escalation_id),
            action=payload.action,
            resolution_note=payload.resolution_note,
            resolved_by=payload.resolved_by,
        )
        _log_supply_chain_audit(
            db,
            task_description="supply_chain_escalation_resolve",
            status="succeeded",
            tool_called="resolve_escalation",
            input_payload={"escalation_id": escalation_id, **payload.model_dump()},
            output_payload=result,
        )
        return result
    except ValueError as exc:
        message = str(exc)
        _log_supply_chain_audit(
            db,
            task_description="supply_chain_escalation_resolve",
            status="failed",
            tool_called="resolve_escalation",
            input_payload={"escalation_id": escalation_id, **payload.model_dump()},
            error=message,
        )
        if "not found" in message.lower():
            raise HTTPException(status_code=404, detail=message) from exc
        raise HTTPException(status_code=400, detail=message) from exc


@router.get("/agents/supply-chain/audit-traces")
def get_supply_chain_audit_traces(
    status: str | None = None,
    q: str | None = None,
    from_ts: str | None = None,
    to_ts: str | None = None,
    export: str = "json",
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    _: None = Depends(require_agent_auth),
    __: None = Depends(enforce_rate_limit),
):
    query = SupplyChainAuditTraceQuery(
        status=status,
        q=q,
        limit=limit,
        offset=offset,
    )
    logs = list_agent_logs(
        db,
        agent_name="supply-chain-agent",
        status=query.status,
        search=query.q,
        limit=query.limit,
        offset=query.offset,
    )
    start_dt = _parse_iso_datetime(from_ts, "from_ts")
    end_dt = _parse_iso_datetime(to_ts, "to_ts")
    if start_dt and end_dt and start_dt > end_dt:
        raise HTTPException(status_code=400, detail="from_ts must be less than or equal to to_ts")

    records = [_extract_supply_chain_trace_row(row) for row in logs.get("records", [])]
    records = [row for row in records if _record_within_range(row, start_dt, end_dt)]
    if export == "csv":
        buffer = io.StringIO()
        writer = csv.DictWriter(
            buffer,
            fieldnames=[
                "log_id",
                "created_at",
                "task_description",
                "status",
                "session_id",
                "tool_called",
                "timestamp",
                "input_payload",
                "output_payload",
                "reasoning_trace",
                "errors",
            ],
        )
        writer.writeheader()
        for row in records:
            writer.writerow(
                {
                    **row,
                    "input_payload": json.dumps(row.get("input_payload", {}), default=str),
                    "output_payload": json.dumps(row.get("output_payload", {}), default=str),
                    "reasoning_trace": json.dumps(row.get("reasoning_trace", []), default=str),
                    "errors": json.dumps(row.get("errors"), default=str),
                }
            )
        return PlainTextResponse(buffer.getvalue(), media_type="text/csv")

    if export != "json":
        raise HTTPException(status_code=400, detail="export must be json or csv")

    return {
        "audit_policy": AUDIT_POLICY,
        "count": logs.get("count", len(records)),
        "records": records,
    }


@router.get("/agents/supply-chain/audit-traces/explain")
def explain_supply_chain_audit_trace(
    session_id: str | None = None,
    log_id: int | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_agent_auth),
    __: None = Depends(enforce_rate_limit),
):
    if not session_id and log_id is None:
        raise HTTPException(status_code=400, detail="Provide either session_id or log_id")

    logs = list_agent_logs(
        db,
        agent_name="supply-chain-agent",
        limit=500,
        offset=0,
    )
    records = [_extract_supply_chain_trace_row(row) for row in logs.get("records", [])]

    matched = None
    if session_id:
        for row in records:
            if row.get("session_id") == session_id:
                matched = row
                break
    elif log_id is not None:
        for row in records:
            if int(row.get("log_id", 0) or 0) == int(log_id):
                matched = row
                break

    if matched is None:
        raise HTTPException(status_code=404, detail="Audit trace not found")

    return {
        "audit_policy": AUDIT_POLICY,
        "log_id": matched.get("log_id"),
        "session_id": matched.get("session_id"),
        "task_description": matched.get("task_description"),
        "status": matched.get("status"),
        "tool_called": matched.get("tool_called"),
        "input_payload": matched.get("input_payload"),
        "output_payload": matched.get("output_payload"),
        "reasoning_trace": matched.get("reasoning_trace") or [],
        "human_explanation": _build_human_explanation(matched),
        "timestamp": matched.get("timestamp"),
    }


@router.get("/agents/supply-chain/audit-summary")
def get_supply_chain_audit_summary(
    decision_type: str | None = None,
    medicine: str | None = None,
    from_ts: str | None = None,
    to_ts: str | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    _: None = Depends(require_agent_auth),
    __: None = Depends(enforce_rate_limit),
):
    query = SupplyChainAuditSummaryQuery(
        decision_type=decision_type,
        medicine=medicine,
        from_ts=from_ts,
        to_ts=to_ts,
        limit=limit,
        offset=offset,
    )

    start_dt = _parse_iso_datetime(query.from_ts, "from_ts")
    end_dt = _parse_iso_datetime(query.to_ts, "to_ts")
    if start_dt and end_dt and start_dt > end_dt:
        raise HTTPException(status_code=400, detail="from_ts must be less than or equal to to_ts")

    logs = list_agent_logs(
        db,
        agent_name="supply-chain-agent",
        limit=500,
        offset=0,
    )
    records = [_extract_supply_chain_trace_row(row) for row in logs.get("records", [])]
    records = [row for row in records if _record_within_range(row, start_dt, end_dt)]

    decisions = _extract_decision_rows(records)
    if query.decision_type:
        decisions = [row for row in decisions if str(row.get("decision_type")) == query.decision_type]
    if query.medicine:
        needle = query.medicine.strip().lower()
        decisions = [row for row in decisions if needle in str(row.get("medicine", "")).lower()]

    total = len(decisions)
    decisions = decisions[query.offset : query.offset + query.limit]

    counts_by_type: dict[str, int] = {}
    for row in _extract_decision_rows(records):
        key = str(row.get("decision_type", "UNKNOWN"))
        counts_by_type[key] = counts_by_type.get(key, 0) + 1

    return {
        "audit_policy": AUDIT_POLICY,
        "count": total,
        "counts_by_type": counts_by_type,
        "records": decisions,
    }
