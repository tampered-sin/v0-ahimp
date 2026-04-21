"""High-fidelity synthetic hospital inventory seeder.

Creates a realistic 12-year data history with:
- hundreds of medicine/instrument SKUs
- departments and suppliers with different reliability/lead-time profiles
- seasonality + surge effects in daily usage
- inventory, batch, and equipment utilization records
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta
from math import cos, pi, sin

from sqlalchemy.orm import Session

from database.models import (
    Batch,
    ConsumptionRecord,
    Department,
    Equipment,
    EquipmentUsage,
    InventoryStock,
    Item,
    Supplier,
)

SEED = 4217
YEARS_OF_HISTORY = 12
FORECAST_COMPARISON_YEARS = 2

MEDICINE_TARGET = 220
SUPPLY_TARGET = 90
EQUIPMENT_TARGET = 30

PATIENT_TYPES = [
    "Inpatient",
    "Outpatient",
    "Emergency",
    "ICU",
    "Pediatric",
    "Oncology",
    "Dialysis",
]

DEPARTMENTS = [
    ("Pharmacy", "Block A, Floor 1"),
    ("Emergency", "Block A, Floor 2"),
    ("ICU", "Block B, Floor 4"),
    ("Surgery", "Block B, Floor 3"),
    ("Cardiology", "Block C, Floor 2"),
    ("Neurology", "Block C, Floor 3"),
    ("Oncology", "Block D, Floor 2"),
    ("Pediatrics", "Block D, Floor 3"),
    ("Nephrology", "Block E, Floor 2"),
    ("Laboratory", "Block E, Floor 1"),
    ("Radiology", "Block F, Floor 1"),
    ("Blood Bank", "Block F, Floor 2"),
]

SUPPLIERS = [
    ("MediCore Pharma", "medicore.com", 6, 0.97),
    ("CareChem Therapeutics", "carechem.io", 8, 0.93),
    ("Apex Hospital Supplies", "apexhs.com", 7, 0.95),
    ("SterileWave Surgical", "sterilewave.org", 9, 0.92),
    ("Pulse Biomedical", "pulsebio.net", 10, 0.90),
    ("Nexus Diagnostics", "nexusdiag.com", 6, 0.94),
    ("HemoLife Blood Systems", "hemolife.co", 4, 0.98),
    ("SafeShield PPE", "safeshield.ai", 5, 0.96),
    ("Global Generic Labs", "gglabs.health", 12, 0.89),
    ("OrthoPrime Devices", "orthoprime.dev", 11, 0.91),
    ("CleanRoom Essentials", "cleanroomx.com", 7, 0.88),
    ("NovaCare Logistics", "novacarelog.com", 9, 0.90),
    ("BioAxis Clinical", "bioaxis.org", 8, 0.92),
    ("MediTrack Distribution", "meditrack.io", 6, 0.95),
]

MEDICINE_MOLECULES = [
    "Amoxicillin", "Azithromycin", "Ceftriaxone", "Meropenem", "Piperacillin-Tazobactam",
    "Paracetamol", "Ibuprofen", "Diclofenac", "Tramadol", "Morphine Sulfate",
    "Insulin Glargine", "Insulin Regular", "Metformin", "Glimepiride", "Empagliflozin",
    "Amlodipine", "Losartan", "Telmisartan", "Metoprolol", "Atorvastatin",
    "Rosuvastatin", "Clopidogrel", "Aspirin", "Warfarin", "Apixaban",
    "Heparin", "Enoxaparin", "Pantoprazole", "Omeprazole", "Esomeprazole",
    "Ondansetron", "Domperidone", "Metoclopramide", "Levothyroxine", "Prednisolone",
    "Dexamethasone", "Hydrocortisone", "Salbutamol", "Budesonide", "Montelukast",
    "Linezolid", "Vancomycin", "Levofloxacin", "Ciprofloxacin", "Doxycycline",
    "Fluconazole", "Amphotericin", "Acyclovir", "Remdesivir", "Oseltamivir",
    "Epinephrine", "Norepinephrine", "Dopamine", "Dobutamine", "Nitroglycerin",
    "Furosemide", "Spironolactone", "Mannitol", "Albumin", "Calcium Gluconate",
    "Magnesium Sulfate", "Potassium Chloride", "Sodium Bicarbonate", "Phenytoin", "Levetiracetam",
    "Valproate", "Haloperidol", "Risperidone", "Sertraline", "Escitalopram",
    "Olanzapine", "Ketamine", "Propofol", "Midazolam", "Fentanyl",
    "Rocuronium", "Atracurium", "Lignocaine", "Bupivacaine", "Tranexamic Acid",
    "Oxytocin", "Misoprostol", "Methotrexate", "Cyclophosphamide", "Paclitaxel",
    "Cisplatin", "Carboplatin", "Rituximab", "Trastuzumab", "Filgrastim",
]

SUPPLY_NAMES = [
    "Surgical Gloves Sterile", "Suture Kit Absorbable", "Scalpel Blade No.10",
    "Surgical Drapes", "Gauze Swab", "Adhesive Bandage", "IV Cannula",
    "Syringe 5mL", "Syringe 10mL", "Blood Collection Tube", "Urine Collection Bag",
    "N95 Respirator", "Face Shield", "Disposable Gown", "Shoe Cover",
    "PCR Reagent Kit", "Rapid Antigen Kit", "Glucose Test Strip", "CRP Test Cartridge",
    "Dialyzer Cartridge", "ECG Electrode", "Ultrasound Gel", "Catheter Foley",
    "Endotracheal Tube", "Nebulizer Mask", "Central Line Kit", "Suction Catheter",
    "Arterial Blood Gas Syringe", "Platelet Storage Bag", "Blood Transfusion Set",
]

EQUIPMENT_NAMES = [
    "Patient Monitor", "Infusion Pump", "Defibrillator AED", "Ventilator ICU",
    "Portable Ultrasound", "ECG Machine", "Anesthesia Workstation", "Suction Unit",
    "Dialysis Machine", "Blood Warmer", "Syringe Pump", "Transport Ventilator",
    "Fetal Monitor", "Electrocautery Unit", "Pulse Oximeter", "Crash Cart",
]


@dataclass
class ItemBlueprint:
    name: str
    category: str
    unit_type: str
    safety_stock_level: int
    reorder_point: int
    purchase_price: float
    supplier_idx: int
    department_idx: int
    opening_quantity: int
    is_consumable: bool
    shelf_life_days: int | None


def _generate_suppliers() -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for idx, (name, domain, lead, reliability) in enumerate(SUPPLIERS, start=1):
        records.append(
            {
                "name": name,
                "email": f"orders@{domain}",
                "phone": f"+1-555-{1200 + idx:04d}",
                "lead": lead,
                "reliability": reliability,
            }
        )
    return records


def _build_medicine_blueprints(rng: random.Random) -> list[ItemBlueprint]:
    forms = [
        ("Tablets", ["5mg", "10mg", "20mg", "50mg", "100mg"], 0.12, 1.8),
        ("Capsules", ["100mg", "250mg", "500mg"], 0.22, 2.2),
        ("Vials", ["250mg", "500mg", "1g"], 2.0, 45.0),
        ("Injectors", ["1mg/mL", "2mg/mL"], 15.0, 90.0),
        ("Pens", ["100U/mL"], 18.0, 130.0),
    ]
    items: list[ItemBlueprint] = []
    name_seen: set[str] = set()

    while len(items) < MEDICINE_TARGET:
        molecule = rng.choice(MEDICINE_MOLECULES)
        form, strengths, price_min, price_max = rng.choice(forms)
        strength = rng.choice(strengths)
        item_name = f"{molecule} {strength}"
        if item_name in name_seen:
            continue

        name_seen.add(item_name)
        reorder = rng.randint(180, 1400)
        # Keep safety stock below full-week expected demand for a subset of SKUs
        # so stockout labels contain both positive and negative classes.
        safety = int(reorder * rng.uniform(0.45, 0.95))
        opening = int(reorder * rng.uniform(2.0, 7.5))

        items.append(
            ItemBlueprint(
                name=item_name,
                category="Medicines",
                unit_type=form,
                safety_stock_level=safety,
                reorder_point=reorder,
                purchase_price=round(rng.uniform(price_min, price_max), 2),
                supplier_idx=rng.randrange(len(SUPPLIERS)),
                department_idx=rng.randrange(len(DEPARTMENTS)),
                opening_quantity=opening,
                is_consumable=True,
                shelf_life_days=rng.randint(365, 1095),
            )
        )

    return items


def _build_supply_blueprints(rng: random.Random) -> list[ItemBlueprint]:
    unit_map = {
        "Surgical Gloves Sterile": "Pairs",
        "Suture Kit Absorbable": "Kits",
        "Scalpel Blade No.10": "Blades",
        "Surgical Drapes": "Packs",
        "Gauze Swab": "Packs",
        "Adhesive Bandage": "Boxes",
        "IV Cannula": "Units",
        "Syringe 5mL": "Units",
        "Syringe 10mL": "Units",
        "Blood Collection Tube": "Tubes",
        "Urine Collection Bag": "Units",
        "N95 Respirator": "Masks",
        "Face Shield": "Shields",
        "Disposable Gown": "Gowns",
        "Shoe Cover": "Pairs",
        "PCR Reagent Kit": "Kits",
        "Rapid Antigen Kit": "Kits",
        "Glucose Test Strip": "Strips",
        "CRP Test Cartridge": "Cartridges",
        "Dialyzer Cartridge": "Cartridges",
        "ECG Electrode": "Packs",
        "Ultrasound Gel": "Bottles",
        "Catheter Foley": "Units",
        "Endotracheal Tube": "Units",
        "Nebulizer Mask": "Units",
        "Central Line Kit": "Kits",
        "Suction Catheter": "Units",
        "Arterial Blood Gas Syringe": "Units",
        "Platelet Storage Bag": "Units",
        "Blood Transfusion Set": "Units",
    }

    items: list[ItemBlueprint] = []
    for idx in range(SUPPLY_TARGET):
        base = SUPPLY_NAMES[idx % len(SUPPLY_NAMES)]
        variant = idx // len(SUPPLY_NAMES) + 1
        name = base if variant == 1 else f"{base} Type-{variant}"
        category = "PPE" if any(x in base for x in ["Mask", "Shield", "Gown", "Gloves", "Shoe"]) else "Surgical Supplies"
        if any(x in base for x in ["PCR", "Antigen", "CRP", "Glucose"]):
            category = "Lab Reagents"

        reorder = rng.randint(120, 2200)
        safety = int(reorder * rng.uniform(0.50, 1.00))
        opening = int(reorder * rng.uniform(1.8, 6.0))

        items.append(
            ItemBlueprint(
                name=name,
                category=category,
                unit_type=unit_map.get(base, "Units"),
                safety_stock_level=safety,
                reorder_point=reorder,
                purchase_price=round(rng.uniform(0.15, 75.0), 2),
                supplier_idx=rng.randrange(len(SUPPLIERS)),
                department_idx=rng.randrange(len(DEPARTMENTS)),
                opening_quantity=opening,
                is_consumable=True,
                shelf_life_days=rng.randint(300, 1500),
            )
        )

    return items


def _build_equipment_blueprints(rng: random.Random) -> list[ItemBlueprint]:
    items: list[ItemBlueprint] = []
    for idx in range(EQUIPMENT_TARGET):
        base = EQUIPMENT_NAMES[idx % len(EQUIPMENT_NAMES)]
        variant = idx // len(EQUIPMENT_NAMES) + 1
        name = base if variant == 1 else f"{base} Gen-{variant}"

        items.append(
            ItemBlueprint(
                name=name,
                category="Equipment",
                unit_type="Units",
                safety_stock_level=rng.randint(2, 12),
                reorder_point=rng.randint(2, 12),
                purchase_price=round(rng.uniform(1200.0, 55000.0), 2),
                supplier_idx=rng.randrange(len(SUPPLIERS)),
                department_idx=rng.randrange(len(DEPARTMENTS)),
                opening_quantity=rng.randint(2, 40),
                is_consumable=False,
                shelf_life_days=None,
            )
        )

    return items


def _seasonal_multiplier(category: str, day_index: int) -> float:
    weekly = 1.0 + 0.10 * sin(2 * pi * (day_index % 7) / 7)
    annual = 1.0 + 0.14 * sin(2 * pi * day_index / 365)
    quarterly = 1.0 + 0.04 * cos(2 * pi * day_index / 90)

    category_bias = {
        "Medicines": 1.0,
        "Surgical Supplies": 0.95,
        "PPE": 0.9,
        "Lab Reagents": 0.8,
        "Blood Bank": 0.75,
        "Equipment": 0.15,
    }.get(category, 0.9)

    return max(0.05, weekly * annual * quarterly * category_bias)


def _surge_multiplier(day_index: int, rng: random.Random) -> float:
    # Simulate occasional outbreaks/high occupancy waves.
    annual_day = day_index % 365
    seasonal_wave = 1.15 if annual_day in range(320, 365) or annual_day in range(0, 45) else 1.0
    random_surge = 1.0 + max(0.0, rng.gauss(0, 0.03))
    return seasonal_wave * random_surge


def seed(db: Session) -> None:
    """Idempotent seed function – skips if data already exists."""
    if db.query(Department).count() > 0:
        print("Database already seeded – skipping.")
        return

    rng = random.Random(SEED)
    print(
        "Seeding database with realistic 12-year hospital inventory data "
        f"(includes {FORECAST_COMPARISON_YEARS}-year holdout for forecast comparison) …"
    )

    # Departments
    dept_rows: list[Department] = []
    for name, location in DEPARTMENTS:
        dep = Department(department_name=name, location=location)
        db.add(dep)
        dept_rows.append(dep)
    db.flush()

    # Suppliers
    supplier_rows: list[Supplier] = []
    for row in _generate_suppliers():
        supplier = Supplier(
            supplier_name=row["name"],
            contact_email=row["email"],
            contact_phone=row["phone"],
            avg_lead_time_days=row["lead"],
            reliability_score=row["reliability"],
        )
        db.add(supplier)
        supplier_rows.append(supplier)
    db.flush()

    # Item catalog (hundreds of unique medicines/instruments)
    catalog = []
    catalog.extend(_build_medicine_blueprints(rng))
    catalog.extend(_build_supply_blueprints(rng))
    catalog.extend(_build_equipment_blueprints(rng))
    rng.shuffle(catalog)

    today = date.today()
    start_date = today - timedelta(days=YEARS_OF_HISTORY * 365)
    total_days = (today - start_date).days

    item_rows: list[tuple[Item, ItemBlueprint]] = []
    batch_by_item_id: dict[int, int] = {}

    for blueprint in catalog:
        item = Item(
            item_name=blueprint.name,
            category=blueprint.category,
            unit_type=blueprint.unit_type,
            safety_stock_level=blueprint.safety_stock_level,
            reorder_point=blueprint.reorder_point,
        )
        db.add(item)
        db.flush()

        expiry_date = None
        if blueprint.shelf_life_days is not None:
            # Keep a realistic minority of consumable batches close to expiry so
            # expiry-risk labels contain both positive and negative classes.
            if blueprint.is_consumable and rng.random() < 0.18:
                remaining_days = rng.randint(5, 14)
            else:
                remaining_days = rng.randint(
                    min(90, blueprint.shelf_life_days),
                    blueprint.shelf_life_days,
                )
            expiry_date = today + timedelta(days=remaining_days)

        batch = Batch(
            item_id=item.item_id,
            supplier_id=supplier_rows[blueprint.supplier_idx].supplier_id,
            manufacture_date=today - timedelta(days=rng.randint(40, 450)),
            expiry_date=expiry_date,
            purchase_price=blueprint.purchase_price,
            quantity_received=max(
                blueprint.opening_quantity + rng.randint(0, blueprint.opening_quantity // 2 + 1),
                blueprint.opening_quantity,
            ),
        )
        db.add(batch)
        db.flush()

        stock = InventoryStock(
            item_id=item.item_id,
            batch_id=batch.batch_id,
            department_id=dept_rows[blueprint.department_idx].department_id,
            current_quantity=blueprint.opening_quantity,
        )
        db.add(stock)

        item_rows.append((item, blueprint))
        batch_by_item_id[item.item_id] = batch.batch_id

    db.flush()

    # Equipment table rows (for equipment items)
    equipment_rows: list[Equipment] = []
    for item, blueprint in item_rows:
        if blueprint.category != "Equipment":
            continue
        equipment = Equipment(
            equipment_name=blueprint.name,
            serial_number=f"{item.item_id:05d}-{rng.randint(1000, 9999)}",
            department_id=dept_rows[blueprint.department_idx].department_id,
            purchase_date=today - timedelta(days=rng.randint(180, 2200)),
            maintenance_due=today + timedelta(days=rng.randint(30, 365)),
        )
        db.add(equipment)
        db.flush()
        equipment_rows.append(equipment)

    # Equipment usage for last 365 days
    for equipment in equipment_rows:
        for day_offset in range(365):
            usage = EquipmentUsage(
                equipment_id=equipment.equipment_id,
                usage_date=today - timedelta(days=day_offset),
                usage_hours=round(max(0.5, rng.gauss(9.5, 3.0)), 1),
            )
            db.add(usage)

    # Consumption records over 10 years
    consumption_count = 0
    flush_every = 2500

    for item, blueprint in item_rows:
        if not blueprint.is_consumable:
            continue

        dept_id = dept_rows[blueprint.department_idx].department_id
        batch_id = batch_by_item_id[item.item_id]

        # Demand intensity calibrated to create realistic replenishment pressure.
        base_daily = max(1.0, blueprint.reorder_point / 11.0)

        for day_offset in range(total_days):
            day = start_date + timedelta(days=day_offset)
            seasonal = _seasonal_multiplier(blueprint.category, day_offset)
            surge = _surge_multiplier(day_offset, rng)
            noise = max(0.2, 1.0 + rng.gauss(0, 0.12))

            expected = base_daily * seasonal * surge * noise
            qty_used = int(max(0, round(expected)))

            # Keep sparse low-volume usage for specialty categories.
            if blueprint.category in {"Blood Bank", "Lab Reagents"} and rng.random() < 0.55:
                qty_used = int(max(0, round(qty_used * 0.4)))

            if qty_used <= 0:
                continue

            record = ConsumptionRecord(
                item_id=item.item_id,
                batch_id=batch_id,
                department_id=dept_id,
                quantity_used=qty_used,
                usage_date=day,
                patient_type=rng.choice(PATIENT_TYPES),
            )
            db.add(record)
            consumption_count += 1

            if consumption_count % flush_every == 0:
                db.flush()

    db.commit()
    print(
        "Seeding complete – "
        f"{len(item_rows)} items, {len(equipment_rows)} equipment assets, "
        f"{consumption_count:,} consumption records over {YEARS_OF_HISTORY} years "
        f"({YEARS_OF_HISTORY - FORECAST_COMPARISON_YEARS}y baseline + {FORECAST_COMPARISON_YEARS}y comparison)."
    )
