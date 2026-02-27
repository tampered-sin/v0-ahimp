-- =============================================================================
-- AHIMP – AI-Based Hospital Inventory Management & Prediction
-- Full 14-Table PostgreSQL/SQLite Schema
-- =============================================================================

-- ─── 5.1 Master Tables ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS Departments (
    department_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    department_name VARCHAR(100) NOT NULL,
    location        VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS Suppliers (
    supplier_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_name     VARCHAR(150) NOT NULL,
    contact_email     VARCHAR(150),
    contact_phone     VARCHAR(20),
    avg_lead_time_days INTEGER,
    reliability_score REAL
);

CREATE TABLE IF NOT EXISTS Items (
    item_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    item_name          VARCHAR(150) NOT NULL,
    category           VARCHAR(100),
    unit_type          VARCHAR(50),
    safety_stock_level INTEGER,
    reorder_point      INTEGER
);

-- ─── 5.2 Inventory & Batch Tables ────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS Batches (
    batch_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id           INTEGER NOT NULL REFERENCES Items(item_id),
    supplier_id       INTEGER NOT NULL REFERENCES Suppliers(supplier_id),
    manufacture_date  DATE,
    expiry_date       DATE,
    purchase_price    REAL,
    quantity_received INTEGER
);

CREATE TABLE IF NOT EXISTS Inventory_Stock (
    stock_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id          INTEGER NOT NULL REFERENCES Items(item_id),
    batch_id         INTEGER NOT NULL REFERENCES Batches(batch_id),
    department_id    INTEGER NOT NULL REFERENCES Departments(department_id),
    current_quantity INTEGER NOT NULL,
    last_updated     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─── 5.3 Procurement Tables ──────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS Purchase_Orders (
    po_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id       INTEGER REFERENCES Suppliers(supplier_id),
    order_date        DATE,
    expected_delivery DATE,
    status            VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS Goods_Receipts (
    grn_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    po_id         INTEGER REFERENCES Purchase_Orders(po_id),
    received_date DATE,
    verified_by   VARCHAR(100)
);

-- ─── 5.4 Core ML Table ───────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS Consumption_Records (
    consumption_id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id        INTEGER NOT NULL REFERENCES Items(item_id),
    batch_id       INTEGER REFERENCES Batches(batch_id),
    department_id  INTEGER REFERENCES Departments(department_id),
    quantity_used  INTEGER,
    usage_date     DATE,
    patient_type   VARCHAR(50)
);

-- ─── 5.5 Equipment Tables ────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS Equipment (
    equipment_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_name VARCHAR(150),
    serial_number  VARCHAR(150),
    department_id  INTEGER REFERENCES Departments(department_id),
    purchase_date  DATE,
    maintenance_due DATE
);

CREATE TABLE IF NOT EXISTS Equipment_Usage (
    usage_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_id INTEGER REFERENCES Equipment(equipment_id),
    usage_date   DATE,
    usage_hours  REAL
);

-- ─── 5.6 AI Prediction Tables ────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS Demand_Predictions (
    prediction_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id           INTEGER REFERENCES Items(item_id),
    prediction_date   DATE,
    predicted_quantity REAL,
    model_version     VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS Stockout_Risk (
    risk_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id          INTEGER REFERENCES Items(item_id),
    prediction_date  DATE,
    risk_probability REAL,
    risk_flag        BOOLEAN
);

CREATE TABLE IF NOT EXISTS Expiry_Risk (
    expiry_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id               INTEGER REFERENCES Batches(batch_id),
    prediction_date        DATE,
    expiry_risk_probability REAL,
    high_risk_flag         BOOLEAN
);

-- ─── 5.7 Audit & Cost Analysis ───────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS Inventory_Audit_Log (
    audit_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id          INTEGER REFERENCES Items(item_id),
    batch_id         INTEGER REFERENCES Batches(batch_id),
    old_quantity     INTEGER,
    new_quantity     INTEGER,
    updated_by       VARCHAR(100),
    update_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS Cost_Analysis (
    cost_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id          INTEGER REFERENCES Items(item_id),
    holding_cost     REAL,
    shortage_cost    REAL,
    expiry_loss_cost REAL,
    estimated_savings REAL
);
