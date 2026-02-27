"""
Expiry Risk Model

Model: Logistic Regression
Target: Will the batch expire before it is fully consumed? (Binary)
Metrics: ROC Curve, AUC Score
"""
from __future__ import annotations

import pickle

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, roc_curve
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from config import PKL_DIR, RANDOM_SEED

FEATURE_COLS = [
    "avg_daily_usage", "days_until_expiry",
    "projected_consumption", "reorder_point",
]
TARGET_COL = "expiry_label"

PKL_LR     = PKL_DIR / "expiry_lr.pkl"
PKL_SCALER = PKL_DIR / "expiry_scaler.pkl"
PKL_META   = PKL_DIR / "expiry_meta.pkl"


def train(feat_df: pd.DataFrame) -> dict:
    """Train Logistic Regression for expiry risk. Returns metrics dict."""
    feat_df = feat_df.dropna(subset=FEATURE_COLS + [TARGET_COL])

    if len(feat_df) < 10:
        print("[ExpiryModel] Not enough data to train.")
        return {}

    X = feat_df[FEATURE_COLS].values.astype(float)
    y = feat_df[TARGET_COL].values.astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_SEED
    )

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s  = scaler.transform(X_test)

    lr = LogisticRegression(class_weight="balanced", random_state=RANDOM_SEED, max_iter=500)
    lr.fit(X_train_s, y_train)

    y_proba = lr.predict_proba(X_test_s)[:, 1]
    auc     = float(roc_auc_score(y_test, y_proba))

    fpr, tpr, thresh = roc_curve(y_test, y_proba)
    roc_points = [
        {"fpr": round(float(f), 4), "tpr": round(float(t), 4)}
        for f, t in zip(fpr, tpr)
    ]

    meta = {
        "auc": auc,
        "roc_curve": roc_points,
        "coefficients": {col: float(c) for col, c in zip(FEATURE_COLS, lr.coef_[0])},
    }

    with open(PKL_LR,     "wb") as f: pickle.dump(lr,     f)
    with open(PKL_SCALER, "wb") as f: pickle.dump(scaler, f)
    with open(PKL_META,   "wb") as f: pickle.dump(meta,   f)

    print(f"[ExpiryModel] AUC={auc:.4f}")
    return meta


def is_trained() -> bool:
    return PKL_LR.exists() and PKL_META.exists()


def predict_all(feat_df: pd.DataFrame) -> dict:
    """Return expiry risk for every item row in feat_df."""
    with open(PKL_LR,     "rb") as f: lr     = pickle.load(f)
    with open(PKL_SCALER, "rb") as f: scaler = pickle.load(f)
    with open(PKL_META,   "rb") as f: meta   = pickle.load(f)

    available = [c for c in FEATURE_COLS if c in feat_df.columns]
    X = feat_df[available].fillna(0).values.astype(float)
    X_s = scaler.transform(X)
    probas = lr.predict_proba(X_s)[:, 1]

    items = []
    for i, (_, row) in enumerate(feat_df.iterrows()):
        items.append({
            "item_id":          int(row["item_id"]),
            "item_name":        row.get("item_name", str(row["item_id"])),
            "expiry_risk_prob": round(float(probas[i]), 3),
            "high_risk":        bool(probas[i] >= 0.5),
            "days_until_expiry": int(row.get("days_until_expiry", 0)),
            "avg_daily_usage":  round(float(row.get("avg_daily_usage", 0)), 1),
            "projected_consumption": round(float(row.get("projected_consumption", 0)), 1),
        })

    items.sort(key=lambda x: x["expiry_risk_prob"], reverse=True)

    return {"items": items, "metrics": meta}
