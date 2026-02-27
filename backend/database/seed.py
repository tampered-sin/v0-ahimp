"""
Synthetic data seeder.

Creates departments, suppliers, items, batches, inventory stock, and
~2 years of daily Consumption_Records derived from the mock inventory items
used in the Next.js frontend.
"""
from __future__ import annotations

import random
from datetime import date, timedelta
from math import sin, pi

from sqlalchemy.orm import Session
from database.models import (
    Department, Supplier, Item, Batch,
    InventoryStock, ConsumptionRecord, Equipment, EquipmentUsage,
)

SEED = 42
random.seed(SEED)

# ---------------------------------------------------------------------------
# Raw mock data  (mirrors lib/mock-data.ts so the DB is consistent with UI)
# ---------------------------------------------------------------------------
DEPARTMENTS = [
    {"name": "Pharmacy",   "location": "Block A, Floor 1"},
    {"name": "Surgery",    "location": "Block B, Floor 3"},
    {"name": "Emergency",  "location": "Block C, Floor 1"},
    {"name": "ICU",        "location": "Block D, Floor 4"},
    {"name": "Pediatrics", "location": "Block E, Floor 2"},
    {"name": "Laboratory", "location": "Block F, Floor 1"},
]

SUPPLIERS = [
    {"name": "MedPharm Distributors", "email": "orders@medpharm.com",   "phone": "+1-555-0101", "lead": 7,  "reliability": 0.96},
    {"name": "SurgiTech Solutions",   "email": "sales@surgitech.com",   "phone": "+1-555-0102", "lead": 10, "reliability": 0.90},
    {"name": "BioLab Supplies Inc",   "email": "info@biolab.com",       "phone": "+1-555-0103", "lead": 8,  "reliability": 0.84},
    {"name": "SafeGuard PPE Co",      "email": "supply@safeguard.com",  "phone": "+1-555-0104", "lead": 5,  "reliability": 0.92},
    {"name": "BloodCare Systems",     "email": "orders@bloodcare.com",  "phone": "+1-555-0105", "lead": 3,  "reliability": 0.98},
    {"name": "PharmaGlobal Ltd",      "email": "sales@pharmaglobal.com","phone": "+1-555-0106", "lead": 12, "reliability": 0.86},
    {"name": "OrthoMed Devices",      "email": "info@orthomed.com",     "phone": "+1-555-0107", "lead": 9,  "reliability": 0.94},
    {"name": "CleanRoom Essentials",  "email": "orders@cleanroom.com",  "phone": "+1-555-0108", "lead": 6,  "reliability": 0.82},
]

ITEMS = [
    # (name, category, unit, safety_stock, reorder_pt, price, supplier_idx, dept_idx, qty, expiry_str)
    ("Amoxicillin 500mg",          "Medicines",         "Capsules", 500,  500,  0.45,  0, 0, 2500, "2026-08-15"),
    ("Ibuprofen 200mg",            "Medicines",         "Tablets",  400,  400,  0.12,  0, 0, 1800, "2026-11-20"),
    ("Morphine Sulfate 10mg",      "Medicines",         "Vials",    150,  150,  8.50,  5, 3, 120,  "2026-03-10"),
    ("Epinephrine 1mg/mL",         "Medicines",         "Injectors",100,  100,  35.00, 0, 2, 350,  "2026-06-30"),
    ("Insulin Glargine 100U/mL",   "Medicines",         "Pens",     100,  100,  42.00, 5, 0, 85,   "2026-04-15"),
    ("Ceftriaxone 1g",             "Medicines",         "Vials",    200,  200,  3.20,  0, 0, 600,  "2027-01-20"),
    ("Paracetamol 500mg",          "Medicines",         "Tablets",  1000, 1000, 0.08,  0, 0, 5000, "2027-03-15"),
    ("Omeprazole 20mg",            "Medicines",         "Capsules", 300,  300,  0.35,  5, 0, 30,   "2026-02-28"),
    ("Patient Monitor",            "Equipment",         "Units",    5,    5,    4500,  1, 3, 24,   None),
    ("Infusion Pump",              "Equipment",         "Units",    10,   10,   2800,  1, 3, 45,   None),
    ("Defibrillator AED",          "Equipment",         "Units",    3,    3,    1200,  1, 2, 8,    None),
    ("Ventilator (ICU Grade)",     "Equipment",         "Units",    5,    5,    25000, 1, 3, 3,    None),
    ("Surgical Gloves (Sterile)",  "Surgical Supplies", "Pairs",    2000, 2000, 0.65,  3, 1, 8000, "2027-05-20"),
    ("Suture Kit (Absorbable)",    "Surgical Supplies", "Kits",     50,   50,   12.50, 1, 1, 250,  "2027-08-30"),
    ("Scalpel Blades #10",        "Surgical Supplies", "Blades",   100,  100,  0.85,  1, 1, 400,  "2028-01-15"),
    ("Surgical Drapes (Sterile)",  "Surgical Supplies", "Packs",    60,   60,   8.75,  7, 1, 45,   "2027-04-10"),
    ("N95 Respirator Masks",       "PPE",               "Masks",    1000, 1000, 1.85,  3, 2, 3500, "2027-12-31"),
    ("Disposable Gowns",           "PPE",               "Gowns",    300,  300,  2.40,  3, 2, 1200, "2027-10-15"),
    ("Face Shields",               "PPE",               "Shields",  200,  200,  3.50,  3, 2, 180,  "2028-06-30"),
    ("Nitrile Exam Gloves (M)",    "PPE",               "Gloves",   5000, 5000, 0.12,  3, 2, 15000,"2028-03-20"),
    ("Blood Glucose Test Strips",  "Lab Reagents",      "Strips",   500,  500,  0.55,  2, 5, 2000, "2026-09-30"),
    ("PCR Reagent Kit",            "Lab Reagents",      "Kits",     20,   20,   285.0, 2, 5, 15,   "2026-04-20"),
    ("Packed RBC (O+)",            "Blood Bank",        "Units",    30,   30,   225.0, 4, 1, 45,   "2026-03-15"),
    ("Fresh Frozen Plasma (AB)",   "Blood Bank",        "Units",    15,   15,   180.0, 4, 1, 12,   "2026-08-20"),
    ("Platelet Concentrate",       "Blood Bank",        "Units",    10,   10,   550.0, 4, 1, 8,    "2026-02-20"),
    ("Warfarin 5mg",               "Medicines",         "Tablets",  200,  200,  0.18,  5, 0, 0,    "2027-02-28"),
    ("Aspirin 81mg",               "Medicines",         "Tablets",  500,  500,  0.05,  0, 0, 3000, "2027-06-15"),
    ("Metformin 500mg",            "Medicines",         "Tablets",  300,  300,  0.15,  5, 0, 1500, "2027-09-30"),
]

PATIENT_TYPES = ["Inpatient", "Outpatient", "Emergency", "ICU", "Pediatric"]


def _daily_demand(base: int, day_idx: int) -> int:
    """Simulate realistic demand with weekly + annual seasonality + noise."""
    # Weekly cycle: higher mid-week
    weekly   = 1 + 0.15 * sin(2 * pi * (day_idx % 7) / 7)
    # Annual cycle: higher in winter months
    annual   = 1 + 0.10 * sin(2 * pi * day_idx / 365)
    noise    = random.gauss(0, 0.08)
    demand   = max(0, int(base * (weekly + annual + noise)))
    return demand


def seed(db: Session) -> None:
    """Idempotent seed function – skips if data already exists."""
    if db.query(Department).count() > 0:
        print("Database already seeded – skipping.")
        return

    print("Seeding database …")

    # ── Departments ──────────────────────────────────────────────────────────
    depts = []
    for d in DEPARTMENTS:
        dep = Department(department_name=d["name"], location=d["location"])
        db.add(dep); depts.append(dep)
    db.flush()

    # ── Suppliers ────────────────────────────────────────────────────────────
    sups = []
    for s in SUPPLIERS:
        sup = Supplier(
            supplier_name=s["name"], contact_email=s["email"],
            contact_phone=s["phone"], avg_lead_time_days=s["lead"],
            reliability_score=s["reliability"],
        )
        db.add(sup); sups.append(sup)
    db.flush()

    # ── Items + Batches + Stock ───────────────────────────────────────────────
    today        = date.today()
    start_date   = date(today.year - 2, today.month, today.day)

    item_objs = []
    batch_map: dict[int, int] = {}  # item_idx → batch_id

    for idx, row in enumerate(ITEMS):
        name, cat, unit, safety, reorder, price, sup_idx, dept_idx, qty, exp = row

        item = Item(
            item_name=name, category=cat, unit_type=unit,
            safety_stock_level=safety, reorder_point=reorder,
        )
        db.add(item); db.flush()

        exp_date = date.fromisoformat(exp) if exp else date(today.year + 3, 1, 1)
        batch = Batch(
            item_id=item.item_id, supplier_id=sups[sup_idx].supplier_id,
            manufacture_date=date(today.year - 1, 6, 1),
            expiry_date=exp_date,
            purchase_price=price, quantity_received=qty + random.randint(0, qty // 2 + 1),
        )
        db.add(batch); db.flush()

        stock = InventoryStock(
            item_id=item.item_id, batch_id=batch.batch_id,
            department_id=depts[dept_idx].department_id,
            current_quantity=qty,
        )
        db.add(stock)
        item_objs.append(item)
        batch_map[idx] = batch.batch_id

    db.flush()

    # ── Equipment (optional module) ───────────────────────────────────────────
    equip_rows = [
        ("Patient Monitor",  "PM-001", 3, date(2022, 6, 1), date(today.year, 6, 1)),
        ("Infusion Pump",    "IP-001", 3, date(2022, 9, 1), date(today.year, 9, 1)),
        ("Ventilator",       "VN-001", 3, date(2023, 1, 1), date(today.year + 1, 1, 1)),
        ("Defibrillator",    "DF-001", 2, date(2021, 11, 1),date(today.year, 11, 1)),
    ]
    equip_objs = []
    for ename, serial, didx, pdate, mdue in equip_rows:
        e = Equipment(
            equipment_name=ename, serial_number=serial,
            department_id=depts[didx].department_id,
            purchase_date=pdate, maintenance_due=mdue,
        )
        db.add(e); db.flush()
        equip_objs.append(e)

    # Equipment usage – 1 record/day for last 90 days
    for e in equip_objs:
        for d in range(90):
            eu = EquipmentUsage(
                equipment_id=e.equipment_id,
                usage_date=today - timedelta(days=d),
                usage_hours=round(random.uniform(4.0, 20.0), 1),
            )
            db.add(eu)

    # ── Consumption Records (≈2 years daily) ─────────────────────────────────
    total_days = (today - start_date).days
    BATCH_SIZE = 500
    count = 0

    for item_idx, item in enumerate(item_objs):
        # Equipment items: almost zero daily consumption
        is_equipment = ITEMS[item_idx][1] == "Equipment"
        base_demand  = max(1, ITEMS[item_idx][7 + 1] // 30) if not is_equipment else 0

        dept_id  = depts[ITEMS[item_idx][7]].department_id
        batch_id = batch_map[item_idx]

        for day_offset in range(total_days):
            usage_date = start_date + timedelta(days=day_offset)
            qty_used   = _daily_demand(base_demand, day_offset)
            if qty_used == 0:
                continue

            cr = ConsumptionRecord(
                item_id=item.item_id,
                batch_id=batch_id,
                department_id=dept_id,
                quantity_used=qty_used,
                usage_date=usage_date,
                patient_type=random.choice(PATIENT_TYPES),
            )
            db.add(cr)
            count += 1
            if count % BATCH_SIZE == 0:
                db.flush()

    db.commit()
    print(f"Seeding complete – {count:,} consumption records created.")
