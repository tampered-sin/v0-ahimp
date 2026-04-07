"""
Anomaly detection for consumption records.

Model:
- Isolation Forest with contamination=5%

Rule-based safeguards:
- Sudden 10x consumption spike vs item baseline
- Zero consumption when item baseline is high
- Department-level >3 sigma deviations
"""
from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from config import PKL_DIR, RANDOM_SEED

PKL_IFOREST = PKL_DIR / "anomaly_iforest.pkl"
PKL_META = PKL_DIR / "anomaly_meta.pkl"

MODEL_FEATURES = [
    "quantity_used",
    "item_mean",
    "item_std",
    "dept_mean",
    "dept_std",
    "day_of_week",
    "month",
]


def _safe_std(series: pd.Series) -> float:
    val = float(series.std(ddof=0)) if len(series) > 1 else 0.0
    return val if val > 1e-6 else 1.0


def _build_detection_frame(df: pd.DataFrame) -> pd.DataFrame:
    required = ["item_id", "department_id", "quantity_used", "usage_date"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns for anomaly detection: {missing}")

    feat = df.copy()
    feat["usage_date"] = pd.to_datetime(feat["usage_date"])

    item_stats = (
        feat.groupby("item_id")["quantity_used"]
        .agg(["mean", lambda s: _safe_std(s)])
        .reset_index()
        .rename(columns={"mean": "item_mean", "<lambda_0>": "item_std"})
    )
    dept_stats = (
        feat.groupby("department_id")["quantity_used"]
        .agg(["mean", lambda s: _safe_std(s)])
        .reset_index()
        .rename(columns={"mean": "dept_mean", "<lambda_0>": "dept_std"})
    )

    feat = feat.merge(item_stats, on="item_id", how="left")
    feat = feat.merge(dept_stats, on="department_id", how="left")

    feat["item_std"] = feat["item_std"].fillna(1.0).replace(0, 1.0)
    feat["dept_std"] = feat["dept_std"].fillna(1.0).replace(0, 1.0)
    feat["item_mean"] = feat["item_mean"].fillna(0.0)
    feat["dept_mean"] = feat["dept_mean"].fillna(0.0)

    feat["item_z"] = (feat["quantity_used"] - feat["item_mean"]) / feat["item_std"]
    feat["dept_z"] = (feat["quantity_used"] - feat["dept_mean"]) / feat["dept_std"]
    feat["day_of_week"] = feat["usage_date"].dt.dayofweek
    feat["month"] = feat["usage_date"].dt.month

    feat["spike_10x"] = (feat["item_mean"] > 0) & (feat["quantity_used"] >= feat["item_mean"] * 10)
    feat["zero_high_baseline"] = (feat["quantity_used"] == 0) & (feat["item_mean"] >= 5)
    feat["item_sigma_gt_3"] = feat["item_z"].abs() > 3
    feat["dept_sigma_gt_3"] = feat["dept_z"].abs() > 3

    return feat


def train(df: pd.DataFrame) -> dict:
    """Train IsolationForest and persist metadata."""
    feat = _build_detection_frame(df)
    X = feat[MODEL_FEATURES].astype(float).to_numpy()

    model = IsolationForest(
        n_estimators=300,
        contamination=0.05,
        random_state=RANDOM_SEED,
        n_jobs=-1,
    )
    model.fit(X)

    PKL_IFOREST.parent.mkdir(parents=True, exist_ok=True)
    with open(PKL_IFOREST, "wb") as f:
        pickle.dump(model, f)

    meta = {
        "contamination": 0.05,
        "n_estimators": 300,
        "features": MODEL_FEATURES,
        "rules": [
            "spike_10x",
            "zero_high_baseline",
            "item_sigma_gt_3",
            "dept_sigma_gt_3",
        ],
    }
    with open(PKL_META, "wb") as f:
        pickle.dump(meta, f)

    return meta


def is_trained() -> bool:
    return PKL_IFOREST.exists() and PKL_META.exists()


def _load_model() -> IsolationForest:
    with open(PKL_IFOREST, "rb") as f:
        return pickle.load(f)


def detect(df: pd.DataFrame) -> pd.DataFrame:
    """Detect anomalies in the supplied dataframe."""
    if not is_trained():
        raise FileNotFoundError("Anomaly detector is not trained")

    feat = _build_detection_frame(df)
    X = feat[MODEL_FEATURES].astype(float).to_numpy()

    model = _load_model()
    iforest_pred = model.predict(X)  # -1 outlier, 1 inlier
    anomaly_score = -model.score_samples(X)

    feat["iforest_anomaly"] = iforest_pred == -1
    feat["anomaly_score"] = anomaly_score
    feat["anomaly_flag"] = (
        feat["iforest_anomaly"]
        | feat["spike_10x"]
        | feat["zero_high_baseline"]
        | feat["item_sigma_gt_3"]
        | feat["dept_sigma_gt_3"]
    )

    def _severity(row: pd.Series) -> str:
        if row["spike_10x"] or row["zero_high_baseline"] or row["item_sigma_gt_3"] or row["dept_sigma_gt_3"]:
            return "RED"
        if row["iforest_anomaly"]:
            return "YELLOW"
        return "NORMAL"

    feat["severity"] = feat.apply(_severity, axis=1)

    def _reasons(row: pd.Series) -> list[str]:
        reasons = []
        if row["spike_10x"]:
            reasons.append("sudden_10x_spike")
        if row["zero_high_baseline"]:
            reasons.append("zero_with_high_baseline")
        if row["item_sigma_gt_3"]:
            reasons.append("item_sigma_gt_3")
        if row["dept_sigma_gt_3"]:
            reasons.append("department_sigma_gt_3")
        if row["iforest_anomaly"]:
            reasons.append("iforest_outlier")
        return reasons

    feat["reasons"] = feat.apply(_reasons, axis=1)
    return feat


def predict_recent(df: pd.DataFrame, days: int = 7, limit: int = 100) -> dict:
    """Return recent anomalies for API usage."""
    detected = detect(df)
    cutoff = detected["usage_date"].max() - pd.Timedelta(days=days)
    recent = detected[(detected["usage_date"] >= cutoff) & (detected["anomaly_flag"])].copy()
    recent = recent.sort_values(["severity", "anomaly_score"], ascending=[True, False]).head(limit)

    records = []
    for _, row in recent.iterrows():
        records.append(
            {
                "item_id": int(row["item_id"]),
                "department_id": int(row["department_id"]),
                "usage_date": pd.Timestamp(row["usage_date"]).strftime("%Y-%m-%d"),
                "quantity_used": float(row["quantity_used"]),
                "severity": row["severity"],
                "anomaly_score": float(row["anomaly_score"]),
                "reasons": row["reasons"],
            }
        )

    red_count = int((recent["severity"] == "RED").sum()) if not recent.empty else 0
    yellow_count = int((recent["severity"] == "YELLOW").sum()) if not recent.empty else 0

    return {
        "days": days,
        "total_anomalies": len(records),
        "red_alerts": red_count,
        "yellow_alerts": yellow_count,
        "anomalies": records,
    }
