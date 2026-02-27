"""SQLAlchemy ORM models – mirrors the 14-table schema."""
from datetime import date, datetime
from sqlalchemy import (
    Boolean, Column, Date, Float, ForeignKey,
    Integer, String, DateTime, func,
)
from database.db import Base


class Department(Base):
    __tablename__ = "departments"
    department_id   = Column(Integer, primary_key=True, autoincrement=True)
    department_name = Column(String(100), nullable=False)
    location        = Column(String(100))


class Supplier(Base):
    __tablename__ = "suppliers"
    supplier_id        = Column(Integer, primary_key=True, autoincrement=True)
    supplier_name      = Column(String(150), nullable=False)
    contact_email      = Column(String(150))
    contact_phone      = Column(String(20))
    avg_lead_time_days = Column(Integer)
    reliability_score  = Column(Float)


class Item(Base):
    __tablename__ = "items"
    item_id            = Column(Integer, primary_key=True, autoincrement=True)
    item_name          = Column(String(150), nullable=False)
    category           = Column(String(100))
    unit_type          = Column(String(50))
    safety_stock_level = Column(Integer)
    reorder_point      = Column(Integer)


class Batch(Base):
    __tablename__ = "batches"
    batch_id          = Column(Integer, primary_key=True, autoincrement=True)
    item_id           = Column(Integer, ForeignKey("items.item_id"), nullable=False)
    supplier_id       = Column(Integer, ForeignKey("suppliers.supplier_id"), nullable=False)
    manufacture_date  = Column(Date)
    expiry_date       = Column(Date)
    purchase_price    = Column(Float)
    quantity_received = Column(Integer)


class InventoryStock(Base):
    __tablename__ = "inventory_stock"
    stock_id         = Column(Integer, primary_key=True, autoincrement=True)
    item_id          = Column(Integer, ForeignKey("items.item_id"), nullable=False)
    batch_id         = Column(Integer, ForeignKey("batches.batch_id"), nullable=False)
    department_id    = Column(Integer, ForeignKey("departments.department_id"), nullable=False)
    current_quantity = Column(Integer, nullable=False)
    last_updated     = Column(DateTime, server_default=func.now())


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    po_id             = Column(Integer, primary_key=True, autoincrement=True)
    supplier_id       = Column(Integer, ForeignKey("suppliers.supplier_id"))
    order_date        = Column(Date)
    expected_delivery = Column(Date)
    status            = Column(String(50))


class GoodsReceipt(Base):
    __tablename__ = "goods_receipts"
    grn_id        = Column(Integer, primary_key=True, autoincrement=True)
    po_id         = Column(Integer, ForeignKey("purchase_orders.po_id"))
    received_date = Column(Date)
    verified_by   = Column(String(100))


class ConsumptionRecord(Base):
    __tablename__ = "consumption_records"
    consumption_id = Column(Integer, primary_key=True, autoincrement=True)
    item_id        = Column(Integer, ForeignKey("items.item_id"), nullable=False)
    batch_id       = Column(Integer, ForeignKey("batches.batch_id"))
    department_id  = Column(Integer, ForeignKey("departments.department_id"))
    quantity_used  = Column(Integer)
    usage_date     = Column(Date)
    patient_type   = Column(String(50))


class Equipment(Base):
    __tablename__ = "equipment"
    equipment_id    = Column(Integer, primary_key=True, autoincrement=True)
    equipment_name  = Column(String(150))
    serial_number   = Column(String(150))
    department_id   = Column(Integer, ForeignKey("departments.department_id"))
    purchase_date   = Column(Date)
    maintenance_due = Column(Date)


class EquipmentUsage(Base):
    __tablename__ = "equipment_usage"
    usage_id     = Column(Integer, primary_key=True, autoincrement=True)
    equipment_id = Column(Integer, ForeignKey("equipment.equipment_id"))
    usage_date   = Column(Date)
    usage_hours  = Column(Float)


class DemandPrediction(Base):
    __tablename__ = "demand_predictions"
    prediction_id      = Column(Integer, primary_key=True, autoincrement=True)
    item_id            = Column(Integer, ForeignKey("items.item_id"))
    prediction_date    = Column(Date)
    predicted_quantity = Column(Float)
    model_version      = Column(String(50))


class StockoutRisk(Base):
    __tablename__ = "stockout_risk"
    risk_id          = Column(Integer, primary_key=True, autoincrement=True)
    item_id          = Column(Integer, ForeignKey("items.item_id"))
    prediction_date  = Column(Date)
    risk_probability = Column(Float)
    risk_flag        = Column(Boolean)


class ExpiryRisk(Base):
    __tablename__ = "expiry_risk"
    expiry_id               = Column(Integer, primary_key=True, autoincrement=True)
    batch_id                = Column(Integer, ForeignKey("batches.batch_id"))
    prediction_date         = Column(Date)
    expiry_risk_probability = Column(Float)
    high_risk_flag          = Column(Boolean)


class InventoryAuditLog(Base):
    __tablename__ = "inventory_audit_log"
    audit_id         = Column(Integer, primary_key=True, autoincrement=True)
    item_id          = Column(Integer, ForeignKey("items.item_id"))
    batch_id         = Column(Integer, ForeignKey("batches.batch_id"))
    old_quantity     = Column(Integer)
    new_quantity     = Column(Integer)
    updated_by       = Column(String(100))
    update_timestamp = Column(DateTime, server_default=func.now())


class CostAnalysis(Base):
    __tablename__ = "cost_analysis"
    cost_id           = Column(Integer, primary_key=True, autoincrement=True)
    item_id           = Column(Integer, ForeignKey("items.item_id"))
    holding_cost      = Column(Float)
    shortage_cost     = Column(Float)
    expiry_loss_cost  = Column(Float)
    estimated_savings = Column(Float)
