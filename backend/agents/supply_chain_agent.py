"""Supply chain agent for stockout monitoring and auto-purchase orchestration."""
from __future__ import annotations

from datetime import date, timedelta
import time
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from agents.config import AgentTask, BaseAgent, build_crewai_llm
from agents.supplier_scoring import score_suppliers
from data.feature_engineering import build_stockout_features, load_consumption_df
from database.models import InventoryStock, Item, PurchaseOrder, Supplier
from models import stockout_model


def build_supply_chain_payload(
    risk_threshold: float = 0.7,
    max_items: int = 10,
    auto_purchase: bool = False,
    cadence_hours: int = 1,
    supplier_overrides: dict[int, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    return {
        "risk_threshold": risk_threshold,
        "max_items": max_items,
        "auto_purchase": auto_purchase,
        "cadence_hours": max(1, int(cadence_hours)),
        "supplier_overrides": supplier_overrides or {},
    }


class SupplyChainAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="supply-chain-agent")
        self.llm = build_crewai_llm(self.settings)
        self.registry.register("check_stockout_risk_tool", self.check_stockout_risk_tool)
        self.registry.register("score_suppliers_tool", self.score_suppliers_tool)
        self.registry.register("calculate_order_qty_tool", self.calculate_order_qty_tool)
        self.registry.register("create_po_tool", self.create_po_tool)
        self.registry.register("send_to_supplier_tool", self.send_to_supplier_tool)
        self.registry.register("track_delivery_tool", self.track_delivery_tool)

    def check_stockout_risk_tool(
        self,
        db: Session,
        risk_threshold: float,
        max_items: int,
    ) -> list[dict[str, Any]]:
        if not stockout_model.is_trained():
            return []

        raw_df = load_consumption_df(db)
        feat_df = build_stockout_features(raw_df)
        name_map = raw_df.groupby("item_id")["item_name"].first()
        feat_df["item_name"] = feat_df["item_id"].map(name_map)

        predicted = stockout_model.predict_all(feat_df)
        at_risk = [
            row
            for row in predicted.get("items", [])
            if float(row.get("risk_prob", 0.0)) >= float(risk_threshold)
        ]
        return at_risk[: max(1, int(max_items))]

    def score_suppliers_tool(
        self,
        db: Session,
        item_id: int,
        supplier_overrides: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return score_suppliers(db, item_id=item_id, supplier_overrides=supplier_overrides)

    def calculate_order_qty_tool(self, db: Session, item_id: int, risk_prob: float) -> int:
        item = db.query(Item).filter(Item.item_id == item_id).first()
        if item is None:
            return 1

        current_stock = (
            db.query(func.coalesce(func.sum(InventoryStock.current_quantity), 0))
            .filter(InventoryStock.item_id == item_id)
            .scalar()
        )
        current_stock = int(current_stock or 0)

        reorder = int(item.reorder_point or 10)
        safety = int(item.safety_stock_level or reorder)

        base_qty = max(1, reorder + safety - current_stock)
        if base_qty <= 1:
            base_qty = max(1, int(reorder * 0.5))

        multiplier = 1.0 + max(0.0, float(risk_prob) - 0.7) * 2.0
        qty = int(round(base_qty * multiplier))
        return max(1, qty)

    def create_po_tool(self, db: Session, supplier_id: int, status: str = "AUTO_CREATED") -> PurchaseOrder:
        supplier = db.query(Supplier).filter(Supplier.supplier_id == supplier_id).first()
        lead_days = int((supplier.avg_lead_time_days if supplier and supplier.avg_lead_time_days else 7) or 7)

        po = PurchaseOrder(
            supplier_id=supplier_id,
            order_date=date.today(),
            expected_delivery=date.today() + timedelta(days=max(1, lead_days)),
            status=status,
        )
        db.add(po)
        db.commit()
        db.refresh(po)
        return po

    def send_to_supplier_tool(self, db: Session, supplier_id: int, po_id: int) -> dict[str, Any]:
        supplier = db.query(Supplier).filter(Supplier.supplier_id == supplier_id).first()
        elapsed = max(1e-9, time.perf_counter() - started)

        return {
            "po_id": int(po_id),
            "supplier_id": int(supplier_id),
            "channel": "email" if supplier and supplier.contact_email else "log",
            "target": supplier.contact_email if supplier and supplier.contact_email else "supplier-not-configured",
            "status": "queued",
        }

    def track_delivery_tool(self, db: Session, po_id: int) -> dict[str, Any]:
        po = db.query(PurchaseOrder).filter(PurchaseOrder.po_id == po_id).first()
        if po is None:
            return {"po_id": int(po_id), "status": "unknown"}
        return {
            "po_id": int(po.po_id),
            "status": po.status,
            "expected_delivery": str(po.expected_delivery) if po.expected_delivery else None,
        }

    def execute(self, task: AgentTask, context: dict[str, Any] | None = None) -> dict[str, Any]:
        context = context or {}
        db: Session | None = context.get("db")
        if db is None:
            raise ValueError("SupplyChainAgent requires a DB session in context['db']")

        payload = task.payload or {}
        risk_threshold = float(payload.get("risk_threshold", 0.7))
        max_items = int(payload.get("max_items", 10))
        auto_purchase = bool(payload.get("auto_purchase", False))
        cadence_hours = max(1, int(payload.get("cadence_hours", 1)))
        supplier_overrides = payload.get("supplier_overrides") or {}

        started = time.perf_counter()

        at_risk_items = self.registry.execute(
            "check_stockout_risk_tool",
            db,
            risk_threshold,
            max_items,
        )

        decisions: list[dict[str, Any]] = []
        for entry in at_risk_items:
            item_id = int(entry["item_id"])
            item_name = entry.get("item_name", str(item_id))
            risk_prob = float(entry.get("risk_prob", 0.0))

            scored = self.registry.execute(
                "score_suppliers_tool",
                db,
                item_id,
                supplier_overrides.get(item_id) or supplier_overrides.get(str(item_id)) or [],
            )
            ranked_suppliers = scored.get("suppliers", [])
            if not ranked_suppliers:
                continue

            top_supplier = ranked_suppliers[0]
            order_qty = self.registry.execute(
                "calculate_order_qty_tool",
                db,
                item_id,
                risk_prob,
            )

            decision = {
                "item_id": item_id,
                "item_name": item_name,
                "risk_prob": round(risk_prob, 3),
                "recommended_supplier": {
                    "supplier_id": top_supplier["supplier_id"],
                    "supplier_name": top_supplier["supplier_name"],
                    "score": top_supplier["score"],
                    "breakdown": top_supplier.get("breakdown", {}),
                },
                "recommended_order_qty": int(order_qty),
                "reason": (
                    f"risk={risk_prob:.3f}, supplier_score={top_supplier['score']}, "
                    f"rank=1 among {len(ranked_suppliers)}"
                ),
                "created_po": None,
                "dispatch": None,
                "tracking": None,
            }

            if auto_purchase:
                po = self.registry.execute("create_po_tool", db, int(top_supplier["supplier_id"]))
                dispatch = self.registry.execute("send_to_supplier_tool", db, int(top_supplier["supplier_id"]), int(po.po_id))
                tracking = self.registry.execute("track_delivery_tool", db, int(po.po_id))
                decision["created_po"] = {
                    "po_id": int(po.po_id),
                    "supplier_id": int(po.supplier_id) if po.supplier_id else None,
                    "order_date": str(po.order_date) if po.order_date else None,
                    "expected_delivery": str(po.expected_delivery) if po.expected_delivery else None,
                    "status": po.status,
                }
                decision["dispatch"] = dispatch
                decision["tracking"] = tracking

            decisions.append(decision)

        elapsed = max(1e-9, time.perf_counter() - started)

        return {
            "risk_threshold": risk_threshold,
            "auto_purchase": auto_purchase,
            "cadence_hours": cadence_hours,
            "items_evaluated": len(at_risk_items),
            "decisions": decisions,
            "llm_model": self.settings.ollama_model,
            "llm_ready": self.llm is not None,
            "cycle_duration_sec": round(elapsed, 3),
            "performance_target_sec": 30.0,
            "sla_under_30s": elapsed < 30.0,
        }
