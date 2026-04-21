from __future__ import annotations

from datetime import datetime, timezone
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.config import AgentTask
from agents.data_ingestion_agent import DataIngestionAgent, build_ingestion_payload


class _FakeDB:
    def __init__(self):
        self.single_added = []
        self.added = []
        self.commits = 0
        self._next_audit_id = 1

    def add(self, row):
        if hasattr(row, "audit_id") and getattr(row, "audit_id", None) is None:
            setattr(row, "audit_id", self._next_audit_id)
            self._next_audit_id += 1
        self.single_added.append(row)

    def flush(self):
        return None

    def add_all(self, rows):
        self.added.extend(rows)

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass


def test_validate_data_tool_with_partial_filtering():
    agent = DataIngestionAgent()
    today = datetime.now(tz=timezone.utc).date()
    old_date = today - pd.Timedelta(days=200)

    raw = pd.DataFrame(
        [
            {
                "item_id": "1",
                "department_id": "1",
                "quantity_used": "20",
                "usage_date": str(today),
                "patient_type": " General ",
            },
            {
                "item_id": "1",
                "department_id": "1",
                "quantity_used": "20",
                "usage_date": str(today),
                "patient_type": "GENERAL",
            },
            {
                "item_id": "2",
                "department_id": "1",
                "quantity_used": "-5",
                "usage_date": str(old_date),
                "patient_type": "emergency",
            },
        ]
    )

    out = agent.validate_data_tool(raw, allow_partial=True)

    assert len(out["valid_df"]) == 1
    assert len(out["invalid_rows"]) == 2
    assert out["valid_df"].iloc[0]["patient_type"] == "general"


def test_detect_anomalies_tool_flags_outliers():
    agent = DataIngestionAgent()
    baseline = [10] * 20
    quantities = baseline + [300]
    df = pd.DataFrame(
        {
            "item_id": [1] * len(quantities),
            "department_id": [1] * len(quantities),
            "quantity_used": quantities,
            "usage_date": ["2026-01-01"] * len(quantities),
            "patient_type": ["general"] * len(quantities),
            "batch_id": [None] * len(quantities),
        }
    )
    out = agent.detect_anomalies_tool(df)
    assert out["red"] >= 1 or out["yellow"] >= 1


def test_execute_records_source_success():
    agent = DataIngestionAgent()
    fake_db = _FakeDB()

    task = AgentTask(
        name="data_ingestion",
        description="test ingestion",
        payload=build_ingestion_payload(
            source_type="records",
            records=[
                {
                    "item_id": 1,
                    "department_id": 1,
                    "quantity_used": 30,
                    "usage_date": str(datetime.now(tz=timezone.utc).date()),
                    "patient_type": "general",
                }
            ],
            allow_partial=True,
        ),
    )

    out = agent.run(task=task, context={"db": fake_db})
    assert out["ok"] is True
    assert out["result"]["inserted"] == 1
    assert fake_db.commits >= 1
