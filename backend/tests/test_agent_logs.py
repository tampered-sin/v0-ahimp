from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.agent_logs import archive_old_logs, create_agent_log, list_agent_logs, summarize_agent_logs
from database.db import Base


def _make_db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return SessionLocal()


def test_create_and_query_agent_logs_with_search():
    db = _make_db_session()

    create_agent_log(
        db,
        agent_name="data-ingestion-agent",
        task_description="data_ingestion",
        status="succeeded",
        level="INFO",
        result={"inserted": 2},
    )
    create_agent_log(
        db,
        agent_name="supply-chain-agent",
        task_description="supply_chain_optimize",
        status="failed",
        level="ERROR",
        errors={"message": "supplier API timeout"},
    )

    all_logs = list_agent_logs(db)
    assert all_logs["count"] == 2

    filtered = list_agent_logs(db, agent_name="supply-chain-agent", status="failed")
    assert filtered["count"] == 1
    assert filtered["records"][0]["agent_name"] == "supply-chain-agent"

    searched = list_agent_logs(db, search="optimize")
    assert searched["count"] == 1
    assert searched["records"][0]["task_description"] == "supply_chain_optimize"


def test_archive_old_logs_and_summary():
    db = _make_db_session()

    old_created_at = datetime.now(tz=timezone.utc) - timedelta(days=120)
    create_agent_log(
        db,
        agent_name="data-ingestion-agent",
        task_description="old_job",
        status="failed",
        level="ERROR",
        errors={"message": "old"},
        created_at=old_created_at,
        completed_at=old_created_at,
    )
    create_agent_log(
        db,
        agent_name="data-ingestion-agent",
        task_description="new_job",
        status="succeeded",
        level="INFO",
    )

    # Old rows are archived on write, so only recent logs should remain already.
    pre_archive = list_agent_logs(db)
    assert pre_archive["count"] == 1

    deleted = archive_old_logs(db, retention_days=90)
    assert deleted == 0

    remaining = list_agent_logs(db)
    assert remaining["count"] == 1
    assert remaining["records"][0]["task_description"] == "new_job"

    summary = summarize_agent_logs(db)
    assert summary["counts"]["succeeded"] == 1
