-- =============================================================================
-- AHIMP – AI-Based Hospital Inventory Management & Prediction
-- Full relational schema including ingestion audit quarantine table
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

CREATE TABLE IF NOT EXISTS Purchase_Order_Details (
    detail_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    po_id              INTEGER NOT NULL REFERENCES Purchase_Orders(po_id),
    item_id            INTEGER NOT NULL REFERENCES Items(item_id),
    quantity           INTEGER NOT NULL,
    unit_price         REAL NOT NULL,
    discount_pct       REAL NOT NULL DEFAULT 0,
    total_cost         REAL NOT NULL,
    created_by         VARCHAR(100) NOT NULL DEFAULT 'system',
    approval_required  BOOLEAN NOT NULL DEFAULT FALSE,
    approval_status    VARCHAR(30) NOT NULL DEFAULT 'APPROVED',
    submission_method  VARCHAR(30),
    submission_status  VARCHAR(30),
    supplier_api_url   VARCHAR(255),
    submission_payload TEXT,
    tracking_reference VARCHAR(120),
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS Purchase_Order_Approvals (
    approval_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    po_id                 INTEGER NOT NULL UNIQUE REFERENCES Purchase_Orders(po_id),
    approval_level        VARCHAR(30) NOT NULL DEFAULT 'AUTO',
    approval_status       VARCHAR(30) NOT NULL DEFAULT 'AUTO_APPROVED',
    escalation_required   BOOLEAN NOT NULL DEFAULT FALSE,
    approval_reason       VARCHAR(255),
    score_breakdown       TEXT,
    rule_snapshot         TEXT,
    requested_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    due_at                TIMESTAMP,
    decided_at            TIMESTAMP,
    decided_by            VARCHAR(120),
    decision_comment      VARCHAR(500),
    notification_alert_id INTEGER,
    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS Purchase_Order_Approval_Audit (
    audit_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    po_id            INTEGER NOT NULL REFERENCES Purchase_Orders(po_id),
    event_type       VARCHAR(40) NOT NULL,
    previous_status  VARCHAR(30),
    new_status       VARCHAR(30) NOT NULL,
    actor            VARCHAR(120) NOT NULL DEFAULT 'system',
    comment          VARCHAR(500),
    metadata_json    TEXT,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_po_approvals_status ON Purchase_Order_Approvals(approval_status);
CREATE INDEX IF NOT EXISTS idx_po_approvals_level ON Purchase_Order_Approvals(approval_level);
CREATE INDEX IF NOT EXISTS idx_po_approval_audit_po_id ON Purchase_Order_Approval_Audit(po_id);
CREATE INDEX IF NOT EXISTS idx_po_approval_audit_event_type ON Purchase_Order_Approval_Audit(event_type);

CREATE TABLE IF NOT EXISTS Goods_Receipts (
    grn_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    po_id         INTEGER REFERENCES Purchase_Orders(po_id),
    received_date DATE,
    verified_by   VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS Delivery_Tracking (
    delivery_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    po_id                 INTEGER NOT NULL REFERENCES Purchase_Orders(po_id),
    tracking_reference    VARCHAR(120) NOT NULL UNIQUE,
    carrier_name          VARCHAR(80),
    status                VARCHAR(30) NOT NULL DEFAULT 'PENDING',
    expected_delivery     DATE,
    actual_delivery       DATE,
    last_event_code       VARCHAR(50),
    last_event_message    VARCHAR(255),
    last_event_at         TIMESTAMP,
    delay_reason          VARCHAR(255),
    last_alert_level_sent VARCHAR(30),
    alert_recipients      VARCHAR(1000),
    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS Delivery_Events (
    event_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    delivery_id           INTEGER NOT NULL REFERENCES Delivery_Tracking(delivery_id),
    source                VARCHAR(30) NOT NULL DEFAULT 'manual',
    external_status_code  VARCHAR(50) NOT NULL,
    reason_code           VARCHAR(50),
    normalized_status     VARCHAR(30) NOT NULL,
    event_message         VARCHAR(255),
    event_at              TIMESTAMP NOT NULL,
    raw_payload           TEXT,
    idempotency_key       VARCHAR(255) NOT NULL UNIQUE,
    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

CREATE TABLE IF NOT EXISTS Consumption_Record_Audit (
    audit_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id        INTEGER REFERENCES Items(item_id),
    department_id  INTEGER REFERENCES Departments(department_id),
    quantity_used  INTEGER,
    usage_date     DATE,
    z_score        REAL,
    severity       VARCHAR(20),
    reason         VARCHAR(255) NOT NULL,
    status         VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    source         VARCHAR(80) NOT NULL DEFAULT 'ingestion_agent',
    raw_payload    TEXT,
    reviewed_by    VARCHAR(100),
    reviewed_at    TIMESTAMP,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS Agent_Logs (
    log_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_name        VARCHAR(120) NOT NULL,
    task_description  VARCHAR(255) NOT NULL,
    status            VARCHAR(20) NOT NULL,
    level             VARCHAR(10) NOT NULL DEFAULT 'INFO',
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at      TIMESTAMP,
    result            TEXT,
    errors            TEXT
);

CREATE INDEX IF NOT EXISTS idx_agent_logs_agent ON Agent_Logs(agent_name);
CREATE INDEX IF NOT EXISTS idx_agent_logs_status ON Agent_Logs(status);
CREATE INDEX IF NOT EXISTS idx_agent_logs_task_description ON Agent_Logs(task_description);

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
