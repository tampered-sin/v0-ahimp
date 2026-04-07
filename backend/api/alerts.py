"""FastAPI route: GET /api/alerts/recent"""
from __future__ import annotations

from fastapi import APIRouter, Query

from services.notifications import get_recent_alerts

router = APIRouter()


@router.get("/alerts/recent")
def recent_alerts(
    limit: int = Query(default=50, ge=1, le=500),
    severity: str | None = Query(default=None, description="Optional severity filter, e.g. RED/YELLOW"),
):
    alerts = get_recent_alerts(limit=limit, severity=severity)
    return {
        "count": len(alerts),
        "alerts": alerts,
    }
