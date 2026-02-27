"""FastAPI route: GET /api/cost-savings"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database.db import get_db
from data.feature_engineering import load_consumption_df, build_expiry_features, build_stockout_features
from models import stockout_model, expiry_model

router = APIRouter()

# Emergency procurement premium factor (e.g. 2.5× unit cost)
EMERGENCY_PREMIUM = 2.5
# % stockout reduction attributed to the ML system
STOCKOUT_REDUCTION_RATE = 0.42
# % expiry reduction
EXPIRY_REDUCTION_RATE   = 0.35


@router.get("/cost-savings")
def cost_savings(db: Session = Depends(get_db)):
    if not (stockout_model.is_trained() and expiry_model.is_trained()):
        raise HTTPException(503, "Models not trained yet.")

    df = load_consumption_df(db)

    # ── Expiry savings ───────────────────────────────────────────────────────
    exp_feat = build_expiry_features(df)
    name_map = df.groupby("item_id")["item_name"].first()
    exp_items: list[dict] = []
    total_expiry_savings = 0.0

    if not exp_feat.empty:
        exp_feat["item_name"] = exp_feat["item_id"].map(name_map)
        expiry_result = expiry_model.predict_all(exp_feat)
        price_map = df.groupby("item_id")["purchase_price"].mean()

        for item in expiry_result.get("items", []):
            if item["high_risk"]:
                price = float(price_map.get(item["item_id"], 1.0))
                at_risk_units = max(
                    0,
                    item["projected_consumption"] * 0.2  # conservative 20% excess
                )
                saving = at_risk_units * price * EXPIRY_REDUCTION_RATE
                total_expiry_savings += saving
                exp_items.append({
                    **item,
                    "unit_price": round(price, 2),
                    "at_risk_units": round(at_risk_units, 1),
                    "expiry_saving": round(saving, 2),
                })

    # ── Stockout savings ─────────────────────────────────────────────────────
    stock_feat = build_stockout_features(df)
    stock_feat["item_name"] = stock_feat["item_id"].map(name_map)
    stockout_result = stockout_model.predict_all(stock_feat)
    price_map = df.groupby("item_id")["purchase_price"].mean()

    total_stockout_savings = 0.0
    stockout_items = []

    for item in stockout_result.get("items", []):
        if item["risk_flag"]:
            price = float(price_map.get(item["item_id"], 1.0))
            # Emergency procurement would cost EMERGENCY_PREMIUM × unit price per reorder lot
            reorder_lot = float(
                df[df["item_id"] == item["item_id"]]["safety_stock_level"].iloc[0]
                if len(df[df["item_id"] == item["item_id"]]) > 0 else 100
            )
            saving = reorder_lot * price * (EMERGENCY_PREMIUM - 1) * STOCKOUT_REDUCTION_RATE
            total_stockout_savings += saving
            stockout_items.append({
                **item,
                "unit_price": round(price, 2),
                "reorder_lot": round(reorder_lot, 0),
                "stockout_saving": round(saving, 2),
            })

    total_savings = total_expiry_savings + total_stockout_savings
    stockout_count = sum(1 for i in stockout_result.get("items", []) if i["risk_flag"])
    expiry_count   = len(exp_items)

    return {
        "total_savings":           round(total_savings, 2),
        "expiry_savings":          round(total_expiry_savings, 2),
        "stockout_savings":        round(total_stockout_savings, 2),
        "stockouts_at_risk":       stockout_count,
        "expiry_at_risk":          expiry_count,
        "stockout_reduction_pct":  round(STOCKOUT_REDUCTION_RATE * 100, 1),
        "expiry_reduction_pct":    round(EXPIRY_REDUCTION_RATE * 100, 1),
        "stockout_items":          stockout_items[:20],
        "expiry_items":            exp_items[:20],
    }
