from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import database.data_validation as data_validation
from database.db import Base
from database.models import ConsumptionRecord, Department, Item


def _make_db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return SessionLocal()


def _seed_refs(db):
    db.add(Department(department_id=1, department_name="Pharmacy", location="A"))
    db.add(Department(department_id=2, department_name="ER", location="B"))
    db.add(Item(item_id=1, item_name="Bandage", category="medical", unit_type="box"))
    db.add(Item(item_id=2, item_name="Syringe", category="medical", unit_type="box"))
    db.commit()


def test_validate_candidate_records_rules_and_duplicates():
    db = _make_db_session()
    _seed_refs(db)

    today = datetime.now(tz=timezone.utc).date()
    existing_date = today - timedelta(days=1)
    db.add(
        ConsumptionRecord(
            item_id=1,
            department_id=1,
            quantity_used=9,
            usage_date=existing_date,
            patient_type="general",
        )
    )
    db.commit()

    records = [
        {
            "item_id": 2,
            "department_id": 1,
            "quantity_used": 12,
            "usage_date": str(today),
            "patient_type": "general",
        },
        {
            "item_id": 999,
            "department_id": 1,
            "quantity_used": 12,
            "usage_date": str(today),
        },
        {
            "item_id": 2,
            "department_id": 999,
            "quantity_used": 12,
            "usage_date": str(today),
        },
        {
            "item_id": 2,
            "department_id": 1,
            "quantity_used": -3,
            "usage_date": str(today),
        },
        {
            "item_id": 2,
            "department_id": 1,
            "quantity_used": 7,
            "usage_date": str(today - timedelta(days=120)),
        },
        {
            "item_id": 1,
            "department_id": 1,
            "quantity_used": 18,
            "usage_date": str(existing_date),
        },
        {
            "item_id": 2,
            "department_id": 1,
            "quantity_used": 12,
            "usage_date": str(today),
        },
    ]

    result = data_validation.validate_candidate_records(db, records)

    assert len(result["valid_records"]) == 1
    assert len(result["invalid_rows"]) == 6

    all_errors = {err for row in result["invalid_rows"] for err in row["errors"]}
    assert "invalid_item_id" in all_errors
    assert "invalid_department_id" in all_errors
    assert "invalid_quantity_range" in all_errors
    assert "invalid_usage_date_range" in all_errors
    assert "duplicate_in_database" in all_errors
    assert "duplicate_in_payload" in all_errors


def test_quarantine_list_and_review_workflow(monkeypatch):
    db = _make_db_session()
    _seed_refs(db)

    monkeypatch.setattr(
        data_validation,
        "send_anomaly_alert",
        lambda subject, body, recipients=None, severity="RED": {
            "sent": True,
            "channels": ["log"],
            "severity": severity,
        },
    )

    usage_date = datetime.now(tz=timezone.utc).date()
    quarantine = data_validation.record_quarantine_issues(
        db,
        invalid_rows=[
            {
                "errors": ["invalid_item_id"],
                "row": {
                    "item_id": 99,
                    "department_id": 1,
                    "quantity_used": 11,
                    "usage_date": str(usage_date),
                },
            }
        ],
        anomaly_rows=[
            {
                "item_id": 1,
                "department_id": 1,
                "quantity_used": 500,
                "usage_date": str(usage_date),
                "z_score": 3.2,
                "severity": "RED",
            }
        ],
        source="test-suite",
    )

    assert len(quarantine["created_ids"]) == 2
    assert quarantine["red"] == 2
    assert quarantine["alert"]["sent"] is True

    listed = data_validation.list_audit_records(db, status="PENDING", limit=20, offset=0)
    assert len(listed) >= 2

    review_target = quarantine["created_ids"][-1]
    reviewed = data_validation.review_audit_record(
        db,
        audit_id=review_target,
        action="approve",
        reviewed_by="qa-user",
        comment="manually approved",
        create_consumption_record=True,
    )
    assert reviewed["status"] == "APPROVED"

    inserted = (
        db.query(ConsumptionRecord)
        .filter(
            ConsumptionRecord.item_id == 1,
            ConsumptionRecord.department_id == 1,
            ConsumptionRecord.quantity_used == 500,
            ConsumptionRecord.usage_date == usage_date,
        )
        .first()
    )
    assert inserted is not None


def test_assess_records_for_quarantine_flags_anomalies(monkeypatch):
    db = _make_db_session()
    _seed_refs(db)

    monkeypatch.setattr(
        data_validation,
        "_score_anomaly",
        lambda _db, item_id, quantity_used: (3.5, "RED") if quantity_used > 100 else (0.5, None),
    )

    today = datetime.now(tz=timezone.utc).date()
    assessed = data_validation.assess_records_for_quarantine(
        db,
        records=[
            {
                "item_id": 1,
                "department_id": 1,
                "quantity_used": 18,
                "usage_date": str(today),
            },
            {
                "item_id": 2,
                "department_id": 2,
                "quantity_used": 240,
                "usage_date": str(today),
            },
        ],
    )

    assert len(assessed["valid_records"]) == 2
    assert len(assessed["invalid_rows"]) == 0
    assert len(assessed["anomaly_rows"]) == 1
    assert assessed["anomaly_rows"][0]["severity"] == "RED"
