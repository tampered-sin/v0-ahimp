"""
Demand Forecasting Model

Models:
    1. Linear Regression (baseline)
    2. ARIMA (time-series baseline)
    3. LightGBM Regressor (primary model)

Metrics: MAE, RMSE, R²
"""
from __future__ import annotations

import pickle
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

try:
    from statsmodels.tsa.arima.model import ARIMA
    ARIMA_AVAILABLE = True
except ImportError:
    ARIMA_AVAILABLE = False

from config import PKL_DIR, RANDOM_SEED, FORECAST_HORIZON
from models.lightgbm_model import (
    build_model as build_lgbm_model,
    cross_validate_r2,
    load_model as load_lgbm_model,
    save_model as save_lgbm_model,
)

FEATURE_COLS = [
    "rolling_7d", "rolling_30d", "lag_7", "lag_14",
    "day_of_week", "month", "velocity", "stock_ratio",
    "avg_lead_time_days", "reliability_score",
]
TARGET_COL = "quantity_used"

PKL_LGBM = PKL_DIR / "demand_lgbm.pkl"
PKL_LR  = PKL_DIR / "demand_lr.pkl"
PKL_META = PKL_DIR / "demand_meta.pkl"


def _evaluate_arima_baseline(feat_df: pd.DataFrame) -> tuple[dict | None, str | None]:
    """
    Evaluate ARIMA on aggregated daily demand with safe fallbacks.
    Returns (metrics, error).
    """
    if not ARIMA_AVAILABLE:
        return None, "statsmodels ARIMA is unavailable"

    series_df = feat_df[["usage_date", TARGET_COL]].dropna().copy()
    if series_df.empty:
        return None, "no usable demand time-series rows"

    series_df["usage_date"] = pd.to_datetime(series_df["usage_date"], errors="coerce")
    series_df = series_df.dropna(subset=["usage_date"])
    if series_df.empty:
        return None, "usage_date could not be parsed"

    ts = (
        series_df.groupby("usage_date")[TARGET_COL]
        .sum()
        .sort_index()
        .astype(float)
    )

    if len(ts) < 30:
        return None, f"insufficient history for ARIMA: {len(ts)} points"

    split = int(len(ts) * 0.8)
    split = max(20, min(split, len(ts) - 7))
    train_ts = ts.iloc[:split]
    test_ts = ts.iloc[split:]

    if len(test_ts) < 7:
        return None, f"insufficient holdout window for ARIMA: {len(test_ts)} points"

    candidate_orders = [(2, 1, 2), (1, 1, 1), (1, 0, 1)]
    best_metrics = None
    best_mae = float("inf")
    errors: list[str] = []

    for order in candidate_orders:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                model = ARIMA(train_ts, order=order)
                fitted = model.fit()

            y_pred = np.asarray(fitted.forecast(steps=len(test_ts)), dtype=float)
            y_true = test_ts.to_numpy(dtype=float)

            mae = float(mean_absolute_error(y_true, y_pred))
            rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
            r2 = float(r2_score(y_true, y_pred))

            if mae < best_mae:
                best_mae = mae
                best_metrics = {
                    "mae": mae,
                    "rmse": rmse,
                    "r2": r2,
                    "order": list(order),
                    "series_points": int(len(ts)),
                    "holdout_points": int(len(test_ts)),
                }
        except Exception as exc:
            errors.append(f"order={order}: {exc}")

    if best_metrics is None:
        short_error = "; ".join(errors[:2]) if errors else "unknown ARIMA failure"
        return None, short_error

    return best_metrics, None


# ─── Training ────────────────────────────────────────────────────────────────

def train(feat_df: pd.DataFrame) -> dict:
    """Train all three demand models. Returns metrics dict."""
    feat_df = feat_df.dropna(subset=FEATURE_COLS + [TARGET_COL])
    X = feat_df[FEATURE_COLS].values
    y = feat_df[TARGET_COL].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_SEED, shuffle=False
    )

    # ── LightGBM ─────────────────────────────────────────────────────────────
    lgbm = build_lgbm_model(RANDOM_SEED)
    lgbm.fit(X_train, y_train)
    y_pred_lgbm = lgbm.predict(X_test)

    mae_lgbm  = float(mean_absolute_error(y_test, y_pred_lgbm))
    rmse_lgbm = float(np.sqrt(mean_squared_error(y_test, y_pred_lgbm)))
    r2_lgbm   = float(r2_score(y_test, y_pred_lgbm))
    cv_r2_scores = cross_validate_r2(X_train, y_train, RANDOM_SEED, folds=5)

    save_lgbm_model(lgbm, PKL_LGBM)

    # ── Linear Regression ────────────────────────────────────────────────────
    lr = LinearRegression()
    lr.fit(X_train, y_train)
    y_pred_lr = lr.predict(X_test)

    mae_lr  = float(mean_absolute_error(y_test, y_pred_lr))
    rmse_lr = float(np.sqrt(mean_squared_error(y_test, y_pred_lr)))
    r2_lr   = float(r2_score(y_test, y_pred_lr))

    with open(PKL_LR, "wb") as f:
        pickle.dump(lr, f)

    # ── ARIMA baseline on aggregate demand ───────────────────────────────────
    arima_metrics, arima_error = _evaluate_arima_baseline(feat_df)
    arima_payload = {
        "mae": None,
        "rmse": None,
        "r2": None,
    }
    if arima_metrics:
        arima_payload.update(arima_metrics)
    if arima_error:
        arima_payload["error"] = arima_error

    # ── Feature importance ───────────────────────────────────────────────────
    importance = [
        {"feature": col, "importance": float(imp)}
        for col, imp in zip(FEATURE_COLS, lgbm.feature_importances_)
    ]
    importance.sort(key=lambda x: x["importance"], reverse=True)

    meta = {
        # Keep xgb key for backward compatibility with existing frontend types.
        "xgb": {"mae": mae_lgbm,  "rmse": rmse_lgbm,  "r2": r2_lgbm},
        "lgbm": {
            "mae": mae_lgbm,
            "rmse": rmse_lgbm,
            "r2": r2_lgbm,
            "cv_r2_scores": cv_r2_scores,
            "cv_r2_mean": float(np.mean(cv_r2_scores)) if cv_r2_scores else None,
        },
        "lr":  {"mae": mae_lr,   "rmse": rmse_lr,    "r2": r2_lr},
        "arima": arima_payload,
        "feature_importance": importance,
        "feature_cols": FEATURE_COLS,
        "primary_model": "LightGBM",
    }
    with open(PKL_META, "wb") as f:
        pickle.dump(meta, f)

    print(f"[DemandModel] LGBM MAE={mae_lgbm:.2f}  RMSE={rmse_lgbm:.2f}  R²={r2_lgbm:.3f}")
    return meta


# ─── Inference ───────────────────────────────────────────────────────────────

def _load_lgbm():
    return load_lgbm_model(PKL_LGBM)


def _load_lr() -> LinearRegression:
    with open(PKL_LR, "rb") as f:
        return pickle.load(f)


def _load_meta() -> dict:
    with open(PKL_META, "rb") as f:
        return pickle.load(f)


def is_trained() -> bool:
    return PKL_LGBM.exists() and PKL_META.exists()


def _iterative_forecast(
    model,
    item_df: pd.DataFrame,
    horizon: int = FORECAST_HORIZON,
) -> list[dict]:
    """Run iterative horizon forecasting with rolling feature updates."""
    history = list(item_df["quantity_used"].values)
    forecast = []
    today = pd.Timestamp.today().normalize()

    for day in range(horizon):
        arr = np.array(history)
        r7 = arr[-7:].mean() if len(arr) >= 7 else arr.mean()
        r30 = arr[-30:].mean() if len(arr) >= 30 else arr.mean()
        l7 = arr[-7] if len(arr) >= 7 else arr[0]
        l14 = arr[-14] if len(arr) >= 14 else arr[0]
        vel = float(np.polyfit(range(min(14, len(arr))), arr[-min(14, len(arr)):], 1)[0])
        target_dt = today + pd.Timedelta(days=day + 1)
        stock_ratio = r7 / max(1, item_df["reorder_point"].iloc[0])
        features = np.array(
            [[
                r7,
                r30,
                l7,
                l14,
                target_dt.dayofweek,
                target_dt.month,
                vel,
                stock_ratio,
                item_df["avg_lead_time_days"].iloc[0],
                item_df["reliability_score"].iloc[0],
            ]]
        )
        pred = float(max(0, model.predict(features)[0]))
        forecast.append(
            {
                "date": target_dt.strftime("%Y-%m-%d"),
                "predicted": round(pred, 1),
                "lower": round(max(0, pred * 0.80), 1),
                "upper": round(pred * 1.20, 1),
            }
        )
        history.append(pred)

    return forecast


def predict_forecast(feat_df: pd.DataFrame, item_id: int) -> dict:
    """
    Generate a 14-day demand forecast for a specific item.
    Uses LightGBM iteratively with rolling feature updates.
    """
    lgbm = _load_lgbm()
    meta = _load_meta()

    item_df = (
        feat_df[feat_df["item_id"] == item_id]
        .sort_values("usage_date")
        .tail(60)
        .reset_index(drop=True)
    )

    if item_df.empty:
        return {"error": "No data for this item"}

    forecast = _iterative_forecast(lgbm, item_df, horizon=FORECAST_HORIZON)

    return {
        "item_id":   item_id,
        "item_name": item_df["item_name"].iloc[0] if "item_name" in item_df else str(item_id),
        "forecast":  forecast,
        "metrics":   meta,
        "feature_importance": meta["feature_importance"],
    }


def predict_forecast_lr(feat_df: pd.DataFrame, item_id: int) -> dict:
    """Generate a 14-day demand forecast using the persisted Linear Regression model."""
    if not PKL_LR.exists():
        return {"error": "Linear Regression model not trained"}

    lr = _load_lr()
    meta = _load_meta()
    item_df = (
        feat_df[feat_df["item_id"] == item_id]
        .sort_values("usage_date")
        .tail(60)
        .reset_index(drop=True)
    )
    if item_df.empty:
        return {"error": "No data for this item"}

    forecast = _iterative_forecast(lr, item_df, horizon=FORECAST_HORIZON)
    return {
        "item_id": item_id,
        "item_name": item_df["item_name"].iloc[0] if "item_name" in item_df else str(item_id),
        "forecast": forecast,
        "metrics": meta.get("lr", {}),
        "model": "LinearRegression",
    }
