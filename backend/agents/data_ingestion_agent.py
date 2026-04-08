"""Data ingestion agent for CSV/API/inline consumption records."""
from __future__ import annotations

from datetime import datetime, timezone
from io import StringIO
import time
from typing import Any
from xml.etree import ElementTree

import httpx
import pandas as pd
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from agents.config import AgentTask, BaseAgent, build_crewai_llm
from database.data_validation import record_quarantine_issues
from database.models import ConsumptionRecord
from services.notifications import send_anomaly_alert


REQUIRED_COLUMNS = ["item_id", "quantity_used", "usage_date"]
OPTIONAL_COLUMNS = ["department_id", "patient_type", "batch_id"]
DEFAULT_PATIENT_TYPE = "general"


def build_ingestion_payload(
    source_type: str,
    csv_path: str | None = None,
    api_url: str | None = None,
    api_format: str = "json",
    records: list[dict[str, Any]] | None = None,
    allow_partial: bool = True,
    max_retries: int = 2,
) -> dict[str, Any]:
    return {
        "source_type": source_type,
        "csv_path": csv_path,
        "api_url": api_url,
        "api_format": api_format,
        "records": records or [],
        "allow_partial": allow_partial,
        "max_retries": max_retries,
    }


class DataIngestionAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="data-ingestion-agent")
        self.llm = build_crewai_llm(self.settings)
        self.registry.register("read_csv_tool", self.read_csv_tool)
        self.registry.register("parse_api_tool", self.parse_api_tool)
        self.registry.register("validate_data_tool", self.validate_data_tool)
        self.registry.register("detect_anomalies_tool", self.detect_anomalies_tool)
        self.registry.register("ingest_database_tool", self.ingest_database_tool)

    def execute(self, task: AgentTask, context: dict[str, Any] | None = None) -> dict:
        context = context or {}
        db: Session | None = context.get("db")
        if db is None:
            raise ValueError("DataIngestionAgent requires a DB session in context['db']")

        payload = task.payload
        source_type = str(payload.get("source_type", "records")).strip().lower()
        allow_partial = bool(payload.get("allow_partial", True))
        max_retries = int(payload.get("max_retries", 2))

        start = time.perf_counter()
        self.logger.info("Ingestion started (source=%s)", source_type)

        source_df = self._load_source_dataframe(source_type, payload)
        self.logger.info("Source loaded: %d records", len(source_df))

        validated = self.registry.execute("validate_data_tool", source_df, allow_partial)
        valid_df: pd.DataFrame = validated["valid_df"]
        invalid_rows: list[dict[str, Any]] = validated["invalid_rows"]

        anomalies = self.registry.execute("detect_anomalies_tool", valid_df)

        quarantine = record_quarantine_issues(
            db,
            invalid_rows=invalid_rows,
            anomaly_rows=anomalies["records"],
            source="data_ingestion_agent",
        )

        inserted = 0
        if not valid_df.empty:
            inserted = int(self.registry.execute("ingest_database_tool", db, valid_df, max_retries))

        elapsed = max(1e-9, time.perf_counter() - start)
        throughput = float(len(source_df) / elapsed)

        alert = {
            "sent": False,
            "channels": [],
            "reason": "none",
        }
        if invalid_rows or anomalies["red"] > 0:
            body = (
                f"Total input: {len(source_df)}\n"
                f"Inserted: {inserted}\n"
                f"Invalid rows: {len(invalid_rows)}\n"
                f"Red anomalies: {anomalies['red']}\n"
                f"Yellow anomalies: {anomalies['yellow']}"
            )
            severity = "RED" if anomalies["red"] > 0 else "YELLOW"
            alert = send_anomaly_alert(
                subject="AHIMP Data Ingestion Alert",
                body=body,
                severity=severity,
            )

        self.logger.info(
            "Ingestion finished (inserted=%d invalid=%d red=%d yellow=%d throughput=%.2f rec/s)",
            inserted,
            len(invalid_rows),
            anomalies["red"],
            anomalies["yellow"],
            throughput,
        )

        return {
            "source_type": source_type,
            "input_records": int(len(source_df)),
            "inserted": inserted,
            "llm_provider": self.settings.crew_llm_provider,
            "llm_model": self.settings.ollama_model,
            "llm_ready": self.llm is not None,
            "invalid_count": int(len(invalid_rows)),
            "invalid_rows": invalid_rows[:100],
            "anomalies": anomalies,
            "quarantine": quarantine,
            "throughput_records_per_sec": round(throughput, 2),
            "allow_partial": allow_partial,
            "alert": alert,
        }

    def _load_source_dataframe(self, source_type: str, payload: dict[str, Any]) -> pd.DataFrame:
        if source_type == "csv":
            csv_path = payload.get("csv_path")
            if not csv_path:
                raise ValueError("csv_path is required for source_type=csv")
            return self.registry.execute("read_csv_tool", str(csv_path))

        if source_type == "api":
            api_url = payload.get("api_url")
            if not api_url:
                raise ValueError("api_url is required for source_type=api")
            api_format = str(payload.get("api_format", "json")).lower()
            return self.registry.execute("parse_api_tool", str(api_url), api_format)

        if source_type == "records":
            records = payload.get("records") or []
            if not isinstance(records, list):
                raise ValueError("records must be a list")
            return pd.DataFrame(records)

        raise ValueError(f"Unsupported source_type: {source_type}")

    def read_csv_tool(self, csv_path: str) -> pd.DataFrame:
        df = pd.read_csv(csv_path)
        return df

    def parse_api_tool(self, api_url: str, api_format: str = "json") -> pd.DataFrame:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(api_url)
            resp.raise_for_status()

        normalized = api_format.strip().lower()
        if normalized == "json":
            payload = resp.json()
            if isinstance(payload, dict):
                if "records" in payload and isinstance(payload["records"], list):
                    return pd.DataFrame(payload["records"])
                return pd.DataFrame([payload])
            if isinstance(payload, list):
                return pd.DataFrame(payload)
            raise ValueError("Unsupported JSON payload shape")

        if normalized == "xml":
            root = ElementTree.fromstring(resp.text)
            rows: list[dict[str, Any]] = []
            for record in root.findall(".//record"):
                row = {child.tag: child.text for child in list(record)}
                rows.append(row)
            if not rows:
                # fallback: treat top-level elements as one record
                row = {child.tag: child.text for child in list(root)}
                if row:
                    rows.append(row)
            return pd.DataFrame(rows)

        raise ValueError(f"Unsupported api_format: {api_format}")

    def validate_data_tool(self, raw_df: pd.DataFrame, allow_partial: bool = True) -> dict[str, Any]:
        if raw_df.empty:
            return {
                "valid_df": raw_df.copy(),
                "invalid_rows": [],
            }

        df = raw_df.copy()
        df.columns = [str(c).strip().lower() for c in df.columns]

        missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        for col in OPTIONAL_COLUMNS:
            if col not in df.columns:
                if col == "department_id":
                    df[col] = 1
                elif col == "patient_type":
                    df[col] = DEFAULT_PATIENT_TYPE
                else:
                    df[col] = None

        # Auto-fix minor issues (whitespace/case)
        df["patient_type"] = (
            df["patient_type"].astype(str).str.strip().str.lower().replace({"": DEFAULT_PATIENT_TYPE})
        )

        invalid_rows: list[dict[str, Any]] = []

        df["item_id"] = pd.to_numeric(df["item_id"], errors="coerce")
        df["department_id"] = pd.to_numeric(df["department_id"], errors="coerce")
        df["quantity_used"] = pd.to_numeric(df["quantity_used"], errors="coerce")
        df["batch_id"] = pd.to_numeric(df["batch_id"], errors="coerce")

        df["usage_date"] = pd.to_datetime(df["usage_date"], errors="coerce").dt.date

        today = datetime.now(tz=timezone.utc).date()
        min_date = today - pd.Timedelta(days=90)

        masks = {
            "missing_item_id": df["item_id"].isna(),
            "missing_department_id": df["department_id"].isna(),
            "missing_quantity": df["quantity_used"].isna(),
            "missing_usage_date": df["usage_date"].isna(),
            "invalid_quantity_range": (df["quantity_used"] < 0) | (df["quantity_used"] > 100000),
            "invalid_date_range": (df["usage_date"] < min_date) | (df["usage_date"] > today),
        }

        invalid_mask = pd.Series(False, index=df.index)
        for _, mask in masks.items():
            invalid_mask = invalid_mask | mask.fillna(False)

        duplicate_mask = df.duplicated(subset=["item_id", "usage_date", "department_id"], keep="first")
        invalid_mask = invalid_mask | duplicate_mask

        for idx in df[invalid_mask].index:
            row_errors = [name for name, mask in masks.items() if bool(mask.loc[idx])]
            if bool(duplicate_mask.loc[idx]):
                row_errors.append("duplicate_record")
            invalid_rows.append(
                {
                    "index": int(idx),
                    "errors": row_errors,
                    "row": raw_df.iloc[int(idx)].to_dict() if idx < len(raw_df) else {},
                }
            )

        if invalid_rows and not allow_partial:
            raise ValueError(f"Validation failed with {len(invalid_rows)} invalid rows")

        valid_df = df[~invalid_mask].copy()
        if not valid_df.empty:
            valid_df["item_id"] = valid_df["item_id"].astype(int)
            valid_df["department_id"] = valid_df["department_id"].astype(int)
            valid_df["quantity_used"] = valid_df["quantity_used"].astype(int)
            valid_df["batch_id"] = valid_df["batch_id"].where(valid_df["batch_id"].notna(), None)

        return {
            "valid_df": valid_df,
            "invalid_rows": invalid_rows,
        }

    def detect_anomalies_tool(self, valid_df: pd.DataFrame) -> dict[str, Any]:
        if valid_df.empty:
            return {
                "red": 0,
                "yellow": 0,
                "records": [],
            }

        qty = valid_df["quantity_used"].astype(float)
        mean = float(qty.mean())
        std = float(qty.std(ddof=0))
        if std <= 1e-9:
            z = pd.Series([0.0] * len(valid_df), index=valid_df.index)
        else:
            z = (qty - mean) / std

        rows: list[dict[str, Any]] = []
        red = yellow = 0
        for idx, score in z.items():
            abs_score = abs(float(score))
            severity = None
            if abs_score > 3.0:
                severity = "RED"
                red += 1
            elif abs_score > 2.0:
                severity = "YELLOW"
                yellow += 1

            if severity:
                row = valid_df.loc[idx]
                rows.append(
                    {
                        "item_id": int(row["item_id"]),
                        "department_id": int(row["department_id"]),
                        "quantity_used": int(row["quantity_used"]),
                        "usage_date": str(row["usage_date"]),
                        "z_score": round(abs_score, 4),
                        "severity": severity,
                    }
                )

        return {
            "red": red,
            "yellow": yellow,
            "records": rows,
        }

    def ingest_database_tool(self, db: Session, valid_df: pd.DataFrame, max_retries: int = 2) -> int:
        if valid_df.empty:
            return 0

        rows: list[ConsumptionRecord] = []
        for _, rec in valid_df.iterrows():
            rows.append(
                ConsumptionRecord(
                    item_id=int(rec["item_id"]),
                    batch_id=int(rec["batch_id"]) if pd.notna(rec["batch_id"]) else None,
                    department_id=int(rec["department_id"]),
                    quantity_used=int(rec["quantity_used"]),
                    usage_date=rec["usage_date"],
                    patient_type=str(rec["patient_type"]),
                )
            )

        attempts = max(1, int(max_retries) + 1)
        last_error: Exception | None = None
        for _ in range(attempts):
            try:
                db.add_all(rows)
                db.commit()
                return len(rows)
            except SQLAlchemyError as exc:
                db.rollback()
                last_error = exc
                continue

        raise RuntimeError(f"Database ingestion failed after retries: {last_error}")
