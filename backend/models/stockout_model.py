"""
Stockout Risk Model

Model: Random Forest Classifier
Target: Will this item stock out in the next 7 days? (Binary)
Metrics: Accuracy, Precision, Recall, F1, Confusion Matrix
"""
from __future__ import annotations

import pickle

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, confusion_matrix,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import label_binarize

from config import PKL_DIR, RANDOM_SEED

FEATURE_COLS = [
    "rolling_7d", "rolling_30d", "lag_7", "lag_14",
    "day_of_week", "month", "velocity", "stock_ratio",
    "avg_lead_time_days", "reliability_score",
]
TARGET_COL = "stockout_label"

PKL_RF   = PKL_DIR / "stockout_rf.pkl"
PKL_META = PKL_DIR / "stockout_meta.pkl"


def train(feat_df: pd.DataFrame) -> dict:
    """Train Random Forest classifier. Returns metrics dict."""
    feat_df = feat_df.dropna(subset=FEATURE_COLS + [TARGET_COL])

    X = feat_df[FEATURE_COLS].values
    y = feat_df[TARGET_COL].values.astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_SEED, stratify=y
    )

    rf = RandomForestClassifier(
        n_estimators=200, max_depth=10,
        class_weight="balanced", random_state=RANDOM_SEED, n_jobs=-1,
    )
    rf.fit(X_train, y_train)

    y_pred  = rf.predict(X_test)
    y_proba = rf.predict_proba(X_test)[:, 1]

    acc  = float(accuracy_score(y_test, y_pred))
    prec = float(precision_score(y_test, y_pred, zero_division=0))
    rec  = float(recall_score(y_test, y_pred, zero_division=0))
    f1   = float(f1_score(y_test, y_pred, zero_division=0))
    cm   = confusion_matrix(y_test, y_pred).tolist()

    importance = [
        {"feature": col, "importance": float(imp)}
        for col, imp in zip(FEATURE_COLS, rf.feature_importances_)
    ]
    importance.sort(key=lambda x: x["importance"], reverse=True)

    meta = {
        "accuracy": acc, "precision": prec, "recall": rec, "f1": f1,
        "confusion_matrix": cm, "feature_importance": importance,
    }

    with open(PKL_RF, "wb") as f:
        pickle.dump(rf, f)
    with open(PKL_META, "wb") as f:
        pickle.dump(meta, f)

    print(f"[StockoutModel] Acc={acc:.3f}  Pre={prec:.3f}  Rec={rec:.3f}  F1={f1:.3f}")
    return meta


def is_trained() -> bool:
    return PKL_RF.exists() and PKL_META.exists()


def predict_all(feat_df: pd.DataFrame) -> dict:
    """
    Return stockout risk probability for every item (most recent row).
    """
    with open(PKL_RF, "rb") as f:
        rf = pickle.load(f)
    with open(PKL_META, "rb") as f:
        meta = pickle.load(f)

    # Most recent feature row per item
    latest = (
        feat_df.sort_values("usage_date")
        .groupby("item_id")
        .last()
        .reset_index()
    )

    available_cols = [c for c in FEATURE_COLS if c in latest.columns]
    X = latest[available_cols].fillna(0).values

    probas = rf.predict_proba(X)[:, 1]
    preds  = (probas >= 0.5).astype(int)

    items = []
    for i, row in latest.iterrows():
        items.append({
            "item_id":       int(row["item_id"]),
            "item_name":     row.get("item_name", str(row["item_id"])),
            "risk_prob":     round(float(probas[list(latest.index).index(i)]), 3),
            "risk_flag":     bool(preds[list(latest.index).index(i)]),
            "rolling_7d":    round(float(row.get("rolling_7d", 0)), 1),
            "stock_ratio":   round(float(row.get("stock_ratio", 0)), 3),
        })

    items.sort(key=lambda x: x["risk_prob"], reverse=True)

    return {
        "items":   items,
        "metrics": meta,
    }
