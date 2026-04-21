# AHIMP Dataset Generation Task

## Task Metadata
- Task ID: DATA-GEN-001
- Project: AHIMP (AI-Based Hospital Inventory Management)
- Owner: Data Engineering + ML Engineering
- Status: Ready for Implementation
- Priority: High
- Target Environment: backend seeding + model-training pipeline

## Objective
Create a realistic synthetic hospital inventory dataset that is suitable for:
1. Daily operations simulation (inventory, procurement, expiry, stockout workflows)
2. Demand forecasting model training and validation
3. Stockout and expiry risk model training
4. Explainability and dashboard feature demonstrations

## Realism Envelope (What To Simulate)
Use these ranges as target realism guidance for a medium to large hospital system:
- Medicine types (unique SKUs): 200 to 500
- Consumables and supplies (PPE, surgical, lab): 80 to 250
- Equipment asset types: 20 to 80
- Total item catalog size: 320 to 830
- Historical horizon: minimum 10 years daily usage history

## Required Output Artifacts
1. Seeded master and transactional tables in the project database
2. Reproducible generation logic with deterministic seed
3. Documentation of assumptions and parameter choices
4. Validation report (counts, constraints, data-quality checks)

## Database Coverage Requirements
The generated dataset must populate at minimum:
- Departments
- Suppliers
- Items
- Batches
- Inventory_Stock
- Consumption_Records
- Equipment
- Equipment_Usage

Should also support downstream generation or testing for:
- Purchase_Orders
- Purchase_Order_Details
- Goods_Receipts
- Delivery_Tracking
- Delivery_Events
- Demand_Predictions
- Stockout_Risk
- Expiry_Risk

## Generation Rules

### 1. Master Data
- Departments:
  - Include core clinical and operational areas (Pharmacy, ICU, ER, Surgery, Lab, Pediatrics, Oncology, Cardiology, etc.)
  - Minimum count: 8
- Suppliers:
  - Include mixed reliability and lead-time profiles
  - Minimum count: 10
  - Lead time range: 3 to 15 days
  - Reliability score range: 0.80 to 0.99
- Items:
  - Include medicines, consumables, and equipment
  - Must include category, unit_type, safety_stock_level, reorder_point

### 2. Batch and Stock Data
- Every item must have at least one batch and one stock row
- Medicines and consumables must include expiry date behavior
- Equipment may have long or null expiry treatment depending on business assumption
- Purchase prices must be positive and category-appropriate

### 3. Consumption Time Series (Critical)
- Horizon: 10 years of daily records
- Time-series behavior must include:
  - Weekly seasonality
  - Annual seasonality
  - Random noise
  - Surge periods (for outbreaks/high occupancy)
- Must include:
  - item_id
  - department_id
  - quantity_used
  - usage_date
  - patient_type

### 4. Equipment Utilization
- Equipment usage records should exist for recent operating period (example: last 365 days)
- Usage hours should be non-negative with realistic distribution

## Qualification Criteria (Must Pass)

### A. Schema Qualification
- 100% of required NOT NULL fields are populated
- All foreign-key references are valid
- No duplicate primary keys

### B. Statistical Qualification
- No negative values for quantity_used, current_quantity, purchase_price
- Daily consumption present for the majority of consumable SKUs
- Long-tail behavior present (not all items same demand level)
- Seasonal signal detectable in aggregate demand series

### C. Operational Qualification
- Seed process is idempotent (safe to rerun without duplicate inserts)
- Seed process finishes within acceptable local runtime
- Data volume does not break training startup flow

### D. ML Qualification
- Generated data supports successful training of:
  - Demand model
  - Stockout model
  - Expiry model
- Model training produces non-empty metrics and artifacts
- ARIMA baseline receives enough history to evaluate (no forced null metrics from missing history)

## Data Quality Checklist
- Row counts by table verified
- Null-rate report for critical columns
- Category distribution report
- Supplier distribution report
- Top 20 high-usage items report
- Date range check confirms >= 10 years
- Outlier check for impossible values

## Recommended Default Targets For This Repo
- Medicines: 220
- Supplies: 90
- Equipment: 30
- Total catalog: 340
- History: 10 years daily

## Reproducibility Requirements
- Use a fixed random seed in generator
- Keep parameterized constants for item counts and horizon
- Document all constants in code and in this file

## Privacy and Compliance Qualification
- Synthetic only
- No real patient identifiers
- No real supplier secrets or credentials
- No accidental linkage to identifiable real persons

## Implementation Notes (Project-Specific)
- Primary generation file: backend/database/seed.py
- DB schema reference: backend/database/schema.sql
- ORM reference: backend/database/models.py

## Execution Workflow
1. Initialize DB schema
2. Run seed generation
3. Validate row counts and constraints
4. Train models
5. Verify model metrics are populated
6. Run API and dashboard sanity checks

## Done Definition
Task is complete when:
1. Dataset meets realism envelope and qualification criteria
2. Seeder is reproducible and idempotent
3. Backend model training succeeds on generated data
4. Dashboard endpoints return coherent, non-placeholder metrics
5. Validation summary is documented and reviewed
