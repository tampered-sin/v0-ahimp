from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.supplier_scoring import clear_supplier_score_cache, score_suppliers
from database.db import Base
from database.models import Batch, Item, Supplier


def _make_db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return SessionLocal()


def _seed_supplier_fixtures(db):
    item = Item(item_id=1, item_name="Gloves", category="PPE", unit_type="box")
    db.add(item)

    suppliers = [
        Supplier(
            supplier_id=1,
            supplier_name="Alpha Medical",
            avg_lead_time_days=5,
            reliability_score=0.96,
        ),
        Supplier(
            supplier_id=2,
            supplier_name="Budget Supplies",
            avg_lead_time_days=12,
            reliability_score=0.82,
        ),
        Supplier(
            supplier_id=3,
            supplier_name="Prime Care",
            avg_lead_time_days=7,
            reliability_score=0.90,
        ),
    ]
    db.add_all(suppliers)

    db.add_all(
        [
            Batch(item_id=1, supplier_id=1, purchase_price=10.0, quantity_received=100),
            Batch(item_id=1, supplier_id=2, purchase_price=7.5, quantity_received=100),
            Batch(item_id=1, supplier_id=3, purchase_price=11.5, quantity_received=100),
        ]
    )
    db.commit()


def test_score_suppliers_ranks_and_breakdown(monkeypatch):
    db = _make_db_session()
    _seed_supplier_fixtures(db)
    clear_supplier_score_cache()

    monkeypatch.setattr(
        "agents.supplier_scoring.analyze_sentiment",
        lambda text: {
            "sentiment_score": 0.4,
            "model": "mocked-model",
        },
    )

    result = score_suppliers(
        db,
        item_id=1,
        supplier_overrides=[
            {"supplier_id": 1, "distance_km": 90, "sentiment_score": 0.6},
            {"supplier_id": 2, "distance_km": 420, "sentiment_score": -0.4},
            {"supplier_id": 3, "distance_km": 140, "review_text": "great quality and reliable delivery"},
        ],
    )

    assert result["item_id"] == 1
    assert len(result["suppliers"]) == 3

    scores = [supplier["score"] for supplier in result["suppliers"]]
    assert scores == sorted(scores, reverse=True)

    top = result["suppliers"][0]
    assert top["supplier_name"] in {"Alpha Medical", "Prime Care"}
    assert set(top["breakdown"].keys()) == {
        "reliability",
        "on_time_delivery",
        "price_competitiveness",
        "distance_penalty",
        "review_sentiment",
    }

    supplier_three = [row for row in result["suppliers"] if row["supplier_id"] == 3][0]
    assert supplier_three["inputs"]["sentiment_source"] == "mocked-model"


def test_score_suppliers_missing_item_raises_error():
    db = _make_db_session()
    clear_supplier_score_cache()

    try:
        score_suppliers(db, item_id=999)
    except ValueError as exc:
        assert "Item not found" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing item")
