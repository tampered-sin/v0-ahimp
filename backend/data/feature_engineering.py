"""
Feature engineering pipeline.

Reads ConsumptionRecord rows from the DB and builds a feature matrix for
the three ML models (demand forecast, stockout risk, expiry risk).
"""
from __future__ import annotations

import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import text


def load_consumption_df(db: Session) -> pd.DataFrame:
    """Load all consumption records into a pandas DataFrame."""
    sql = text("""
        SELECT
            cr.consumption_id,
            cr.item_id,
            i.item_name,
            i.category,
            cr.department_id,
            cr.quantity_used,
            cr.usage_date,
            cr.patient_type,
            b.expiry_date,
            b.purchase_price,
            i.safety_stock_level,
            i.reorder_point,
            s.avg_lead_time_days,
            s.reliability_score
        FROM consumption_records cr
        JOIN items     i ON cr.item_id   = i.item_id
        JOIN batches   b ON cr.batch_id  = b.batch_id
        JOIN suppliers s ON b.supplier_id = s.supplier_id
    """)
    rows = db.execute(sql).fetchall()
    df = pd.DataFrame(rows, columns=[
        "consumption_id", "item_id", "item_name", "category",
        "department_id", "quantity_used", "usage_date", "patient_type",
        "expiry_date", "purchase_price", "safety_stock_level",
        "reorder_point", "avg_lead_time_days", "reliability_score",
    ])
    df["usage_date"]  = pd.to_datetime(df["usage_date"])
    df["expiry_date"] = pd.to_datetime(df["expiry_date"], errors="coerce")
    return df


def build_demand_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate to daily item-level and engineer features for demand forecasting.
    Returns one row per (item_id, usage_date).
    """
    daily = (
        df.groupby(["item_id", "item_name", "usage_date",
                    "safety_stock_level", "reorder_point",
                    "avg_lead_time_days", "reliability_score"])
        .agg(quantity_used=("quantity_used", "sum"))
        .reset_index()
        .sort_values(["item_id", "usage_date"])
    )

    features = []
    for item_id, grp in daily.groupby("item_id"):
        grp = grp.set_index("usage_date").sort_index()

        # Rolling averages
        grp["rolling_7d"]  = grp["quantity_used"].rolling(7,  min_periods=1).mean()
        grp["rolling_30d"] = grp["quantity_used"].rolling(30, min_periods=1).mean()

        # Lag features
        grp["lag_7"]  = grp["quantity_used"].shift(7).fillna(0)
        grp["lag_14"] = grp["quantity_used"].shift(14).fillna(0)

        # Seasonality
        grp["day_of_week"] = grp.index.dayofweek
        grp["month"]       = grp.index.month

        # Demand velocity (slope of last 14 days)
        grp["velocity"] = (
            grp["quantity_used"]
            .rolling(14, min_periods=2)
            .apply(lambda x: np.polyfit(range(len(x)), x, 1)[0], raw=True)
            .fillna(0)
        )

        # Stock ratio proxy (reorder_point as normalizer)
        grp["stock_ratio"] = (
            grp["quantity_used"] / grp["reorder_point"].iloc[0]
        ).replace([np.inf, -np.inf], 0)

        grp = grp.reset_index()
        features.append(grp)

    result = pd.concat(features, ignore_index=True)
    result = result.fillna(0)
    return result


def build_stockout_features(df: pd.DataFrame, horizon_days: int = 7) -> pd.DataFrame:
    """
    Build binary classification dataset for stockout prediction.
    Label = 1 if cumulative usage in next `horizon_days` exceeds safety_stock_level.
    """
    feat_df = build_demand_features(df)

    rows = []
    for item_id, grp in feat_df.groupby("item_id"):
        safety = grp["safety_stock_level"].iloc[0]
        grp = grp.sort_values("usage_date").reset_index(drop=True)

        for i in range(len(grp) - horizon_days):
            future_demand = grp.loc[i + 1: i + horizon_days, "quantity_used"].sum()
            label = int(future_demand > safety)

            row = grp.loc[i, [
                "item_id", "usage_date", "rolling_7d", "rolling_30d",
                "lag_7", "lag_14", "day_of_week", "month",
                "velocity", "stock_ratio",
                "avg_lead_time_days", "reliability_score",
            ]].to_dict()
            row["stockout_label"] = label
            rows.append(row)

    return pd.DataFrame(rows).fillna(0)


def build_expiry_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build binary classification dataset for expiry risk prediction.
    Label = 1 if item expires within days_until_expiry and
    recent usage is too low to consume remaining stock in time.
    """
    today = pd.Timestamp.today().normalize()

    # Last 30-day avg demand per item
    recent = (
        df[df["usage_date"] >= today - pd.Timedelta(days=30)]
        .groupby("item_id")
        .agg(
            avg_daily_usage=("quantity_used", "mean"),
            expiry_date=("expiry_date", "first"),
            purchase_price=("purchase_price", "first"),
            reorder_point=("reorder_point", "first"),
        )
        .reset_index()
    )

    if recent.empty:
        return pd.DataFrame()

    recent["days_until_expiry"] = (
        recent["expiry_date"] - today
    ).dt.days.clip(lower=0)

    recent["projected_consumption"] = (
        recent["avg_daily_usage"] * recent["days_until_expiry"]
    )

    recent["expiry_label"] = (
        recent["projected_consumption"] < recent["reorder_point"]
    ).astype(int)

    return recent.fillna(0)
