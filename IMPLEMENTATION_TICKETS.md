# AHIMP Implementation Tickets (Jira-style)

## EPIC-1: ML Model Enhancements & Optimization
**Epic ID:** EPIC-1
**Status:** Not Started
**Priority:** HIGH
**Timeline:** Week 1-2
**Assignee:** ML Engineering Team

---

## TICKET: TASK-101
**Title:** Migrate XGBoost to LightGBM for Demand Forecasting
**Type:** Task
**Status:** Completed
**Priority:** HIGH
**Story Points:** 13
**Sprint:** Sprint 1
**Assignee:** [ML Engineer]
**Due Date:** Week 1, Day 3

**Description:**
Replace current XGBoost demand model with LightGBM to achieve 3-5x faster training and +5-15% accuracy improvement on 7.3M consumption records.

**Acceptance Criteria:**
- [x] LightGBM 4.0+ installed in requirements.txt
- [x] New `backend/models/lightgbm_model.py` created with:
  - [x] Model training function with optimal hyperparameters
  - [x] Feature importance calculations
  - [x] Cross-validation pipeline (5-fold)
  - [x] Model persistence (pkl format)
- [x] Performance benchmarks recorded:
  - [x] Training time: <5 minutes for 7.3M records
  - [x] Inference time: <50ms per item
  - [x] R² score: ≥0.97
- [x] Backward compatible with existing API (`/api/demand-forecast`)
- [x] Unit tests passing (95%+ code coverage)
- [x] Documentation updated in README

**Tasks:**
1. Install LightGBM: `pip install lightgbm==4.0.0`
2. Create `backend/models/lightgbm_model.py`
3. Implement `train()` function with hyperparameters
4. Add feature importance output
5. Benchmark vs XGBoost
6. Update `backend/main.py` startup sequence
7. Add `/api/model-comparison` diagnostic endpoint
8. Write unit tests
9. Update README docs

**Dependencies:**
- TASK-102 (Feature normalization)

**Related Issues:**
- Better performance for hospital scale

---

## TICKET: TASK-102
**Title:** Add CatBoost Model with Categorical Feature Support
**Type:** Task
**Status:** In Progress
**Priority:** HIGH
**Story Points:** 8
**Sprint:** Sprint 1
**Assignee:** [ML Engineer]
**Due Date:** Week 1, Day 5

**Description:**
Implement CatBoost model to handle categorical features (supplier_id, department_id, category) natively without label encoding, improving model interpretability and training speed.

**Acceptance Criteria:**
- [ ] CatBoost 1.2+ installed
- [ ] `backend/models/catboost_model.py` created
- [ ] Categorical features defined:
  - [ ] supplier_id
  - [ ] department_id
  - [ ] category
  - [ ] patient_type
- [ ] Model training with cat_features parameter
- [ ] Feature importance with categorical insights
- [ ] R² score: ≥0.96
- [ ] Training time: <3 minutes
- [ ] Integration tests with real data

**Tasks:**
1. Install CatBoost: `pip install catboost==1.2.0`
2. Create `backend/models/catboost_model.py`
3. Define categorical feature indices
4. Implement training with early stopping
5. Add SHAP integration for interpretability
6. Benchmark performance
7. Create comparison notebook
8. Document categorical handling

**Dependencies:**
- TASK-101 completed

**Blocks:**
- TASK-105 (Ensemble model)

---

## TICKET: TASK-103
**Title:** Implement LSTM/GRU Time-Series Model for Seasonal Forecasting
**Type:** Task
**Status:** Not Started
**Priority:** MEDIUM
**Story Points:** 21
**Sprint:** Sprint 1-2
**Assignee:** [ML Engineer / Deep Learning Specialist]
**Due Date:** Week 2, Day 3

**Description:**
Build LSTM/GRU neural network to capture temporal patterns, seasonal cycles, and non-linear relationships in consumption data for 14-day demand forecasting.

**Acceptance Criteria:**
- [ ] TensorFlow 2.13+ and Keras installed
- [ ] `backend/models/lstm_model.py` created
- [ ] Model architecture:
  - [ ] Input shape: (14-day lookback, 10 features)
  - [ ] LSTM layer: 64 units + 0.2 dropout
  - [ ] LSTM layer: 32 units + 0.2 dropout
  - [ ] Dense layer: 16 units
  - [ ] Output layer: 14 predictions (14-day forecast)
- [ ] Training pipeline:
  - [ ] Sequence generation from time-series data
  - [ ] 80/20 train-test split
  - [ ] Early stopping callback
  - [ ] Model checkpointing
- [ ] Performance metrics:
  - [ ] R² ≥ 0.95
  - [ ] MAE ≤ 6.5
  - [ ] Training time: <10 minutes
- [ ] Model serialization (h5 format)
- [ ] Inference time: <100ms per batch

**Tasks:**
1. Install TensorFlow/Keras: `pip install tensorflow==2.13.0`
2. Create `backend/data/sequence_generator.py`
3. Create `backend/models/lstm_model.py`
4. Implement build_lstm_model() function
5. Add data preprocessing pipeline
6. Implement training loop with callbacks
7. Add prediction function
8. Create comparison with XGBoost on volatile items
9. Write integration tests
10. Document architecture and hyperparameters

**Dependencies:**
- TASK-101 (Feature pipeline ready)

**Blocks:**
- TASK-105 (Ensemble voting)

**Notes:**
- Test on high-volatility items (blood bank, emergency supplies)
- May require GPU acceleration for 7.3M records

---

## TICKET: TASK-104
**Title:** Add Anomaly Detection with Isolation Forest
**Type:** Task
**Status:** Not Started
**Priority:** MEDIUM
**Story Points:** 5
**Sprint:** Sprint 1
**Assignee:** [ML Engineer]
**Due Date:** Week 1, Day 4

**Description:**
Implement Isolation Forest to detect data entry errors, equipment malfunctions, and unusual consumption patterns that could skew ML models.

**Acceptance Criteria:**
- [ ] `backend/models/anomaly_detector.py` created
- [ ] Detector trained on historical consumption data
- [ ] Contamination parameter: 5% (95th percentile as normal)
- [ ] Detects >3σ deviations:
  - [ ] Sudden 10x consumption spike
  - [ ] Zero consumption when baseline high
  - [ ] Department-specific anomalies
- [ ] Integration with data ingestion pipeline
- [ ] Alert API endpoint: `/api/anomalies/recent`
- [ ] Pharmacist dashboard notification (email/SMS)
- [ ] Unit tests for known anomalies

**Tasks:**
1. Install IForest (included in scikit-learn)
2. Create `backend/models/anomaly_detector.py`
3. Implement `train()` on consumption data
4. Add `detect()` function
5. Create alerting logic
6. Add to `/api/consumption/ingest` workflow
7. Create test cases with synthetic anomalies
8. Document business logic

**Dependencies:**
- None

**Related Items:**
- TASK-201 (Data ingestion agent will use this)

---

## TICKET: TASK-105
**Title:** Build Ensemble Model with Voting Predictor
**Type:** Task
**Status:** Not Started
**Priority:** HIGH
**Story Points:** 8
**Sprint:** Sprint 2
**Assignee:** [ML Engineer]
**Due Date:** Week 2, Day 5

**Description:**
Combine XGBoost, LightGBM, LSTM, and Linear Regression predictions using weighted voting to achieve 97%+ R² accuracy.

**Acceptance Criteria:**
- [ ] `backend/models/ensemble_model.py` created
- [ ] Voting weights tuned via cross-validation:
  - [ ] XGBoost: 0.4
  - [ ] LightGBM: 0.3
  - [ ] LSTM: 0.2
  - [ ] Linear Regression: 0.1
- [ ] Ensemble R² score: ≥0.97 (vs 0.986 baseline)
- [ ] Maintains inference speed: <100ms per item
- [ ] Model stacking with meta-learner (optional)
- [ ] Fallback to best single model if any fails

**Tasks:**
1. Create `backend/models/ensemble_model.py`
2. Implement `VotingPredictor` class
3. Load individual models
4. Implement weighted voting logic
5. Add confidence scoring (std dev of predictions)
6. Tune weights via Optuna (TASK-106)
7. Create `/api/ensemble-forecast` endpoint
8. Add comparison dashboard
9. Unit tests

**Dependencies:**
- TASK-101 (LightGBM)
- TASK-102 (CatBoost)
- TASK-103 (LSTM)

**Blocks:**
- TASK-107 (Explainability with SHAP)

---

## TICKET: TASK-106
**Title:** Implement Hyperparameter Tuning with Optuna
**Type:** Task
**Status:** Not Started
**Priority:** MEDIUM
**Story Points:** 13
**Sprint:** Sprint 2
**Assignee:** [ML Engineer]
**Due Date:** Week 2, Day 4

**Description:**
Use Optuna to automatically find optimal hyperparameters for LightGBM, CatBoost, and LSTM models. Reduce manual tuning and improve model performance by 2-5%.

**Acceptance Criteria:**
- [ ] Optuna 3.0+ installed
- [ ] `backend/models/hyperparameter_tuning.py` created
- [ ] Trial objectives:
  - [ ] LightGBM: maximize R² on validation set
  - [ ] CatBoost: maximize R² on validation set
  - [ ] LSTM: minimize MAE on test set
- [ ] Search space defined:
  - [ ] n_estimators: 100-500
  - [ ] max_depth: 3-10
  - [ ] learning_rate: 0.01-0.3
  - [ ] subsample: 0.5-1.0
- [ ] Minimum 100 trials per model
- [ ] Results logged to database
- [ ] Top 3 parameter sets recorded
- [ ] Performance improvement: +2-5%

**Tasks:**
1. Install Optuna: `pip install optuna==3.0.0`
2. Create `backend/models/hyperparameter_tuning.py`
3. Define objective functions for each model
4. Set up Optuna study with:
   - [ ] Sampler: TPESampler
   - [ ] Pruner: SuccessiveHalvingPruner
   - [ ] 100 trials minimum
5. Run optimization (may take 4-6 hours)
6. Log best params to `backend/models/best_params.json`
7. Compare with manual params
8. Document trials and results
9. Create optimization report

**Dependencies:**
- TASK-101, TASK-102, TASK-103

**Notes:**
- Consider running overnight due to 100+ trials
- GPU acceleration recommended

---

## TICKET: TASK-107
**Title:** Add SHAP & LIME Explainability Layer
**Type:** Task
**Status:** Not Started
**Priority:** HIGH
**Story Points:** 13
**Sprint:** Sprint 2
**Assignee:** [ML Engineer]
**Due Date:** Week 2, Day 5

**Description:**
Implement SHAP values and LIME for model explainability, enabling pharmacists/doctors to understand why the system makes predictions (regulatory compliance + trust).

**Acceptance Criteria:**
- [ ] SHAP 0.42+ and LIME installed
- [ ] `backend/models/explainability.py` created
- [ ] SHAP features:
  - [ ] TreeExplainer for tree-based models
  - [ ] Feature importance ranking
  - [ ] Individual prediction explanations
  - [ ] Force plots for top features
- [ ] LIME features:
  - [ ] Local explanations for any prediction
  - [ ] Interpretable classifier
  - [ ] Feature weights for individual instances
- [ ] `/api/explain/item/{item_id}` endpoint
- [ ] `/api/explain/prediction/{prediction_id}` endpoint
- [ ] Frontend visualization support (JSON format)
- [ ] Documentation for stakeholders

**Tasks:**
1. Install dependencies: `pip install shap==0.42.0 lime`
2. Create `backend/models/explainability.py`
3. Implement `SHAPExplainer` class
4. Implement `LIMEExplainer` class
5. Pre-compute SHAP background data (~1000 samples)
6. Create explanation caching (avoid recomputation)
7. Add API endpoints
8. Create visualization templates
9. Write stakeholder documentation
10. Add unit tests

**Dependencies:**
- ALL ML models (TASK-101 through TASK-105)

**Notes:**
- SHAP computation can be slow; plan for background processing
- Consider SHAP background sampling to speed up

---

## EPIC-2: AI-Powered Data Ingestion Agent
**Epic ID:** EPIC-2
**Status:** Not Started
**Priority:** HIGH
**Timeline:** Week 3
**Assignee:** AI/Backend Team

---

## TICKET: TASK-201
**Title:** Set Up CrewAI Framework & LLM Integration
**Type:** Task
**Status:** Not Started
**Priority:** HIGH
**Story Points:** 8
**Sprint:** Sprint 3
**Assignee:** [Backend Engineer]
**Due Date:** Week 3, Day 1

**Description:**
Initialize CrewAI framework and configure OpenAI GPT-4 integration for AI agent orchestration.

**Acceptance Criteria:**
- [ ] CrewAI 0.3+ installed
- [ ] LangChain 0.1+ installed
- [ ] `backend/agents/__init__.py` created
- [ ] `backend/agents/config.py` created with:
  - [ ] OpenAI API key configuration
  - [ ] LLM model selection (gpt-4-turbo)
  - [ ] Temperature & other params
- [ ] Agent base class created
- [ ] Tool registry system implemented
- [ ] Logging configured for agent execution
- [ ] Unit tests for framework

**Tasks:**
1. Install CrewAI: `pip install crewai==0.3.0`
2. Install LangChain: `pip install langchain==0.1.0`
3. Create `backend/agents/__init__.py`
4. Create `backend/agents/config.py`
5. Add OpenAI API credentials to `.env`
6. Create base `Agent` class
7. Create `Task` runner
8. Create `Crew` orchestrator
9. Add logging/monitoring
10. Write integration tests

**Dependencies:**
- None

**Environment Setup:**
```bash
OPENAI_API_KEY=sk-...
GPT_MODEL=gpt-4-turbo
CREW_LOG_LEVEL=INFO
```

**Cost Estimate:**
- ~$1-2/day in API calls (based on usage)

---

## TICKET: TASK-202
**Title:** Build Data Ingestion Agent with CSV/API Support
**Type:** Task
**Status:** Not Started
**Priority:** HIGH
**Story Points:** 13
**Sprint:** Sprint 3
**Assignee:** [AI Engineer]
**Due Date:** Week 3, Day 3

**Description:**
Create AI agent to autonomously ingest consumption records from CSV files and APIs, validate data quality, and feed ML pipeline.

**Acceptance Criteria:**
- [ ] `backend/agents/data_ingestion_agent.py` created
- [ ] Agent capabilities:
  - [ ] Read CSV files from `/data/uploads/`
  - [ ] Parse API responses (JSON/XML)
  - [ ] Validate schema:
    - [ ] Required columns: item_id, quantity_used, usage_date
    - [ ] Data types correct
    - [ ] Date range valid
  - [ ] Duplicate detection
  - [ ] Anomaly detection (>3σ)
  - [ ] Auto-fix minor issues (whitespace, case)
- [ ] Processing pipeline:
  - [ ] 1000+ records/sec throughput
  - [ ] Transaction rollback on errors
  - [ ] Progress logging
- [ ] Error handling:
  - [ ] Partial ingestion with alerts
  - [ ] Retry logic for transient failures
  - [ ] Email alerts to admin
- [ ] `/api/agents/data-ingestion` endpoint

**Tasks:**
1. Create `backend/agents/data_ingestion_agent.py`
2. Define agent role, goal, backstory
3. Create tools:
   - [ ] `read_csv_tool`
   - [ ] `parse_api_tool`
   - [ ] `validate_data_tool`
   - [ ] `detect_anomalies_tool`
   - [ ] `ingest_database_tool`
4. Implement validation rules
5. Create error recovery logic
6. Add progress tracking
7. Create `/api/agents/data-ingestion` endpoint
8. Add background task for async processing
9. Write integration tests with sample data
10. Document ingestion formats

**Dependencies:**
- TASK-201 (CrewAI setup)
- TASK-104 (Anomaly detection)

**File to Handle:**
- CSV format: `item_id,quantity_used,usage_date,department_id,patient_type`

---

## TICKET: TASK-203
**Title:** Implement Data Validation & Anomaly Detection for Ingestion
**Type:** Task
**Status:** Not Started
**Priority:** HIGH
**Story Points:** 8
**Sprint:** Sprint 3
**Assignee:** [Backend Engineer]
**Due Date:** Week 3, Day 4

**Description:**
Create robust validation rules and anomaly detection for data ingestion to ensure ML models receive clean, reliable data.

**Acceptance Criteria:**
- [ ] `backend/database/data_validation.py` created
- [ ] Validation rules:
  - [ ] item_id exists in Items table
  - [ ] quantity_used ≥ 0 and ≤ 100,000
  - [ ] usage_date within last 90 days
  - [ ] department_id valid
  - [ ] No duplicate records (item_id + date + dept)
- [ ] Anomaly scoring:
  - [ ] >3σ from item mean = RED
  - [ ] >2σ = YELLOW
  - [ ] Auto-flag for manual review if RED
- [ ] Quarantine table for suspicious records
- [ ] Admin dashboard to review/approve flagged records

**Tasks:**
1. Create `backend/database/data_validation.py`
2. Implement validation functions
3. Create `consumption_record_audit` table
4. Add quarantine logic
5. Implement statistical thresholds
6. Create review approval workflow
7. Add email alerts
8. Create `/api/admin/ingestion-audit` endpoint
9. Write validation tests

**Dependencies:**
- TASK-202 (Data ingestion agent)
- TASK-104 (Anomaly detection)

---

## EPIC-3: Supply Chain AI Agent & Automated Purchasing
**Epic ID:** EPIC-3
**Status:** Not Started
**Priority:** HIGH
**Timeline:** Week 4
**Assignee:** Supply Chain / AI Team

---

## TICKET: TASK-301
**Title:** Implement Supplier Scoring Algorithm
**Type:** Task
**Status:** Not Started
**Priority:** HIGH
**Story Points:** 13
**Sprint:** Sprint 4
**Assignee:** [Supply Chain Engineer]
**Due Date:** Week 4, Day 2

**Description:**
Build composite supplier scoring algorithm considering reliability, pricing, delivery performance, distance, and sentiment analysis for data-driven supplier selection.

**Acceptance Criteria:**
- [ ] `backend/agents/supplier_scoring.py` created
- [ ] Scoring formula (100-point scale):
  - [ ] Reliability rating: 30% weight
  - [ ] On-time delivery %: 25% weight
  - [ ] Price competitiveness: 20% weight
  - [ ] Distance penalty: 15% weight
  - [ ] Reviews sentiment: 10% weight
- [ ] Output: Ranked supplier list with scores
- [ ] All suppliers scored consistently
- [ ] Score reproducible and auditable
- [ ] Historical score tracking

**Tasks:**
1. Create `backend/agents/supplier_scoring.py`
2. Define Supplier data class
3. Implement normalization function (0-100)
4. Implement price normalization (market comparison)
5. Implement distance penalty (0-500km)
6. Implement sentiment scoring (NLP)
7. Implement composite score calculation
8. Add score caching (refresh daily)
9. Create `/api/suppliers/scoring` endpoint
10. Write unit tests with known suppliers

**Dependencies:**
- Supplier table populated with 8+ suppliers

**Sample Output:**
```json
{
  "item_id": 1,
  "suppliers": [
    {"name": "MedPharm", "score": 87.5},
    {"name": "BioLab", "score": 72.3},
    {"name": "SafeGuard", "score": 81.2}
  ]
}
```

---

## TICKET: TASK-302
**Title:** Add NLP Sentiment Analysis for Supplier Reviews
**Type:** Task
**Status:** Not Started
**Priority:** MEDIUM
**Story Points:** 8
**Sprint:** Sprint 4
**Assignee:** [ML Engineer]
**Due Date:** Week 4, Day 2

**Description:**
Integrate sentiment analysis (NLP) to analyze supplier reviews and feedback, converting qualitative data into quantitative scores for supplier scoring.

**Acceptance Criteria:**
- [ ] Sentiment library installed (transformers/TextBlob)
- [ ] `backend/agents/sentiment_analyzer.py` created
- [ ] Score range: -1 to +1 (converted to 0-100)
- [ ] Handles:
  - [ ] Positive reviews (4-5★): +1.0
  - [ ] Neutral reviews (3★): 0.0
  - [ ] Negative reviews (1-2★): -1.0
- [ ] Batch processing of 1000+ reviews/sec
- [ ] Caching of analyzed reviews
- [ ] Integration with supplier_scoring.py

**Tasks:**
1. Install transformers: `pip install transformers`
2. Create `backend/agents/sentiment_analyzer.py`
3. Use huggingface model for classification
4. Create `analyze_sentiment()` function
5. Add batch processing
6. Create caching layer
7. Implement score normalization
8. Add unit tests
9. Document model choice

**Dependencies:**
- TASK-301 (Supplier scoring)

**Model Choice:**
- `distilbert-base-uncased-finetuned-sst-2-english` (fast, accurate)

---

## TICKET: TASK-303
**Title:** Build Supply Chain Agent for Stockout Prevention
**Type:** Task
**Status:** Not Started
**Priority:** HIGH
**Story Points:** 21
**Sprint:** Sprint 4
**Assignee:** [AI Engineer]
**Due Date:** Week 4, Day 5

**Description:**
Create AI agent to autonomously monitor stockout risk, select best suppliers, create purchase orders, and manage procurement workflow.

**Acceptance Criteria:**
- [ ] `backend/agents/supply_chain_agent.py` created
- [ ] Agent workflow:
  - [ ] Check all items hourly for stockout risk > 70%
  - [ ] For each at-risk item:
    1. Score all suppliers
    2. Select top supplier
    3. Calculate optimal order quantity
    4. Create PO
    5. Send to supplier
    6. Track delivery
- [ ] Decision transparency:
  - [ ] Log reason for supplier selection
  - [ ] Document scoring breakdown
  - [ ] Auto-approval workflow (optional escalation)
- [ ] `/api/agents/supply-chain/at-risk` endpoint
- [ ] `/api/agents/supply-chain/auto-purchase` endpoint (manual trigger)
- [ ] Performance: <30sec per cycle

**Tasks:**
1. Create `backend/agents/supply_chain_agent.py`
2. Define agent role, goal, backstory
3. Create tools:
   - [ ] `check_stockout_risk_tool`
   - [ ] `score_suppliers_tool`
   - [ ] `calculate_order_qty_tool`
   - [ ] `create_po_tool`
   - [ ] `send_to_supplier_tool`
   - [ ] `track_delivery_tool`
4. Implement stockout monitoring loop
5. Add supplier selection logic
6. Implement PO generation
7. Add EDI/Email sender integration
8. Create approval workflow
9. Add logging and audit trail
10. Write integration tests

**Dependencies:**
- TASK-301 (Supplier scoring)
- TASK-201 (CrewAI setup)

---

## TICKET: TASK-304
**Title:** Implement Purchase Order Generation & Submission
**Type:** Task
**Status:** Not Started
**Priority:** HIGH
**Story Points:** 13
**Sprint:** Sprint 4
**Assignee:** [Backend Engineer]
**Due Date:** Week 4, Day 4

**Description:**
Create automated PO generation, validation, and submission logic to suppliers via EDI, email, or API.

**Acceptance Criteria:**
- [ ] `backend/agents/purchase_order_agent.py` created
- [ ] PO generation:
  - [ ] Calculate reorder point + safety stock
  - [ ] Determine optimal order quantity
  - [ ] Calculate total cost
  - [ ] Apply supplier discounts (if any)
- [ ] PO validation:
  - [ ] Budget approval (if >threshold)
  - [ ] Supplier availability check
  - [ ] No duplicate orders (last 7 days)
- [ ] Submission methods:
  - [ ] EDI format (EANCOM)
  - [ ] Email with attachment
  - [ ] Supplier API (REST)
- [ ] Tracking:
  - [ ] PO status database
  - [ ] Expected delivery date
  - [ ] Delivery tracking correlation
- [ ] Alerts:
  - [ ] Procurement team notification
  - [ ] Delayed delivery alerts
  - [ ] Delivery confirmation

**Tasks:**
1. Create `backend/agents/purchase_order_agent.py`
2. Create `generate_po()` function
3. Implement quantity calculation:
   - [ ] Reorder point
   - [ ] Safety stock (1.5x reorder point)
   - [ ] Current stock check
4. Create `validate_po()` function
5. Implement supplier submission:
   - [ ] CSV export for manual orders
   - [ ] Email sender
   - [ ] REST API client
6. Create `purchase_orders` table with tracking
7. Add PO approval workflow
8. Create `/api/purchase-orders` CRUD endpoints
9. Write integration tests
10. Document PO format

**Dependencies:**
- TASK-303 (Supply chain agent)

**Database Schema:**
```sql
purchase_orders:
  po_id, supplier_id, item_id, quantity,
  order_date, expected_delivery,
  status, total_cost, created_by
```

---

## TICKET: TASK-305
**Title:** Build Delivery Tracking & Delay Alert System
**Type:** Task
**Status:** Not Started
**Priority:** MEDIUM
**Story Points:** 8
**Sprint:** Sprint 4
**Assignee:** [Backend Engineer]
**Due Date:** Week 4, Day 5

**Description:**
Implement delivery tracking to monitor PO status, detect delays, and alert procurement team for proactive Follow-up.

**Acceptance Criteria:**
- [ ] `backend/agents/delivery_tracker.py` created
- [ ] Tracking states:
  - [ ] PENDING (order created)
  - [ ] CONFIRMED (supplier acknowledged)
  - [ ] IN_TRANSIT (left warehouse)
  - [ ] DELIVERED (received)
  - [ ] DELAYED (past due date)
  - [ ] CANCELLED
- [ ] Alert logic:
  - [ ] 2 days before due: yellow alert
  - [ ] 1 day past due: red alert
  - [ ] 3 days past due: escalation email
- [ ] Integration:
  - [ ] Supplier API tracking
  - [ ] Manual status updates
  - [ ] Barcode scanning (if available)
- [ ] Dashboard view: `/api/deliveries/status`
- [ ] Alert recipient configuration

**Tasks:**
1. Create `backend/agents/delivery_tracker.py`
2. Create delivery status model
3. Implement tracking state machine
4. Add alert triggers
5. Create supplier API integration
6. Add manual tracking interface
7. Implement `/api/deliveries/status` endpoint
8. Create alert notification system
9. Write tests for state transitions
10. Add notification history

**Dependencies:**
- TASK-304 (PO generation)

---

## EPIC-4: API Endpoints & Dashboard Integration
**Epic ID:** EPIC-4
**Status:** Not Started
**Priority:** HIGH
**Timeline:** Week 5
**Assignee:** Backend & Frontend Team

---

## TICKET: TASK-401
**Title:** Create Agent Management API Endpoints
**Type:** Task
**Status:** Not Started
**Priority:** HIGH
**Story Points:** 8
**Sprint:** Sprint 5
**Assignee:** [Backend Engineer]
**Due Date:** Week 5, Day 1

**Description:**
Build FastAPI endpoints for agent management, monitoring, and manual intervention.

**Acceptance Criteria:**
- [ ] `backend/api/agents.py` created
- [ ] Endpoints:
  - [ ] `POST /api/agents/data-ingestion` (trigger)
  - [ ] `GET /api/agents/data-ingestion/status` (status)
  - [ ] `GET /api/agents/supply-chain/at-risk` (at-risk items)
  - [ ] `POST /api/agents/supply-chain/optimize` (trigger)
  - [ ] `GET /api/agents/logs` (execution logs)
  - [ ] `GET /api/agents/dashboard` (summary)
- [ ] Error handling with proper HTTP codes
- [ ] Request validation (Pydantic)
- [ ] Rate limiting (100 req/min)
- [ ] Authentication (API key or JWT)

**Tasks:**
1. Create `backend/api/agents.py`
2. Implement data ingestion endpoints
3. Implement supply chain endpoints
4. Add logging endpoints
5. Add dashboard summary endpoint
6. Add error handling
7. Add rate limiting middleware
8. Add authentication middleware
9. Write endpoint tests
10. Update OpenAPI docs

**Dependencies:**
- TASK-201 (CrewAI)
- TASK-202 (Data agent)
- TASK-303 (Supply chain agent)

---

## TICKET: TASK-402
**Title:** Add Agent Execution Logging & Audit Trail
**Type:** Task
**Status:** Not Started
**Priority:** MEDIUM
**Story Points:** 5
**Sprint:** Sprint 5
**Assignee:** [Backend Engineer]
**Due Date:** Week 5, Day 2

**Description:**
Implement comprehensive logging for all agent actions for audit, debugging, and regulatory compliance.

**Acceptance Criteria:**
- [ ] `backend/database/agent_logs` table created
- [ ] Fields:
  - [ ] agent_name, task_description
  - [ ] status (running, success, failed)
  - [ ] created_at, completed_at
  - [ ] result (JSON)
  - [ ] errors (JSON)
- [ ] Log levels: DEBUG, INFO, WARNING, ERROR
- [ ] Retention: 90 days rolling archive
- [ ] Query interface: `/api/agents/logs`
- [ ] Full text search on descriptions

**Tasks:**
1. Create `agent_logs` table
2. Create logging utilities
3. Add decorators for agent tracking
4. Implement log persistence
5. Add log archival
6. Create log query API
7. Add log export (CSV/JSON)
8. Write tests
9. Document log format

**Dependencies:**
- All agent tickets

---

## TICKET: TASK-501
**Title:** Build Agent Dashboard UI Components (Frontend)
**Type:** Task
**Status:** Not Started
**Priority:** HIGH
**Story Points:** 21
**Sprint:** Sprint 5
**Assignee:** [Frontend Engineer]
**Due Date:** Week 5, Day 5

**Description:**
Create React components in Next.js for agent monitoring, at-risk items, supplier recommendations, and PO management.

**Acceptance Criteria:**
- [ ] Create new page: `/agents`
- [ ] Components:
  - [ ] AgentDashboard (main hub)
  - [ ] DataIngestionStatus (recent ingestions)
  - [ ] AtRiskItems (stockout risk table)
  - [ ] SupplierRecommendations (scores + details)
  - [ ] POTracker (delivery status)
  - [ ] AgentLogs (execution history)
- [ ] Features:
  - [ ] Real-time updates (WebSocket or polling)
  - [ ] Manual agent triggers
  - [ ] Filter/search capabilities
  - [ ] Drill-down details
- [ ] Responsive design (mobile-friendly)
- [ ] Dark/light theme support

**Tasks:**
1. Create `app/agents/page.tsx`
2. Create `components/agents/AgentDashboard.tsx`
3. Create `components/agents/AtRiskItems.tsx`
4. Create `components/agents/SupplierRecommendations.tsx`
5. Create `components/agents/POTracker.tsx`
6. Create `components/agents/AgentLogs.tsx`
7. Add real-time WebSocket connection
8. Add manual trigger buttons
9. Add filtering/sorting
10. Add responsive styling

**Dependencies:**
- TASK-401 (API endpoints)

---

## TICKET: TASK-502
**Title:** Implement Manual Approval Workflow for Auto-POs
**Type:** Task
**Status:** Not Started
**Priority:** HIGH
**Story Points:** 8
**Sprint:** Sprint 5
**Assignee:** [Backend + Frontend Engineer]
**Due Date:** Week 5, Day 4

**Description:**
Create approval workflow for critical or high-value purchase orders before submission to suppliers.

**Acceptance Criteria:**
- [ ] PO approval workflow:
  - [ ] Auto-approved: <$5000, high-reliability supplier
  - [ ] Manual approval: ≥$5000 or new supplier
  - [ ] Escalation: >$50000 (manager approval)
- [ ] Approval UI:
  - [ ] PO details page with scoring breakdown
  - [ ] Approve/Reject buttons
  - [ ] Comments field
  - [ ] Audit trail
- [ ] Notification:
  - [ ] Email to approvers
  - [ ] In-app notifications
  - [ ] SMS for urgent (if configured)
- [ ] Timeout: Auto-approve if pending >24hrs

**Tasks:**
1. Create approval state machine
2. Add PO approval status field
3. Create approval rules engine
4. Build approval UI page
5. Add notification system
6. Implement email alerts
7. Add audit logging
8. Create `/api/approval-queue` endpoint
9. Write tests
10. Document approval rules

**Dependencies:**
- TASK-304 (PO generation)
- TASK-501 (Dashboard UI)

---

## Summary Table

| EPIC | Tickets | Total Story Points | Timeline |
|------|---------|-------------------|----------|
| EPIC-1: ML Enhancements | TASK-101 to TASK-107 | 86 points | Week 1-2 |
| EPIC-2: Data Agent | TASK-201 to TASK-203 | 29 points | Week 3 |
| EPIC-3: Supply Chain Agent | TASK-301 to TASK-305 | 63 points | Week 4 |
| EPIC-4: API & Dashboard | TASK-401 to TASK-502 | 50 points | Week 5 |
| **TOTAL** | **20 tickets** | **228 points** | **5 weeks** |

## Dependencies Flow

```
TASK-101 ──┐
TASK-102 ──┼──→ TASK-105 (Ensemble) ──→ TASK-107 (SHAP)
TASK-103 ──┘
TASK-104 ──→ TASK-202 (Data agent)
TASK-201 ──→ TASK-202, TASK-303
TASK-201 ──→ TASK-301 ──→ TASK-303
TASK-302 ──→ TASK-301
TASK-303 ──→ TASK-304
TASK-304 ──→ TASK-305, TASK-502
TASK-401 ──→ TASK-402
TASK-401 ──→ TASK-501 ──→ TASK-502
```

## Team Allocation

**Recommended Sprint Teams:**

- **Sprint 1-2 (ML):** 2 ML Engineers + 1 Data Scientist
- **Sprint 3 (Data Agent):** 1 AI Engineer + 1 Backend Engineer
- **Sprint 4 (Supply Chain):** 2 Backend Engineers + 1 Supply Chain Specialist
- **Sprint 5 (API/UI):** 1 Backend Engineer + 2 Frontend Engineers

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| **Long training times** | Run Optuna overnight; use GPU acceleration |
| **LLM API costs** | Implement rate limiting; use async batching |
| **Data quality issues** | Comprehensive validation + anomaly detection |
| **Supplier API integration** | Build fallback (email/manual) |
| **Concurrent PO requests** | Transaction locking + queue system |

---

## Definition of Done

✅ Code reviewed (2 approvals)
✅ Unit tests (>90% coverage)
✅ Integration tests passing
✅ Documentation updated
✅ API docs (Swagger) updated
✅ Deployed to staging
✅ QA sign-off
✅ Monitoring/alerts configured
