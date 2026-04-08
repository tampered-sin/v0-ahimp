"""Agent execution logging persistence and query helpers."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import String, cast, func, or_
from sqlalchemy.orm import Session

from database.models import AgentLog

_DEFAULT_RETENTION_DAYS = 90


def _utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _serialize(row: AgentLog) -> dict[str, Any]:
    return {
        "log_id": int(row.log_id),
        "agent_name": row.agent_name,
        "task_description": row.task_description,
        "status": row.status,
        "level": row.level,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "result": row.result,
        "errors": row.errors,
    }


def archive_old_logs(db: Session, retention_days: int = _DEFAULT_RETENTION_DAYS) -> int:
    cutoff = _utc_now() - timedelta(days=retention_days)
    deleted = (
        db.query(AgentLog)
        .filter(AgentLog.created_at < cutoff)
        .delete(synchronize_session=False)
    )
    return int(deleted)


def create_agent_log(
    db: Session,
    *,
    agent_name: str,
    task_description: str,
    status: str,
    level: str = "INFO",
    result: dict[str, Any] | None = None,
    errors: dict[str, Any] | None = None,
    created_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> dict[str, Any]:
    row = AgentLog(
        agent_name=agent_name,
        task_description=task_description,
        status=status,
        level=level,
        created_at=created_at or _utc_now(),
        completed_at=completed_at,
        result=result,
        errors=errors,
    )
    db.add(row)
    archive_old_logs(db)
    db.commit()
    db.refresh(row)
    return _serialize(row)


def list_agent_logs(
    db: Session,
    *,
    agent_name: str | None = None,
    status: str | None = None,
    level: str | None = None,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    query = db.query(AgentLog)

    if agent_name:
        query = query.filter(AgentLog.agent_name == agent_name)
    if status:
        query = query.filter(AgentLog.status == status)
    if level:
        query = query.filter(AgentLog.level == level)
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                AgentLog.task_description.ilike(pattern),
                cast(AgentLog.errors, String).ilike(pattern),
            )
        )

    total = query.count()
    records = (
        query.order_by(AgentLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "count": total,
        "records": [_serialize(row) for row in records],
    }


def summarize_agent_logs(db: Session, preview_limit: int = 20) -> dict[str, Any]:
    grouped = (
        db.query(AgentLog.status, func.count(AgentLog.log_id))
        .group_by(AgentLog.status)
        .all()
    )
    counts = {str(status): int(count) for status, count in grouped}

    preview_rows = (
        db.query(AgentLog)
        .order_by(AgentLog.created_at.desc())
        .limit(preview_limit)
        .all()
    )

    return {
        "counts": counts,
        "preview": [_serialize(row) for row in preview_rows],
    }
