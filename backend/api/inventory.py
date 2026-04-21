"""FastAPI routes for operational inventory snapshot data used by frontend pages."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.db import get_db
from database.models import (
    Batch,
    Department,
    InventoryStock,
    Item,
    PurchaseOrder,
    PurchaseOrderDetail,
    ConsumptionRecord,
    Supplier,
)

router = APIRouter()


def _parse_prefixed_id(value: str, prefix: str) -> int:
    cleaned = value.strip()
    if cleaned.startswith(prefix):
        cleaned = cleaned[len(prefix):]
    return int(cleaned)


class InventoryItemIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    category: str = Field(..., min_length=1, max_length=100)
    sku: str = Field(..., min_length=1, max_length=100)
    quantity: int = Field(..., ge=0)
    unit: str = Field(..., min_length=1, max_length=50)
    reorderLevel: int = Field(..., ge=0)
    unitPrice: float = Field(..., ge=0)
    supplierId: str = Field(..., min_length=1)
    departmentId: str = Field(..., min_length=1)
    batchNumber: str = Field(..., min_length=1, max_length=120)
    expiryDate: str = Field(..., min_length=1)
    location: str = Field(default="", max_length=200)
    notes: str = Field(default="", max_length=1000)


class SupplierIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    contact: str = Field(default="Procurement Desk", max_length=100)
    email: str = Field(default="", max_length=150)
    phone: str = Field(default="", max_length=20)
    address: str = Field(default="On file", max_length=200)
    rating: float = Field(default=4.0, ge=1.0, le=5.0)
    itemsSupplied: int = Field(default=0, ge=0)


class PurchaseOrderItemIn(BaseModel):
    itemId: str = Field(..., min_length=1)
    quantity: int = Field(..., ge=1)
    unitPrice: float = Field(..., ge=0)


class PurchaseOrderIn(BaseModel):
    supplierId: str = Field(..., min_length=1)
    items: list[PurchaseOrderItemIn] = Field(..., min_length=1)
    orderDate: str = Field(..., min_length=1)
    expectedDelivery: str = Field(..., min_length=1)


class PurchaseOrderStatusIn(BaseModel):
    status: str = Field(..., min_length=2, max_length=50)


def _stock_status(quantity: int, reorder_level: int, expiry_date: date | None) -> str:
    today = date.today()
    if expiry_date is not None and expiry_date < today:
        return "Expired"
    if quantity <= 0:
        return "Out of Stock"
    if quantity <= max(0, reorder_level):
        return "Low Stock"
    return "In Stock"


def _pretty_po_status(status: str | None) -> str:
    normalized = (status or "PENDING").strip().upper()
    mapping = {
        "PENDING": "Pending",
        "APPROVED": "Approved",
        "SHIPPED": "Shipped",
        "DELIVERED": "Delivered",
        "DELIVERED_LATE": "Delivered",
        "CANCELLED": "Cancelled",
        "AUTO_CREATED": "Pending",
    }
    return mapping.get(normalized, normalized.title())


def _db_po_status(status: str) -> str:
    normalized = status.strip().upper().replace(" ", "_")
    mapping = {
        "PENDING": "PENDING",
        "APPROVED": "APPROVED",
        "SHIPPED": "SHIPPED",
        "DELIVERED": "DELIVERED",
        "CANCELLED": "CANCELLED",
    }
    return mapping.get(normalized, normalized)


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _add_months(start: date, months: int) -> date:
    year = start.year + (start.month - 1 + months) // 12
    month = (start.month - 1 + months) % 12 + 1
    return date(year, month, 1)


@router.get("/inventory/snapshot")
def inventory_snapshot(db: Session = Depends(get_db)) -> dict[str, Any]:
    departments = db.query(Department).all()
    suppliers = db.query(Supplier).all()

    item_rows = (
        db.query(Item, InventoryStock, Batch)
        .join(InventoryStock, Item.item_id == InventoryStock.item_id)
        .join(Batch, InventoryStock.batch_id == Batch.batch_id)
        .all()
    )

    item_map: dict[int, dict[str, Any]] = {}
    dept_value_map: dict[int, float] = {}

    for item, stock, batch in item_rows:
        existing = item_map.get(item.item_id)
        if existing is None:
            existing = {
                "id": f"i{item.item_id}",
                "name": item.item_name,
                "category": item.category or "Medicines",
                "sku": f"SKU-{item.item_id:05d}",
                "quantity": 0,
                "unit": item.unit_type or "Units",
                "reorderLevel": int(item.reorder_point or 0),
                "unitPrice": float(batch.purchase_price or 0.0),
                "supplierId": f"s{batch.supplier_id}",
                "departmentId": f"d{stock.department_id}",
                "batchNumber": f"B-{batch.batch_id:06d}",
                "expiryDate": "N/A" if batch.expiry_date is None else batch.expiry_date.isoformat(),
                "location": "",
                "status": "In Stock",
                "lastRestocked": (stock.last_updated.date().isoformat() if stock.last_updated else date.today().isoformat()),
                "notes": "",
            }
            item_map[item.item_id] = existing

        existing["quantity"] += int(stock.current_quantity or 0)

        # Prefer the most recent stock update as latest restock timestamp.
        stock_updated = stock.last_updated.date().isoformat() if stock.last_updated else None
        if stock_updated and stock_updated > str(existing["lastRestocked"]):
            existing["lastRestocked"] = stock_updated
            existing["unitPrice"] = float(batch.purchase_price or existing["unitPrice"])
            existing["supplierId"] = f"s{batch.supplier_id}"
            existing["departmentId"] = f"d{stock.department_id}"
            existing["batchNumber"] = f"B-{batch.batch_id:06d}"
            existing["expiryDate"] = "N/A" if batch.expiry_date is None else batch.expiry_date.isoformat()

        dept_value_map[stock.department_id] = dept_value_map.get(stock.department_id, 0.0) + (
            float(stock.current_quantity or 0) * float(batch.purchase_price or 0.0)
        )

    dept_lookup = {d.department_id: d for d in departments}
    for payload in item_map.values():
        dept_id = int(str(payload["departmentId"])[1:])
        dept = dept_lookup.get(dept_id)
        payload["location"] = (dept.location if dept and dept.location else "General Store")
        expiry = None if payload["expiryDate"] == "N/A" else date.fromisoformat(str(payload["expiryDate"]))
        payload["status"] = _stock_status(int(payload["quantity"]), int(payload["reorderLevel"]), expiry)

    items = sorted(item_map.values(), key=lambda row: row["name"])

    supplier_item_counts: dict[int, int] = {}
    for item in items:
        supplier_id = int(str(item["supplierId"])[1:])
        supplier_item_counts[supplier_id] = supplier_item_counts.get(supplier_id, 0) + 1

    suppliers_payload = []
    for supplier in suppliers:
        suppliers_payload.append(
            {
                "id": f"s{supplier.supplier_id}",
                "name": supplier.supplier_name,
                "contact": "Procurement Desk",
                "email": supplier.contact_email or "",
                "phone": supplier.contact_phone or "",
                "address": "On file",
                "rating": round(float((supplier.reliability_score or 0.85) * 5), 1),
                "itemsSupplied": supplier_item_counts.get(supplier.supplier_id, 0),
            }
        )

    departments_payload = []
    for dept in departments:
        inv_value = float(dept_value_map.get(dept.department_id, 0.0))
        budget = max(50000.0, inv_value * 1.4)
        spent = min(budget, inv_value * 0.72)
        departments_payload.append(
            {
                "id": f"d{dept.department_id}",
                "name": dept.department_name,
                "head": "Unassigned",
                "budget": round(budget, 2),
                "spent": round(spent, 2),
            }
        )

    po_rows = (
        db.query(PurchaseOrder, PurchaseOrderDetail)
        .outerjoin(PurchaseOrderDetail, PurchaseOrder.po_id == PurchaseOrderDetail.po_id)
        .order_by(PurchaseOrder.po_id.desc())
        .all()
    )

    po_map: dict[int, dict[str, Any]] = {}
    item_name_lookup = {int(str(item["id"])[1:]): item["name"] for item in items}

    for po, detail in po_rows:
        payload = po_map.get(po.po_id)
        if payload is None:
            payload = {
                "id": f"po{po.po_id}",
                "supplierId": f"s{po.supplier_id}" if po.supplier_id else "",
                "items": [],
                "status": _pretty_po_status(po.status),
                "orderDate": po.order_date.isoformat() if po.order_date else date.today().isoformat(),
                "expectedDelivery": po.expected_delivery.isoformat() if po.expected_delivery else date.today().isoformat(),
                "totalAmount": 0.0,
            }
            po_map[po.po_id] = payload

        if detail is not None:
            subtotal = float(detail.total_cost or (detail.quantity or 0) * (detail.unit_price or 0.0))
            payload["items"].append(
                {
                    "itemId": f"i{detail.item_id}",
                    "itemName": item_name_lookup.get(detail.item_id, f"Item {detail.item_id}"),
                    "quantity": int(detail.quantity or 0),
                    "unitPrice": float(detail.unit_price or 0.0),
                }
            )
            payload["totalAmount"] += subtotal

    purchase_orders = sorted(po_map.values(), key=lambda row: row["orderDate"], reverse=True)

    alerts: list[dict[str, Any]] = []
    today = date.today()

    for item in items:
        qty = int(item["quantity"])
        reorder = int(item["reorderLevel"])
        status = item["status"]

        if status in {"Out of Stock", "Low Stock"}:
            severity = "Critical" if status == "Out of Stock" else "Warning"
            alerts.append(
                {
                    "id": f"alert-stock-{item['id']}",
                    "type": "Low Stock",
                    "severity": severity,
                    "message": f"{item['name']} stock is {status.lower()} ({qty}/{reorder}).",
                    "itemId": item["id"],
                    "timestamp": f"{today.isoformat()}T08:00:00Z",
                    "acknowledged": False,
                }
            )

        expiry_raw = item["expiryDate"]
        if expiry_raw != "N/A":
            expiry = date.fromisoformat(str(expiry_raw))
            days_left = (expiry - today).days
            if days_left < 0:
                alerts.append(
                    {
                        "id": f"alert-expired-{item['id']}",
                        "type": "Expired",
                        "severity": "Critical",
                        "message": f"{item['name']} has expired.",
                        "itemId": item["id"],
                        "timestamp": f"{today.isoformat()}T06:00:00Z",
                        "acknowledged": False,
                    }
                )
            elif days_left <= 30:
                alerts.append(
                    {
                        "id": f"alert-expiring-{item['id']}",
                        "type": "Expiring Soon",
                        "severity": "Warning",
                        "message": f"{item['name']} expires in {days_left} day(s).",
                        "itemId": item["id"],
                        "timestamp": f"{today.isoformat()}T06:30:00Z",
                        "acknowledged": False,
                    }
                )

    for order in purchase_orders[:20]:
        if order["status"] in {"Pending", "Approved", "Shipped"}:
            alerts.append(
                {
                    "id": f"alert-po-{order['id']}",
                    "type": "Order Update",
                    "severity": "Info",
                    "message": f"{order['id'].upper()} is currently {order['status'].lower()}.",
                    "timestamp": f"{today.isoformat()}T10:00:00Z",
                    "acknowledged": False,
                }
            )

    alerts = alerts[:200]

    activity_logs = []
    for order in purchase_orders[:20]:
        activity_logs.append(
            {
                "id": f"log-{order['id']}",
                "action": "Purchase Order Updated",
                "userId": "u1",
                "timestamp": f"{today.isoformat()}T11:00:00Z",
                "details": f"{order['id'].upper()} status: {order['status']}.",
            }
        )

    return {
        "items": items,
        "suppliers": sorted(suppliers_payload, key=lambda row: row["name"]),
        "departments": sorted(departments_payload, key=lambda row: row["name"]),
        "purchaseOrders": purchase_orders,
        "alerts": alerts,
        "activityLogs": activity_logs,
    }


@router.get("/inventory/monthly-trend")
def inventory_monthly_trend(months: int = 6, db: Session = Depends(get_db)) -> dict[str, Any]:
    months = max(3, min(months, 24))

    end_month = _month_start(date.today())
    start_month = _add_months(end_month, -(months - 1))
    next_month = _add_months(end_month, 1)

    month_keys: list[str] = []
    month_labels: dict[str, str] = {}
    for idx in range(months):
        current = _add_months(start_month, idx)
        key = current.strftime("%Y-%m")
        month_keys.append(key)
        month_labels[key] = current.strftime("%b")

    consumption_totals = {key: 0.0 for key in month_keys}
    restocked_totals = {key: 0.0 for key in month_keys}

    consumption_rows = (
        db.query(ConsumptionRecord.usage_date, ConsumptionRecord.quantity_used, Batch.purchase_price)
        .outerjoin(Batch, ConsumptionRecord.batch_id == Batch.batch_id)
        .filter(ConsumptionRecord.usage_date >= start_month)
        .filter(ConsumptionRecord.usage_date < next_month)
        .all()
    )
    for usage_date, quantity_used, purchase_price in consumption_rows:
        if usage_date is None:
            continue
        key = usage_date.strftime("%Y-%m")
        if key not in consumption_totals:
            continue
        qty = float(quantity_used or 0)
        price = float(purchase_price or 0.0)
        consumption_totals[key] += qty * price

    restocked_rows = (
        db.query(PurchaseOrder.order_date, PurchaseOrderDetail.total_cost)
        .join(PurchaseOrderDetail, PurchaseOrder.po_id == PurchaseOrderDetail.po_id)
        .filter(PurchaseOrder.order_date >= start_month)
        .filter(PurchaseOrder.order_date < next_month)
        .all()
    )
    for order_date, total_cost in restocked_rows:
        if order_date is None:
            continue
        key = order_date.strftime("%Y-%m")
        if key not in restocked_totals:
            continue
        restocked_totals[key] += float(total_cost or 0.0)

    points = [
        {
            "month": month_labels[key],
            "consumption": round(consumption_totals[key], 2),
            "restocked": round(restocked_totals[key], 2),
        }
        for key in month_keys
    ]
    return {"months": months, "points": points}


@router.post("/inventory/items")
def create_inventory_item(payload: InventoryItemIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        supplier_id = _parse_prefixed_id(payload.supplierId, "s")
        department_id = _parse_prefixed_id(payload.departmentId, "d")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid supplier/department id format: {exc}") from exc

    supplier = db.query(Supplier).filter(Supplier.supplier_id == supplier_id).first()
    department = db.query(Department).filter(Department.department_id == department_id).first()
    if supplier is None:
        raise HTTPException(status_code=404, detail=f"Supplier {payload.supplierId} not found")
    if department is None:
        raise HTTPException(status_code=404, detail=f"Department {payload.departmentId} not found")

    item = Item(
        item_name=payload.name,
        category=payload.category,
        unit_type=payload.unit,
        safety_stock_level=max(0, int(payload.reorderLevel * 0.7)),
        reorder_point=payload.reorderLevel,
    )
    db.add(item)
    db.flush()

    expiry = None if payload.expiryDate == "N/A" else date.fromisoformat(payload.expiryDate)
    batch = Batch(
        item_id=item.item_id,
        supplier_id=supplier_id,
        manufacture_date=date.today(),
        expiry_date=expiry,
        purchase_price=payload.unitPrice,
        quantity_received=payload.quantity,
    )
    db.add(batch)
    db.flush()

    stock = InventoryStock(
        item_id=item.item_id,
        batch_id=batch.batch_id,
        department_id=department_id,
        current_quantity=payload.quantity,
    )
    db.add(stock)
    db.commit()

    return {"ok": True, "itemId": f"i{item.item_id}"}


@router.put("/inventory/items/{item_id}")
def update_inventory_item(item_id: str, payload: InventoryItemIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    item_pk = _parse_prefixed_id(item_id, "i")
    supplier_id = _parse_prefixed_id(payload.supplierId, "s")
    department_id = _parse_prefixed_id(payload.departmentId, "d")

    item = db.query(Item).filter(Item.item_id == item_pk).first()
    if item is None:
        return {"ok": False, "error": "Item not found"}

    latest_row = (
        db.query(InventoryStock, Batch)
        .join(Batch, InventoryStock.batch_id == Batch.batch_id)
        .filter(InventoryStock.item_id == item_pk)
        .order_by(InventoryStock.last_updated.desc())
        .first()
    )
    if latest_row is None:
        return {"ok": False, "error": "Inventory stock row not found for item"}

    stock, batch = latest_row
    item.item_name = payload.name
    item.category = payload.category
    item.unit_type = payload.unit
    item.reorder_point = payload.reorderLevel
    item.safety_stock_level = max(0, int(payload.reorderLevel * 0.7))

    stock.current_quantity = payload.quantity
    stock.department_id = department_id
    batch.supplier_id = supplier_id
    batch.purchase_price = payload.unitPrice
    batch.expiry_date = None if payload.expiryDate == "N/A" else date.fromisoformat(payload.expiryDate)

    db.commit()
    return {"ok": True}


@router.delete("/inventory/items/{item_id}")
def delete_inventory_item(item_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    item_pk = _parse_prefixed_id(item_id, "i")

    has_usage = db.query(ConsumptionRecord).filter(ConsumptionRecord.item_id == item_pk).first()
    if has_usage is not None:
        return {"ok": False, "error": "Item has historical consumption records and cannot be deleted"}

    stock_rows = db.query(InventoryStock).filter(InventoryStock.item_id == item_pk).all()
    batch_rows = db.query(Batch).filter(Batch.item_id == item_pk).all()
    item = db.query(Item).filter(Item.item_id == item_pk).first()

    if item is None:
        return {"ok": False, "error": "Item not found"}

    for row in stock_rows:
        db.delete(row)
    for row in batch_rows:
        db.delete(row)
    db.delete(item)
    db.commit()
    return {"ok": True}


@router.post("/inventory/suppliers")
def create_supplier(payload: SupplierIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    supplier = Supplier(
        supplier_name=payload.name,
        contact_email=payload.email,
        contact_phone=payload.phone,
        avg_lead_time_days=7,
        reliability_score=max(0.0, min(1.0, payload.rating / 5.0)),
    )
    db.add(supplier)
    db.commit()
    return {"ok": True, "supplierId": f"s{supplier.supplier_id}"}


@router.put("/inventory/suppliers/{supplier_id}")
def update_supplier(supplier_id: str, payload: SupplierIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    supplier_pk = _parse_prefixed_id(supplier_id, "s")
    supplier = db.query(Supplier).filter(Supplier.supplier_id == supplier_pk).first()
    if supplier is None:
        return {"ok": False, "error": "Supplier not found"}

    supplier.supplier_name = payload.name
    supplier.contact_email = payload.email
    supplier.contact_phone = payload.phone
    supplier.reliability_score = max(0.0, min(1.0, payload.rating / 5.0))
    db.commit()
    return {"ok": True}


@router.delete("/inventory/suppliers/{supplier_id}")
def delete_supplier(supplier_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    supplier_pk = _parse_prefixed_id(supplier_id, "s")
    supplier = db.query(Supplier).filter(Supplier.supplier_id == supplier_pk).first()
    if supplier is None:
        return {"ok": False, "error": "Supplier not found"}

    item_count = db.query(func.count(Batch.batch_id)).filter(Batch.supplier_id == supplier_pk).scalar() or 0
    if item_count > 0:
        return {"ok": False, "error": "Supplier is referenced by batches and cannot be deleted"}

    try:
        db.delete(supplier)
        db.commit()
    except IntegrityError:
        db.rollback()
        return {"ok": False, "error": "Supplier is referenced and cannot be deleted"}

    return {"ok": True}


@router.post("/inventory/orders")
def create_order(payload: PurchaseOrderIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        supplier_id = _parse_prefixed_id(payload.supplierId, "s")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid supplier id format: {exc}") from exc

    supplier = db.query(Supplier).filter(Supplier.supplier_id == supplier_id).first()
    if supplier is None:
        raise HTTPException(status_code=404, detail=f"Supplier {payload.supplierId} not found")

    order = PurchaseOrder(
        supplier_id=supplier_id,
        order_date=date.fromisoformat(payload.orderDate),
        expected_delivery=date.fromisoformat(payload.expectedDelivery),
        status="PENDING",
    )
    db.add(order)
    db.flush()

    for item in payload.items:
        try:
            item_id = _parse_prefixed_id(item.itemId, "i")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid item id format: {exc}") from exc

        existing_item = db.query(Item).filter(Item.item_id == item_id).first()
        if existing_item is None:
            raise HTTPException(status_code=404, detail=f"Item {item.itemId} not found")

        db.add(
            PurchaseOrderDetail(
                po_id=order.po_id,
                item_id=item_id,
                quantity=item.quantity,
                unit_price=item.unitPrice,
                discount_pct=0.0,
                total_cost=float(item.quantity * item.unitPrice),
                created_by="ui",
                approval_required=False,
                approval_status="APPROVED",
                submission_method="manual",
                submission_status="PENDING",
            )
        )

    db.commit()
    return {"ok": True, "orderId": f"po{order.po_id}"}


@router.put("/inventory/orders/{order_id}/status")
def update_order_status(order_id: str, payload: PurchaseOrderStatusIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        po_id = _parse_prefixed_id(order_id, "po")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid order id format: {exc}") from exc

    order = db.query(PurchaseOrder).filter(PurchaseOrder.po_id == po_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")

    order.status = _db_po_status(payload.status)
    db.commit()
    return {"ok": True, "status": _pretty_po_status(order.status)}
