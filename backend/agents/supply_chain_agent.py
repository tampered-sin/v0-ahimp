"""Supply chain agent for stockout monitoring and auto-purchase orchestration."""
from __future__ import annotations

from datetime import date, timedelta
from datetime import datetime, timezone
from difflib import SequenceMatcher
import os
import time
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from agents.config import AgentTask, BaseAgent, build_crewai_llm
from agents.supplier_scoring import score_suppliers
from data.feature_engineering import build_stockout_features, load_consumption_df
from database.escalations import create_escalation_log
from database.models import Batch, InventoryStock, Item, PurchaseOrder, Supplier
from models import stockout_model
from services.notifications import send_anomaly_alert


AUTO_ORDER_THRESHOLD = 0.75
SUGGEST_THRESHOLD = 0.50

MEDICINE_ALIASES = {
    "paracetamol": ["acetaminophen"],
    "acetaminophen": ["paracetamol"],
    "adrenaline": ["epinephrine"],
    "epinephrine": ["adrenaline"],
}


def build_supply_chain_payload(
    risk_threshold: float = 0.7,
    max_items: int = 10,
    auto_purchase: bool = False,
    cadence_hours: int = 1,
    supplier_overrides: dict[int, list[dict[str, Any]]] | None = None,
    critical_item_ids: list[int] | None = None,
    critical_categories: list[str] | None = None,
    search_location: str | None = None,
    max_distance_km: float = 50.0,
    min_supplier_reliability: float = 0.60,
) -> dict[str, Any]:
    return {
        "risk_threshold": risk_threshold,
        "max_items": max_items,
        "auto_purchase": auto_purchase,
        "cadence_hours": max(1, int(cadence_hours)),
        "supplier_overrides": supplier_overrides or {},
        "critical_item_ids": [int(v) for v in (critical_item_ids or [])],
        "critical_categories": [str(v).strip().lower() for v in (critical_categories or []) if str(v).strip()],
        "search_location": (search_location or "").strip() or None,
        "max_distance_km": float(max_distance_km),
        "min_supplier_reliability": float(min_supplier_reliability),
    }


class SupplyChainAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="supply-chain-agent")
        self.llm = build_crewai_llm(self.settings)
        self.registry.register("check_stockout_risk_tool", self.check_stockout_risk_tool)
        self.registry.register("search_suppliers_tool", self.search_suppliers_tool)
        self.registry.register("score_suppliers_tool", self.score_suppliers_tool)
        self.registry.register("compare_quotes_tool", self.compare_quotes_tool)
        self.registry.register("decide_order_action_tool", self.decide_order_action_tool)
        self.registry.register("build_dual_source_plan_tool", self.build_dual_source_plan_tool)
        self.registry.register("escalate_to_human_tool", self.escalate_to_human_tool)
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

    def _normalize_medicine_name(self, value: str) -> str:
        return " ".join(str(value or "").strip().lower().split())

    def _candidate_terms(self, medicine_name: str) -> list[str]:
        normalized = self._normalize_medicine_name(medicine_name)
        terms = [normalized]
        terms.extend(MEDICINE_ALIASES.get(normalized, []))
        return [term for term in terms if term]

    def _fuzzy_threshold(self) -> float:
        try:
            raw = float(os.getenv("MEDICINE_FUZZY_THRESHOLD", "0.60"))
        except Exception:
            raw = 0.60
        return max(0.0, min(1.0, raw))

    def search_suppliers_tool(
        self,
        db: Session,
        medicine_name: str,
        quantity: int,
        location: str | None = None,
        max_distance_km: float = 50.0,
        min_reliability: float = 0.60,
        supplier_overrides: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        terms = self._candidate_terms(medicine_name)
        threshold = self._fuzzy_threshold()
        quantity = max(1, int(quantity))

        items = db.query(Item).all()
        ranked_items: list[tuple[Item, float]] = []
        for item in items:
            name = self._normalize_medicine_name(item.item_name)
            best = 0.0
            for term in terms:
                if not term:
                    continue
                if term in name or name in term:
                    best = max(best, 1.0)
                else:
                    best = max(best, SequenceMatcher(None, term, name).ratio())
            if best >= threshold:
                ranked_items.append((item, best))

        ranked_items.sort(key=lambda row: (-row[1], int(row[0].item_id)))
        if not ranked_items:
            return []

        target_item = ranked_items[0][0]
        target_item_id = int(target_item.item_id)

        override_map = {
            int(row.get("supplier_id")): row
            for row in (supplier_overrides or [])
            if row.get("supplier_id") is not None
        }

        suppliers = db.query(Supplier).order_by(Supplier.supplier_id.asc()).all()
        output: list[dict[str, Any]] = []
        for supplier in suppliers:
            supplier_id = int(supplier.supplier_id)
            reliability_score = float(supplier.reliability_score or 0.0)
            if reliability_score < float(min_reliability):
                continue

            avg_price = (
                db.query(func.avg(Batch.purchase_price))
                .filter(Batch.item_id == target_item_id, Batch.supplier_id == supplier_id)
                .scalar()
            )
            if avg_price is None:
                continue

            stock_available = (
                db.query(func.coalesce(func.sum(InventoryStock.current_quantity), 0))
                .join(Batch, InventoryStock.batch_id == Batch.batch_id)
                .filter(Batch.item_id == target_item_id, Batch.supplier_id == supplier_id)
                .scalar()
            )
            stock_available = int(stock_available or 0)

            overrides = override_map.get(supplier_id, {})
            distance_km = overrides.get("distance_km")
            if distance_km is not None and float(distance_km) > float(max_distance_km):
                continue

            lead_hours = max(1.0, float(supplier.avg_lead_time_days or 7) * 24.0)
            delivery_speed = max(0.0, min(1.0, 1.0 - (lead_hours / (7.0 * 24.0))))
            stock_ratio = max(0.0, min(1.0, float(stock_available) / float(quantity)))
            composite = 0.5 * reliability_score + 0.3 * stock_ratio + 0.2 * delivery_speed

            output.append(
                {
                    "supplier_id": supplier_id,
                    "name": supplier.supplier_name,
                    "reliability_score": round(reliability_score, 4),
                    "stock_available": stock_available,
                    "price_per_unit": round(float(avg_price), 4),
                    "estimated_delivery_hours": int(round(lead_hours)),
                    "distance_km": float(distance_km) if distance_km is not None else None,
                    "last_verified": datetime.now(tz=timezone.utc).isoformat(),
                    "location": location,
                    "item_id": target_item_id,
                    "item_name": target_item.item_name,
                    "search_score": round(composite, 4),
                }
            )

        output.sort(key=lambda row: (-float(row["search_score"]), int(row["supplier_id"])))
        return output

    def compare_quotes_tool(self, ranked_suppliers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        compared: list[dict[str, Any]] = []
        for supplier in ranked_suppliers:
            breakdown = supplier.get("breakdown", {})
            reliability = float(breakdown.get("reliability", 0.0)) / 100.0
            price_score = float(breakdown.get("price_competitiveness", 0.0)) / 100.0
            delivery_score = float(breakdown.get("on_time_delivery", 0.0)) / 100.0

            composite_score = (
                reliability * 0.6
                + price_score * 0.3
                + delivery_score * 0.1
            )

            compared.append(
                {
                    **supplier,
                    "decision_metrics": {
                        "reliability": round(reliability, 4),
                        "price_score": round(price_score, 4),
                        "delivery_score": round(delivery_score, 4),
                        "composite_score": round(composite_score, 4),
                    },
                }
            )

        compared.sort(
            key=lambda row: (
                -float(row.get("decision_metrics", {}).get("composite_score", 0.0)),
                int(row.get("supplier_id", 0)),
            )
        )
        return compared

    def decide_order_action_tool(self, composite_score: float, is_critical: bool) -> str:
        score = float(composite_score)
        if score >= AUTO_ORDER_THRESHOLD and not is_critical:
            return "AUTO_ORDER"
        if score >= SUGGEST_THRESHOLD:
            return "SUGGEST_HUMAN_APPROVAL"
        return "ESCALATE"

    def build_dual_source_plan_tool(
        self,
        compared_suppliers: list[dict[str, Any]],
        total_quantity: int,
    ) -> dict[str, Any] | None:
        if len(compared_suppliers) < 2:
            return None

        qty = max(1, int(total_quantity))
        primary_qty = max(1, int(round(qty * 0.6)))
        secondary_qty = max(1, qty - primary_qty)

        primary = compared_suppliers[0]
        secondary = compared_suppliers[1]

        return {
            "strategy": "DUAL_SOURCE",
            "split": {"primary_pct": 60, "secondary_pct": 40},
            "orders": [
                {
                    "supplier_id": int(primary["supplier_id"]),
                    "supplier_name": primary.get("supplier_name"),
                    "quantity": primary_qty,
                    "decision_score": float(primary.get("decision_metrics", {}).get("composite_score", 0.0)),
                },
                {
                    "supplier_id": int(secondary["supplier_id"]),
                    "supplier_name": secondary.get("supplier_name"),
                    "quantity": secondary_qty,
                    "decision_score": float(secondary.get("decision_metrics", {}).get("composite_score", 0.0)),
                },
            ],
        }

    def _is_item_critical(
        self,
        db: Session,
        item_id: int,
        critical_item_ids: set[int],
        critical_categories: set[str],
    ) -> bool:
        if item_id in critical_item_ids:
            return True

        if not critical_categories:
            return False

        item = db.query(Item).filter(Item.item_id == item_id).first()
        if item is None:
            return False
        category = str(item.category or "").strip().lower()
        return category in critical_categories

    def escalate_to_human_tool(
        self,
        db: Session,
        *,
        reason: str,
        medicine: str,
        quantity_needed: int,
        stockout_risk: float,
        days_until_stockout: int,
        suppliers_evaluated: list[dict[str, Any]] | None = None,
        recommended_action: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        priority = "CRITICAL" if int(days_until_stockout) <= 1 or float(stockout_risk) >= 0.9 else "HIGH"
        escalation = create_escalation_log(
            db,
            triggered_by=self.name,
            reason=reason,
            medicine=medicine,
            quantity_needed=max(1, int(quantity_needed)),
            stockout_risk=float(stockout_risk),
            days_until_stockout=max(1, int(days_until_stockout)),
            suppliers_evaluated=suppliers_evaluated or [],
            recommended_action=recommended_action,
            priority=priority,
            context=context or {},
        )

        alert = send_anomaly_alert(
            subject=f"Supply-chain escalation: {medicine}",
            body=(
                f"Escalation ID: {escalation['escalation_id']}\n"
                f"Medicine: {medicine}\n"
                f"Reason: {reason}\n"
                f"Stockout risk: {float(stockout_risk):.3f}\n"
                f"Days until stockout: {int(days_until_stockout)}\n"
                f"Recommended action: {recommended_action}"
            ),
            severity="RED" if priority == "CRITICAL" else "YELLOW",
        )

        return {
            "escalation": escalation,
            "alert": alert,
        }

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
        critical_item_ids = {int(v) for v in (payload.get("critical_item_ids") or [])}
        critical_categories = {str(v).strip().lower() for v in (payload.get("critical_categories") or []) if str(v).strip()}
        search_location = payload.get("search_location")
        max_distance_km = float(payload.get("max_distance_km", 50.0))
        min_supplier_reliability = float(payload.get("min_supplier_reliability", 0.60))

        started = time.perf_counter()

        at_risk_items = self.registry.execute(
            "check_stockout_risk_tool",
            db,
            risk_threshold,
            max_items,
        )

        decisions: list[dict[str, Any]] = []
        escalations: list[dict[str, Any]] = []
        for entry in at_risk_items:
            item_id = int(entry["item_id"])
            item_name = entry.get("item_name", str(item_id))
            risk_prob = float(entry.get("risk_prob", 0.0))
            days_until_stockout = max(1, int(round(float(entry.get("days_until_stockout", max(1.0, (1.0 - risk_prob) * 14.0))))))
            is_critical = self._is_item_critical(
                db,
                item_id=item_id,
                critical_item_ids=critical_item_ids,
                critical_categories=critical_categories,
            )

            precomputed_qty = self.registry.execute(
                "calculate_order_qty_tool",
                db,
                item_id,
                risk_prob,
            )

            supplier_search_results = self.registry.execute(
                "search_suppliers_tool",
                db,
                item_name,
                int(precomputed_qty),
                search_location,
                max_distance_km,
                min_supplier_reliability,
                supplier_overrides.get(item_id) or supplier_overrides.get(str(item_id)) or [],
            )
            if not supplier_search_results:
                escalation_result = self.registry.execute(
                    "escalate_to_human_tool",
                    db,
                    reason="No suppliers matched medicine/reliability/distance filters",
                    medicine=item_name,
                    quantity_needed=max(1, int(precomputed_qty)),
                    stockout_risk=risk_prob,
                    days_until_stockout=days_until_stockout,
                    suppliers_evaluated=[],
                    recommended_action="Relax supplier filters or perform manual vendor outreach",
                    context={
                        "item_id": item_id,
                        "location": search_location,
                        "max_distance_km": max_distance_km,
                        "min_supplier_reliability": min_supplier_reliability,
                    },
                )
                escalations.append(
                    {
                        "item_id": item_id,
                        "item_name": item_name,
                        "risk_prob": round(risk_prob, 3),
                        "days_until_stockout": days_until_stockout,
                        "reason": "No suppliers matched medicine/reliability/distance filters",
                        "action": "ESCALATE",
                        "is_critical": is_critical,
                        "ticket": escalation_result.get("escalation"),
                        "alert": escalation_result.get("alert"),
                    }
                )
                continue

            scored = self.registry.execute(
                "score_suppliers_tool",
                db,
                item_id,
                supplier_overrides.get(item_id) or supplier_overrides.get(str(item_id)) or [],
            )
            allowed_supplier_ids = {int(row["supplier_id"]) for row in supplier_search_results}
            ranked_suppliers = [
                row
                for row in scored.get("suppliers", [])
                if int(row.get("supplier_id", 0)) in allowed_supplier_ids
            ]
            if not ranked_suppliers:
                escalation_result = self.registry.execute(
                    "escalate_to_human_tool",
                    db,
                    reason="No suppliers available above scoring thresholds",
                    medicine=item_name,
                    quantity_needed=max(1, int(precomputed_qty)),
                    stockout_risk=risk_prob,
                    days_until_stockout=days_until_stockout,
                    suppliers_evaluated=supplier_search_results,
                    recommended_action="Manual procurement outreach required",
                    context={
                        "item_id": item_id,
                        "is_critical": is_critical,
                    },
                )
                escalations.append(
                    {
                        "item_id": item_id,
                        "item_name": item_name,
                        "risk_prob": round(risk_prob, 3),
                        "days_until_stockout": days_until_stockout,
                        "reason": "No suppliers available above scoring thresholds",
                        "action": "ESCALATE",
                        "is_critical": is_critical,
                        "ticket": escalation_result.get("escalation"),
                        "alert": escalation_result.get("alert"),
                    }
                )
                continue

            compared_suppliers = self.registry.execute("compare_quotes_tool", ranked_suppliers)
            top_supplier = compared_suppliers[0]
            composite_score = float(top_supplier.get("decision_metrics", {}).get("composite_score", 0.0))
            action = self.registry.execute("decide_order_action_tool", composite_score, is_critical)

            order_qty = int(precomputed_qty)
            dual_source_plan = None
            if is_critical:
                dual_source_plan = self.registry.execute(
                    "build_dual_source_plan_tool",
                    compared_suppliers,
                    order_qty,
                )

            decision = {
                "item_id": item_id,
                "item_name": item_name,
                "risk_prob": round(risk_prob, 3),
                "days_until_stockout": days_until_stockout,
                "recommended_supplier": {
                    "supplier_id": top_supplier["supplier_id"],
                    "supplier_name": top_supplier["supplier_name"],
                    "score": top_supplier["score"],
                    "breakdown": top_supplier.get("breakdown", {}),
                    "decision_metrics": top_supplier.get("decision_metrics", {}),
                },
                "candidate_suppliers": compared_suppliers[:3],
                "supplier_search_results": supplier_search_results[:5],
                "recommended_order_qty": int(order_qty),
                "action": action,
                "is_critical": is_critical,
                "reason": (
                    f"risk={risk_prob:.3f}, decision_score={composite_score:.3f}, "
                    f"supplier_score={top_supplier['score']}, rank=1 among {len(ranked_suppliers)}"
                ),
                "created_po": None,
                "dispatch": None,
                "tracking": None,
                "dual_source_plan": dual_source_plan,
            }

            if auto_purchase and action == "AUTO_ORDER":
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
            elif action == "ESCALATE":
                escalation_result = self.registry.execute(
                    "escalate_to_human_tool",
                    db,
                    reason=decision["reason"],
                    medicine=item_name,
                    quantity_needed=int(order_qty),
                    stockout_risk=risk_prob,
                    days_until_stockout=days_until_stockout,
                    suppliers_evaluated=compared_suppliers[:3],
                    recommended_action="Review top suppliers and approve manual procurement",
                    context={
                        "item_id": item_id,
                        "recommended_supplier_id": int(top_supplier["supplier_id"]),
                        "is_critical": is_critical,
                        "decision_metrics": top_supplier.get("decision_metrics", {}),
                        "dual_source_plan": dual_source_plan,
                    },
                )
                escalations.append(
                    {
                        "item_id": item_id,
                        "item_name": item_name,
                        "risk_prob": round(risk_prob, 3),
                        "days_until_stockout": days_until_stockout,
                        "reason": decision["reason"],
                        "action": action,
                        "is_critical": is_critical,
                        "ticket": escalation_result.get("escalation"),
                        "alert": escalation_result.get("alert"),
                    }
                )

            decisions.append(decision)

        elapsed = max(1e-9, time.perf_counter() - started)

        return {
            "risk_threshold": risk_threshold,
            "auto_purchase": auto_purchase,
            "cadence_hours": cadence_hours,
            "items_evaluated": len(at_risk_items),
            "decisions": decisions,
            "escalations": escalations,
            "llm_model": self.settings.ollama_model,
            "llm_ready": self.llm is not None,
            "cycle_duration_sec": round(elapsed, 3),
            "performance_target_sec": 30.0,
            "sla_under_30s": elapsed < 30.0,
        }
