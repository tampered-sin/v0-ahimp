"""Supplier scoring utilities for stockout-driven purchasing decisions."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from agents.sentiment_analyzer import analyze_sentiment
from database.models import Batch, Item, Supplier


WEIGHTS = {
    "reliability": 0.30,
    "on_time_delivery": 0.25,
    "price_competitiveness": 0.20,
    "distance_penalty": 0.15,
    "review_sentiment": 0.10,
}

_CACHE: dict[str, dict[str, Any]] = {}
_HISTORY: dict[int, list[dict[str, Any]]] = {}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _normalize(value: float, min_value: float, max_value: float, inverse: bool = False) -> float:
    if max_value - min_value <= 1e-9:
        return 50.0
    scaled = (value - min_value) / (max_value - min_value)
    if inverse:
        scaled = 1.0 - scaled
    return round(_clamp(scaled * 100.0, 0.0, 100.0), 2)


def _distance_to_score(distance_km: float | None) -> float:
    if distance_km is None:
        return 70.0
    bounded = _clamp(float(distance_km), 0.0, 500.0)
    return round(100.0 - (bounded / 500.0) * 100.0, 2)


def _sentiment_to_score(sentiment: float | None) -> float:
    if sentiment is None:
        return 50.0
    bounded = _clamp(float(sentiment), -1.0, 1.0)
    return round((bounded + 1.0) * 50.0, 2)


def _build_override_map(supplier_overrides: list[dict[str, Any]] | None) -> dict[int, dict[str, Any]]:
    override_map: dict[int, dict[str, Any]] = {}
    for row in supplier_overrides or []:
        sid = int(row.get("supplier_id"))
        override_map[sid] = {
            "distance_km": row.get("distance_km"),
            "sentiment_score": row.get("sentiment_score"),
            "review_text": row.get("review_text"),
        }
    return override_map


def _fetch_price_map(db: Session, item_id: int) -> dict[int, float]:
    item_prices = (
        db.query(Batch.supplier_id, func.avg(Batch.purchase_price))
        .filter(Batch.item_id == item_id)
        .group_by(Batch.supplier_id)
        .all()
    )

    if item_prices:
        return {int(supplier_id): float(avg_price) for supplier_id, avg_price in item_prices if avg_price is not None}

    # Fallback to global supplier pricing when no item-level history is available.
    global_prices = db.query(Batch.supplier_id, func.avg(Batch.purchase_price)).group_by(Batch.supplier_id).all()
    return {int(supplier_id): float(avg_price) for supplier_id, avg_price in global_prices if avg_price is not None}


def _build_cache_key(item_id: int, supplier_overrides: list[dict[str, Any]] | None) -> str:
    now_day = datetime.now(tz=timezone.utc).date().isoformat()
    normalized = sorted(
        supplier_overrides or [],
        key=lambda row: int(row.get("supplier_id", 0)),
    )
    return json.dumps(
        {
            "item_id": int(item_id),
            "day": now_day,
            "overrides": normalized,
        },
        sort_keys=True,
    )


def score_suppliers(
    db: Session,
    item_id: int,
    supplier_overrides: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    item = db.query(Item.item_id, Item.item_name).filter(Item.item_id == item_id).first()
    if item is None:
        raise ValueError("Item not found")

    cache_key = _build_cache_key(item_id, supplier_overrides)
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    suppliers = db.query(Supplier).order_by(Supplier.supplier_id.asc()).all()
    if not suppliers:
        raise ValueError("No suppliers available")

    override_map = _build_override_map(supplier_overrides)
    price_map = _fetch_price_map(db, item_id)

    lead_times = [float(s.avg_lead_time_days or 30.0) for s in suppliers]
    lead_min, lead_max = min(lead_times), max(lead_times)

    price_values = [float(v) for v in price_map.values()]
    price_min = min(price_values) if price_values else 0.0
    price_max = max(price_values) if price_values else 0.0

    scored: list[dict[str, Any]] = []
    for supplier in suppliers:
        supplier_id = int(supplier.supplier_id)
        reliability_score = round(_clamp(float(supplier.reliability_score or 0.0) * 100.0, 0.0, 100.0), 2)

        lead_days = float(supplier.avg_lead_time_days or 30.0)
        on_time_score = _normalize(lead_days, lead_min, lead_max, inverse=True)

        item_price = price_map.get(supplier_id)
        price_score = 50.0 if item_price is None else _normalize(float(item_price), price_min, price_max, inverse=True)

        overrides = override_map.get(supplier_id, {})
        distance_score = _distance_to_score(overrides.get("distance_km"))
        sentiment_source = "override"
        sentiment_value = overrides.get("sentiment_score")
        if sentiment_value is None and overrides.get("review_text"):
            analyzed = analyze_sentiment(str(overrides["review_text"]))
            sentiment_value = analyzed["sentiment_score"]
            sentiment_source = analyzed["model"]
        elif sentiment_value is None:
            sentiment_source = "default"

        sentiment_score = _sentiment_to_score(sentiment_value)

        composite = (
            reliability_score * WEIGHTS["reliability"]
            + on_time_score * WEIGHTS["on_time_delivery"]
            + price_score * WEIGHTS["price_competitiveness"]
            + distance_score * WEIGHTS["distance_penalty"]
            + sentiment_score * WEIGHTS["review_sentiment"]
        )

        scored.append(
            {
                "supplier_id": supplier_id,
                "supplier_name": supplier.supplier_name,
                "score": round(composite, 2),
                "breakdown": {
                    "reliability": reliability_score,
                    "on_time_delivery": on_time_score,
                    "price_competitiveness": price_score,
                    "distance_penalty": distance_score,
                    "review_sentiment": sentiment_score,
                },
                "inputs": {
                    "avg_lead_time_days": lead_days,
                    "avg_purchase_price": round(float(item_price), 4) if item_price is not None else None,
                    "distance_km": overrides.get("distance_km"),
                    "sentiment_score": sentiment_value,
                    "sentiment_source": sentiment_source,
                    "review_text": overrides.get("review_text"),
                },
            }
        )

    scored.sort(key=lambda row: (-float(row["score"]), int(row["supplier_id"])))
    for idx, row in enumerate(scored, start=1):
        row["rank"] = idx

    generated_at = datetime.now(tz=timezone.utc).isoformat()
    history = _HISTORY.setdefault(int(item_id), [])
    history.append(
        {
            "generated_at": generated_at,
            "top_supplier_id": scored[0]["supplier_id"],
            "top_score": scored[0]["score"],
        }
    )

    result = {
        "item_id": int(item_id),
        "item_name": item.item_name,
        "weights": WEIGHTS,
        "generated_at": generated_at,
        "suppliers": scored,
        "history": history[-30:],
    }

    _CACHE[cache_key] = result
    return result


def clear_supplier_score_cache() -> None:
    _CACHE.clear()
