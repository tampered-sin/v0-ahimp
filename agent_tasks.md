# 🏥 Hospital Resource Management Platform — Agent Task Board
**Project:** HRMP (Hospital Resource Management Platform)
**Sprint:** Sprint 1 — Supply Chain AI Agent & Forecasting Engine
**Created:** 2026-04-08
**Team:** Backend · AI/ML · Data · DevOps

---

## EPIC INDEX

| Epic ID | Epic Name | Tickets |
|---------|-----------|---------|
| HRMP-E1 | Supply Chain AI Agent | HRMP-001 → HRMP-006 |
| HRMP-E2 | Supplier Scraping & Intelligence | HRMP-007 → HRMP-011 |
| HRMP-E3 | Reliability Scoring Engine | HRMP-012 → HRMP-014 |
| HRMP-E4 | Inventory Forecasting Engine | HRMP-015 → HRMP-020 |
| HRMP-E5 | Blood Bank & Clinical Forecasting | HRMP-021 → HRMP-023 |
| HRMP-E6 | Alerting & Observability | HRMP-024 → HRMP-026 |

---

---

# 🤖 EPIC HRMP-E1 — Supply Chain AI Agent (Llama3)

---

## HRMP-001 — Bootstrap Llama3 Agent with LangChain Tool Framework

| Field | Value |
|-------|-------|
| **Type** | Story |
| **Priority** | 🔴 Critical |
| **Status** | To Do |
| **Epic** | HRMP-E1 |
| **Assignee** | Backend/AI Engineer |
| **Story Points** | 8 |
| **Sprint** | Sprint 1 |
| **Labels** | `ai-agent` `llama3` `langchain` `backend` |

### Description
Set up the foundational Llama3-powered supply chain agent using LangChain's tool-calling framework served via Ollama. The agent will be the decision-making core for all procurement operations — querying suppliers, comparing quotes, and placing or escalating orders based on stockout risk signals.

### Background
The agent needs to be modular, explainable, and fully auditable. Every decision it makes — whether auto-ordering, suggesting, or escalating — must be logged with a full reasoning trace for compliance and audit purposes in a healthcare setting.

### Technical Approach
- Serve Llama3 (8B or 70B depending on infra) via **Ollama** on a local/on-prem GPU node
- Integrate with **LangChain** as the orchestration layer
- Define tools as LangChain `StructuredTool` objects with strict Pydantic input schemas
- Use **ReAct prompting pattern** (Reason + Act) for interpretable tool chaining
- Persist agent memory using **Redis** for short-term state across multi-step ordering flows

### Tools to Register (Phase 1)

```python
tools = [
    search_suppliers(medicine_name: str, quantity: int, location: str) -> List[Supplier],
    get_supplier_quote(supplier_id: str, items: List[OrderItem]) -> Quote,
    check_supplier_reliability(supplier_id: str) -> ReliabilityReport,
    compare_quotes(quotes: List[Quote]) -> RankedQuoteList,
    place_order(supplier_id: str, order: Order) -> OrderConfirmation,
    track_order(order_id: str) -> OrderStatus,
    escalate_to_human(reason: str, context: dict) -> EscalationTicket,
]
```

### Acceptance Criteria

- [ ] Llama3 is accessible via Ollama API endpoint, health-check passes on startup
- [ ] All 7 tools are registered and callable by the agent in an isolated test environment
- [ ] Agent produces a full ReAct trace (Thought → Action → Observation) for every decision
- [ ] Agent correctly identifies which tool to call given a natural-language stockout alert prompt
- [ ] A mock end-to-end run (no real orders) completes without error: stockout signal → supplier search → quote comparison → decision output
- [ ] Every agent invocation writes a structured log entry to PostgreSQL `agent_audit_log` table with: `session_id`, `tool_called`, `input_payload`, `output_payload`, `reasoning_trace`, `timestamp`
- [ ] Unit tests cover all tool input/output schemas with at least 90% coverage
- [ ] Agent gracefully handles tool timeouts (> 10s) by retrying once then escalating to human

### Definition of Done
- Code reviewed and merged to `develop`
- All acceptance criteria checked off
- Integration test passes in CI pipeline

---

## HRMP-002 — Implement `search_suppliers` Tool

| Field | Value |
|-------|-------|
| **Type** | Task |
| **Priority** | 🔴 Critical |
| **Status** | To Do |
| **Epic** | HRMP-E1 |
| **Parent** | HRMP-001 |
| **Story Points** | 5 |
| **Labels** | `tool` `supplier` `search` |

### Description
Build the `search_suppliers` tool that the Llama3 agent calls when a stockout risk is detected. It must query the internal Supplier Registry DB (populated by the scraping pipeline — see HRMP-E2) and return a filtered, ranked list of suppliers who have the requested medicine in stock, filtered by location proximity and minimum reliability score threshold.

### Input / Output Contract

```python
# Input
{
  "medicine_name": "Metformin 500mg",
  "quantity": 500,          # units
  "location": "Bangalore",
  "max_distance_km": 50,    # optional, default 50
  "min_reliability": 0.60   # optional, default 0.60
}

# Output
[
  {
    "supplier_id": "SUP-042",
    "name": "MedPlus Wholesale Bangalore",
    "reliability_score": 0.87,
    "stock_available": 1200,
    "price_per_unit": 3.50,
    "estimated_delivery_hours": 6,
    "distance_km": 12,
    "last_verified": "2026-04-07T14:30:00Z"
  },
  ...
]
```

### Acceptance Criteria

- [ ] Tool queries `supplier_registry` table and filters by medicine name (exact + fuzzy match using pg_trgm)
- [ ] Results are filtered by `min_reliability` score and `max_distance_km`
- [ ] Results are sorted by composite score: `0.5×reliability + 0.3×stock_ratio + 0.2×delivery_speed`
- [ ] Returns empty list (not error) when no suppliers match — agent handles this by escalating
- [ ] Response time < 500ms for standard queries (indexed DB)
- [ ] Medicine name lookup supports generic name aliases (e.g., "Paracetamol" matches "Acetaminophen")
- [ ] Fuzzy matching threshold is configurable via environment variable `MEDICINE_FUZZY_THRESHOLD`
- [ ] Tool is mocked in unit tests — no real DB calls in CI

---

## HRMP-003 — Implement `compare_quotes` and Order Decision Logic

| Field | Value |
|-------|-------|
| **Type** | Task |
| **Priority** | 🔴 Critical |
| **Status** | To Do |
| **Epic** | HRMP-E1 |
| **Parent** | HRMP-001 |
| **Story Points** | 5 |
| **Labels** | `tool` `decision-engine` `ordering` |

### Description
Build the `compare_quotes` tool and the downstream order decision logic that determines whether the agent should auto-order, request human approval, or escalate to procurement. This is the most safety-critical component of the agent.

### Decision Matrix

```
composite_score = (0.6 × reliability_score)
                + (0.3 × price_score)        # normalized: lowest price = 1.0
                + (0.1 × delivery_score)     # normalized: fastest = 1.0

composite_score ≥ 0.75 AND medicine is non-critical  →  AUTO ORDER
composite_score ≥ 0.75 AND medicine is critical      →  SUGGEST + Human Approval
composite_score 0.50 – 0.74                          →  SUGGEST + Human Approval
composite_score < 0.50                               →  ESCALATE to Procurement Team
No suppliers found                                   →  ESCALATE + ALERT (SMS/email)
```

### Critical Medicine Flag
Medicines tagged `is_critical = true` in the formulary (e.g., insulin, epinephrine, blood thinners, dialysis supplies) always require human approval regardless of composite score.

### Acceptance Criteria

- [ ] `compare_quotes` accepts a list of quotes and returns a ranked list with computed composite scores
- [ ] Decision engine correctly routes to AUTO ORDER / SUGGEST / ESCALATE based on the matrix above
- [ ] Critical medicine flag is respected — no auto-order ever fires for critical medicines
- [ ] `place_order` tool is only callable internally by the decision engine, not directly by the agent
- [ ] A dual-source order is automatically generated for critical medicines (top 2 suppliers)
- [ ] All ESCALATE events create a row in `escalation_log` and trigger a notification (see HRMP-024)
- [ ] Decision rationale is stored in `agent_audit_log` in human-readable format
- [ ] 100% unit test coverage for the decision matrix logic with boundary-value test cases

---

## HRMP-004 — Implement `place_order` and `track_order` Tools with Escrow Pattern

| Field | Value |
|-------|-------|
| **Type** | Task |
| **Priority** | 🔴 Critical |
| **Status** | To Do |
| **Epic** | HRMP-E1 |
| **Story Points** | 8 |
| **Labels** | `tool` `ordering` `tracking` `escrow` |

### Description
Build the order placement and tracking tools using an escrow-style confirmation pattern. An order is only considered fulfilled when physical delivery is confirmed and logged by hospital receiving staff — not when the supplier confirms dispatch.

### Order Lifecycle

```
DRAFT → APPROVED → PLACED → DISPATCHED → DELIVERED → VERIFIED → CLOSED
                                                              ↓ (if rejected)
                                                           DISPUTE
```

### Acceptance Criteria

- [ ] `place_order` creates an order record in `orders` table with status `PLACED` and returns `order_id`
- [ ] Order is never marked `DELIVERED` automatically — requires manual confirmation via receiving UI or API endpoint `POST /orders/{id}/confirm-delivery`
- [ ] `track_order` polls supplier status endpoint (or scrapes order confirmation page) and updates `orders` table
- [ ] Supplier lead time SLA is stored at order creation; a background Celery task monitors SLA breach
- [ ] SLA breach (delivery not confirmed within promised window + 2h buffer) triggers reliability score downgrade and alert
- [ ] `place_order` is idempotent — duplicate calls with same `order_id` return existing order, do not create duplicate
- [ ] All order state transitions are recorded in `order_events` audit table with timestamp and actor
- [ ] Integration test simulates full lifecycle: PLACED → DELIVERED → VERIFIED

---

## HRMP-005 — Implement `escalate_to_human` Tool and Escalation Workflow

| Field | Value |
|-------|-------|
| **Type** | Task |
| **Priority** | 🟠 High |
| **Status** | To Do |
| **Epic** | HRMP-E1 |
| **Story Points** | 3 |
| **Labels** | `tool` `escalation` `notifications` |

### Description
When the agent cannot confidently make a procurement decision, it must hand off to the hospital procurement team with a structured escalation packet — not just a generic alert. The escalation must include enough context for the human to act without needing to re-investigate.

### Escalation Payload

```json
{
  "escalation_id": "ESC-2026-00142",
  "triggered_by": "agent_session_id",
  "reason": "No supplier scored above 0.50 composite for Insulin Glargine 100U/mL",
  "medicine": "Insulin Glargine 100U/mL",
  "quantity_needed": 200,
  "stockout_risk": 0.91,
  "days_until_stockout": 2,
  "suppliers_evaluated": [...],
  "recommended_action": "Contact MedPlus Wholesale directly via phone — last manual order fulfilled in 4h",
  "timestamp": "2026-04-08T09:15:00Z",
  "priority": "CRITICAL"
}
```

### Acceptance Criteria

- [ ] Escalation creates a record in `escalations` table and triggers notifications via Twilio SMS + email
- [ ] Escalation payload includes all fields shown above — incomplete payloads are rejected
- [ ] Procurement dashboard shows all open escalations sorted by `days_until_stockout` ascending
- [ ] Escalation can be resolved or dismissed by procurement staff with a required resolution note
- [ ] Resolved escalations feed back into agent training data pipeline (future improvement flag)
- [ ] P1 escalations (days_until_stockout ≤ 1) trigger an additional on-call page via PagerDuty integration

---

## HRMP-006 — Agent System Prompt Engineering and Safety Rails

| Field | Value |
|-------|-------|
| **Type** | Task |
| **Priority** | 🟠 High |
| **Status** | To Do |
| **Epic** | HRMP-E1 |
| **Story Points** | 5 |
| **Labels** | `prompt-engineering` `safety` `llm` |

### Description
Design and validate the Llama3 system prompt that governs agent behavior. Healthcare AI agents require explicit safety rails to prevent hallucination-driven orders, unauthorized spending, or bypassing human oversight for critical medicines.

### System Prompt Requirements

```
The agent must:
1. NEVER place an order without calling check_supplier_reliability first
2. NEVER place an order for a critical medicine without human approval
3. ALWAYS call compare_quotes before place_order
4. ALWAYS call escalate_to_human if confidence is below threshold
5. NEVER invent supplier names, prices, or stock levels — only use tool outputs
6. ALWAYS state its reasoning before taking action
7. NEVER exceed the per-order budget cap stored in hospital_config.max_order_budget_inr
```

### Acceptance Criteria

- [ ] System prompt passes a red-team evaluation: 20 adversarial prompts cannot cause the agent to bypass safety rails
- [ ] Agent refuses to place orders when tool data is missing or stale (> 4 hours old)
- [ ] Agent correctly identifies ambiguous medicine names and asks for clarification rather than guessing
- [ ] Budget cap enforcement: agent calls escalate_to_human when order total exceeds `max_order_budget_inr`
- [ ] Hallucination guard: if agent output contains a supplier name not in tool results, response is rejected by a validation layer and re-prompted
- [ ] Prompt version is stored in `agent_config` table — changing the prompt auto-increments version and invalidates cached decisions

---

---

# 🕸️ EPIC HRMP-E2 — Supplier Scraping & Intelligence Pipeline

---

## HRMP-007 — Supplier Discovery and Registry Schema

| Field | Value |
|-------|-------|
| **Type** | Story |
| **Priority** | 🔴 Critical |
| **Status** | To Do |
| **Epic** | HRMP-E2 |
| **Story Points** | 3 |
| **Labels** | `database` `schema` `supplier` |

### Description
Design and migrate the `supplier_registry` database schema that all scraping, reliability scoring, and agent tools depend on. This is a foundational blocker for all other HRMP-E2 tickets.

### Schema (PostgreSQL + TimescaleDB)

```sql
-- Core supplier table
CREATE TABLE suppliers (
  supplier_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name              VARCHAR(255) NOT NULL,
  type              ENUM('wholesale', 'retail', 'manufacturer', 'government'),
  city              VARCHAR(100),
  state             VARCHAR(100),
  lat               DECIMAL(9,6),
  lng               DECIMAL(9,6),
  phone             VARCHAR(20),
  whatsapp          VARCHAR(20),
  website           VARCHAR(500),
  reliability_score DECIMAL(4,3) DEFAULT 0.500,
  is_verified       BOOLEAN DEFAULT false,
  last_scraped_at   TIMESTAMPTZ,
  created_at        TIMESTAMPTZ DEFAULT NOW()
);

-- Medicine catalog per supplier
CREATE TABLE supplier_inventory (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  supplier_id     UUID REFERENCES suppliers(supplier_id),
  medicine_name   VARCHAR(255),
  generic_name    VARCHAR(255),
  brand_name      VARCHAR(255),
  strength        VARCHAR(50),
  form            VARCHAR(50),   -- tablet, injection, syrup
  stock_units     INTEGER,
  price_per_unit  DECIMAL(10,2),
  currency        VARCHAR(3) DEFAULT 'INR',
  scraped_at      TIMESTAMPTZ DEFAULT NOW(),
  is_available    BOOLEAN DEFAULT true
);
```

### Acceptance Criteria

- [ ] Migration runs cleanly on a fresh PostgreSQL 16 + TimescaleDB 2.x instance
- [ ] All foreign keys, indexes, and enum types are created correctly
- [ ] `supplier_inventory` is a TimescaleDB hypertable partitioned by `scraped_at` for time-series querying
- [ ] Fuzzy search index (`pg_trgm`) is created on `medicine_name` and `generic_name`
- [ ] Seed script populates 10 mock suppliers and 50 inventory records for development
- [ ] ERD diagram is generated and committed to `/docs/db/supplier_erd.png`

---

## HRMP-008 — Playwright Scraper for MedPlus / PharmEasy B2B

| Field | Value |
|-------|-------|
| **Type** | Story |
| **Priority** | 🔴 Critical |
| **Status** | To Do |
| **Epic** | HRMP-E2 |
| **Story Points** | 8 |
| **Labels** | `scraping` `playwright` `supplier-data` |

### Description
Build a robust Playwright-based scraper targeting MedPlus Wholesale and PharmEasy B2B portals (or their public-facing catalog pages) to extract medicine names, stock availability, pricing, and delivery estimates. The scraper must be resilient to layout changes and respectful of rate limits.

### Scraper Architecture

```
ScraperOrchestrator (Celery Beat — runs every 4h)
├── MedPlusScraper      → /mnt/scrapers/medplus.py
├── PharmEasyScraper    → /mnt/scrapers/pharmeasy.py
└── GenericCatalogScraper (for local distributors with basic HTML pages)
```

### Acceptance Criteria

- [ ] Scraper launches headless Chromium via Playwright and navigates target pages without triggering bot detection
- [ ] Rotating user-agent pool (min. 20 agents) is implemented and cycled per session
- [ ] Scraper respects `robots.txt` — a utility checks and logs disallowed paths before scraping
- [ ] On HTTP 429 / rate-limit response: backs off with exponential delay (5s → 10s → 20s → skip + alert)
- [ ] Extracted data is validated against `SupplierInventorySchema` (Pydantic) before DB upsert
- [ ] Each scrape session stores raw HTML in S3/MinIO with TTL 7 days for audit/debugging
- [ ] Scraper run is logged to `scraper_runs` table: `{scraper_name, start_time, end_time, records_scraped, errors}`
- [ ] Scraper failure (> 3 consecutive errors) sends an alert and pauses the Celery task
- [ ] Data freshness: `supplier_inventory.scraped_at` must be ≤ 4 hours old for the agent to use it

---

## HRMP-009 — WhatsApp Business API Integration for Local Suppliers

| Field | Value |
|-------|-------|
| **Type** | Story |
| **Priority** | 🟠 High |
| **Status** | To Do |
| **Epic** | HRMP-E2 |
| **Story Points** | 8 |
| **Labels** | `whatsapp` `local-suppliers` `integration` |

### Description
Many local medicine distributors in Bangalore and surrounding areas (Kanakapura Road, Jayanagar, Rajajinagar medical districts) primarily operate via WhatsApp catalogs. Build a WhatsApp Business API integration to: (a) request stock and pricing from suppliers via templated messages, and (b) parse their responses to update the supplier registry.

### Flow

```
Celery Task (every 6h)
    → Send "Catalog Request" template message to each local supplier
    → Supplier replies with price list (text or PDF)
    → Webhook receives reply
    → Parser extracts medicine, price, quantity (LLM-assisted for unstructured replies)
    → Upsert into supplier_inventory
```

### Acceptance Criteria

- [ ] WhatsApp Business API is configured with approved message templates for stock inquiries
- [ ] Outbound template message includes: hospital name, list of required medicines, requested format
- [ ] Webhook endpoint `POST /webhooks/whatsapp` correctly receives and verifies Meta signature
- [ ] Unstructured text replies are parsed using a lightweight Llama3 extraction prompt → structured JSON
- [ ] PDF price list attachments are downloaded and parsed using `pdfplumber`
- [ ] Parsing confidence score < 0.7 flags the record for manual review in the supplier dashboard
- [ ] Supplier opt-out is respected — `is_whatsapp_opted_out` flag prevents further outbound messages
- [ ] All message logs are stored for 90 days for compliance

---

## HRMP-010 — Government & Jan Aushadhi (PMBJP) Catalog Integration

| Field | Value |
|-------|-------|
| **Type** | Task |
| **Priority** | 🟡 Medium |
| **Status** | To Do |
| **Epic** | HRMP-E2 |
| **Story Points** | 3 |
| **Labels** | `government` `jan-aushadhi` `pricing` |

### Description
Integrate the Jan Aushadhi (PMBJP) public pricing catalog as a benchmark price reference. Prices from PMBJP outlets serve as the floor price for negotiations with private suppliers. The integration should run as a scheduled scrape of the official portal.

### Acceptance Criteria

- [ ] Scraper fetches the PMBJP medicine price list (CSV/Excel published on janaushadhi.gov.in)
- [ ] Data is stored in a separate `reference_pricing` table linked to `supplier_inventory` via generic name
- [ ] Agent `compare_quotes` tool includes a `vs_jan_aushadhi_price` field showing % difference from government price
- [ ] Dashboard shows medicines where hospital is paying > 20% above Jan Aushadhi price (red flag)
- [ ] Catalog refresh runs weekly (government updates monthly)

---

## HRMP-011 — Supplier Data Quality and Deduplication Pipeline

| Field | Value |
|-------|-------|
| **Type** | Task |
| **Priority** | 🟠 High |
| **Status** | To Do |
| **Epic** | HRMP-E2 |
| **Story Points** | 5 |
| **Labels** | `data-quality` `deduplication` `pipeline` |

### Description
Multiple scrapers will surface the same supplier and medicine under different names. Build a deduplication and normalization pipeline to ensure the supplier registry is clean and consistent before the agent queries it.

### Acceptance Criteria

- [ ] Supplier deduplication uses fuzzy name matching + geolocation (same name within 500m = same supplier)
- [ ] Medicine name normalization maps brand names to WHO INN generic names using an embedded lookup table
- [ ] Strength normalization: "500 mg", "500mg", "0.5g" → canonical form "500mg"
- [ ] Duplicate supplier records are merged with a `merged_into` FK, not deleted, for audit trail
- [ ] Pipeline runs after every scrape session via Celery chain
- [ ] Data quality report (duplicate rate, normalization coverage %) is generated daily and stored in `data_quality_reports`

---

---

# ⭐ EPIC HRMP-E3 — Reliability Scoring Engine

---

## HRMP-012 — Reliability Score Calculation Service

| Field | Value |
|-------|-------|
| **Type** | Story |
| **Priority** | 🔴 Critical |
| **Status** | To Do |
| **Epic** | HRMP-E3 |
| **Story Points** | 8 |
| **Labels** | `reliability` `scoring` `ml` |

### Description
Build the reliability scoring engine that computes a 0–1 composite score for each supplier based on their historical performance. Scores are recalculated after every order event and on a nightly batch run.

### Scoring Formula

```
reliability_score = (
    0.35 × on_time_delivery_rate
  + 0.25 × order_fulfillment_rate
  + 0.15 × price_consistency_score
  + 0.15 × response_time_score
  + 0.10 × (1 - quality_complaint_rate)
)

where:
  on_time_delivery_rate    = orders_on_time / total_orders (rolling 90 days)
  order_fulfillment_rate   = items_fulfilled / items_ordered (rolling 90 days)
  price_consistency_score  = 1 - (std_dev(prices) / mean(prices))   # lower variance = higher score
  response_time_score      = 1 - min(response_hours / 24, 1.0)      # normalized to 24h window
  quality_complaint_rate   = complaints / total_orders (rolling 90 days)
```

### Score Tiers

| Score | Tier | Agent Behavior |
|-------|------|---------------|
| 0.80 – 1.00 | ⭐ Platinum | Auto-order eligible |
| 0.75 – 0.79 | 🟢 Gold | Auto-order eligible (non-critical) |
| 0.50 – 0.74 | 🟡 Silver | Suggest + Human Approval |
| 0.25 – 0.49 | 🟠 Bronze | Human Approval + flagged |
| 0.00 – 0.24 | 🔴 Suspended | Blocked from ordering |

### Acceptance Criteria

- [ ] Scoring function is implemented as a pure Python function with no side effects (easily testable)
- [ ] Score is recalculated and persisted to `suppliers.reliability_score` after every order status change
- [ ] Nightly batch recalculates all scores using a rolling 90-day window
- [ ] Score history is stored in `supplier_score_history` (TimescaleDB) for trend visualization
- [ ] Unit tests cover all formula components with known input/output pairs
- [ ] Score cannot be manually overridden without a `score_override_reason` and manager approval logged
- [ ] New suppliers (< 3 orders) receive a provisional score of 0.50 with a `is_provisional` flag

---

## HRMP-013 — Automatic SLA Monitoring and Score Downgrade

| Field | Value |
|-------|-------|
| **Type** | Task |
| **Priority** | 🟠 High |
| **Status** | To Do |
| **Epic** | HRMP-E3 |
| **Story Points** | 5 |
| **Labels** | `sla` `monitoring` `celery` |

### Description
Background Celery tasks must monitor active orders against their SLA commitment and automatically trigger score adjustments when a supplier fails to deliver within the agreed window.

### Acceptance Criteria

- [ ] Celery Beat task runs every 30 minutes to check all orders with status `PLACED` or `DISPATCHED`
- [ ] Orders past SLA window + 2h buffer are marked `SLA_BREACH` in `order_events`
- [ ] SLA breach triggers an immediate `-0.05` penalty applied to the supplier's rolling score
- [ ] Three consecutive SLA breaches within 30 days automatically suspend the supplier (`score < 0.25`)
- [ ] Suspension triggers a notification to procurement team and removes supplier from active agent queries
- [ ] Supplier can appeal suspension through a manual reinstatement flow (requires manager approval)

---

## HRMP-014 — Supplier Reliability Dashboard

| Field | Value |
|-------|-------|
| **Type** | Story |
| **Priority** | 🟡 Medium |
| **Status** | To Do |
| **Epic** | HRMP-E3 |
| **Story Points** | 5 |
| **Labels** | `dashboard` `frontend` `analytics` |

### Description
Build a procurement dashboard view showing supplier reliability trends, score breakdowns, and comparative performance metrics to help procurement staff make informed decisions on supplier relationships.

### Acceptance Criteria

- [ ] Dashboard shows all suppliers with current score, tier badge, and 90-day score trend sparkline
- [ ] Drill-down view per supplier shows: score component breakdown, order history, complaints, SLA breach history
- [ ] Filter by: city, medicine category, tier, verification status
- [ ] Export supplier performance report as CSV or PDF (monthly)
- [ ] Score trend chart shows data for last 6 months
- [ ] Dashboard loads in < 2 seconds for up to 500 suppliers

---

---

# 📈 EPIC HRMP-E4 — Inventory Forecasting Engine

---

## HRMP-015 — Time-Series Demand Forecasting (Prophet / XGBoost)

| Field | Value |
|-------|-------|
| **Type** | Story |
| **Priority** | 🔴 Critical |
| **Status** | To Do |
| **Epic** | HRMP-E4 |
| **Story Points** | 13 |
| **Labels** | `forecasting` `ml` `prophet` `xgboost` |

### Description
Build the core demand forecasting pipeline that predicts daily medicine consumption for the next 14 and 30 days. Forecasts feed into stockout risk calculations and auto-ordering triggers.

### Model Selection Strategy
- **Facebook Prophet** for medicines with clear seasonal patterns (antipyretics, ORS, antihistamines)
- **XGBoost** for medicines with feature-rich consumption patterns (tied to patient admission rates, diagnosis codes)
- **Ensemble** for high-value / high-risk medicines: weighted average of both

### Feature Set

```
Time features:   day_of_week, month, is_monsoon_season, is_festival_period,
                 days_since_last_stockout
Patient features: daily_admissions, icu_occupancy, ot_scheduled_cases,
                  active_diagnosis_cohort_counts (diabetes, cardiac, respiratory)
Supply features:  current_stock, days_of_supply, pending_order_quantity
External:         local_disease_outbreak_flag (from IDSP Karnataka API)
```

### Acceptance Criteria

- [ ] Pipeline trains models per medicine SKU with at least 180 days of historical consumption data
- [ ] Forecast output includes: `predicted_demand`, `lower_bound_80`, `upper_bound_80` for each day
- [ ] Model selection (Prophet vs XGBoost vs Ensemble) is logged per SKU with selection rationale
- [ ] Forecast is regenerated nightly for all SKUs via Airflow DAG
- [ ] Back-test on last 30 days shows MAPE (Mean Absolute Percentage Error) < 15% for top 100 medicines
- [ ] Seasonal adjustment for known Karnataka disease patterns: dengue (Jun–Sep), flu (Jan–Mar)
- [ ] Forecast API endpoint: `GET /forecast/{medicine_id}?horizon=14` returns JSON with confidence intervals
- [ ] Cold-start handling: new medicines (< 30 days history) use category average consumption rates

---

## HRMP-016 — Stockout Risk Score Calculation

| Field | Value |
|-------|-------|
| **Type** | Story |
| **Priority** | 🔴 Critical |
| **Status** | To Do |
| **Epic** | HRMP-E4 |
| **Story Points** | 5 |
| **Labels** | `stockout` `risk` `forecasting` |

### Description
Combine current inventory levels with demand forecasts to produce a daily stockout risk score (0–100%) for each medicine, and calculate the estimated days until stockout.

### Formula

```
days_of_supply = current_stock / avg_daily_demand_forecast

stockout_risk =
  if days_of_supply > reorder_point_days:  LOW    (0–30%)
  if days_of_supply > safety_stock_days:   MEDIUM (30–70%)
  if days_of_supply ≤ safety_stock_days:  HIGH   (70–100%)

reorder_point_days = avg_lead_time_days × 1.5
safety_stock_days  = avg_lead_time_days × demand_variability_factor
```

### Acceptance Criteria

- [ ] Stockout risk score is calculated for all medicines every 6 hours
- [ ] Risk scores are stored in `inventory_risk_scores` (TimescaleDB hypertable)
- [ ] HIGH risk (> 70%) automatically triggers the supply chain agent (HRMP-001)
- [ ] Medicines with `is_critical = true` trigger agent at MEDIUM risk (> 30%)
- [ ] Inventory dashboard shows risk scores with color coding: green / amber / red
- [ ] Days-until-stockout counter is shown per medicine
- [ ] Risk history chart shows last 30 days to identify chronic shortage medicines

---

## HRMP-017 — Expiry Waste Prediction and Redistribution Alerts

| Field | Value |
|-------|-------|
| **Type** | Story |
| **Priority** | 🟠 High |
| **Status** | To Do |
| **Epic** | HRMP-E4 |
| **Story Points** | 8 |
| **Labels** | `expiry` `waste-reduction` `alerts` |

### Description
Predict which medicines are at risk of expiring before consumption based on current stock, demand forecast, and expiry dates. Generate redistribution recommendations across wards or flag for return to supplier.

### Acceptance Criteria

- [ ] System ingests batch/lot expiry dates from inventory records
- [ ] For each batch: calculates `projected_remaining_stock_at_expiry = current_stock - cumulative_forecast_demand_until_expiry`
- [ ] Batches with `projected_remaining_stock_at_expiry > 0` are flagged as "Expiry Risk"
- [ ] Alert is generated 45 days before expiry for high-risk batches and 14 days for all others
- [ ] Alert includes: quantity at risk, estimated waste value in INR, suggested action (use first / redistribute / return)
- [ ] Redistribution suggestions identify wards with higher consumption of the same medicine
- [ ] Monthly expiry waste report shows: total units wasted, total value, % of inventory, trend vs prior month
- [ ] Unit test: known future expiry with flat demand → system correctly flags waste risk

---

## HRMP-018 — Seasonal Disease Surge Prediction (Karnataka-specific)

| Field | Value |
|-------|-------|
| **Type** | Story |
| **Priority** | 🟠 High |
| **Status** | To Do |
| **Epic** | HRMP-E4 |
| **Story Points** | 8 |
| **Labels** | `seasonal` `disease-surge` `forecasting` `karnataka` |

### Description
Build a Karnataka-specific seasonal surge predictor that boosts demand forecasts for relevant medicines during known endemic disease seasons, and integrates real-time signals from the IDSP (Integrated Disease Surveillance Programme) Karnataka portal.

### Disease → Medicine Mapping (Seed Data)

```
Dengue (Jun–Sep)          → Paracetamol, IV fluids, Platelet transfusion supplies, NS 0.9%
Influenza (Jan–Mar)        → Oseltamivir, Azithromycin, Paracetamol
Malaria (Monsoon)         → Chloroquine, Artemether-Lumefantrine, Primaquine
Gastroenteritis (Year-round)→ ORS, Metronidazole, Ondansetron
Respiratory (Winter)      → Salbutamol nebules, Ipratropium, Prednisolone
```

### Acceptance Criteria

- [ ] Calendar-based seasonal multipliers are configurable per disease per month (JSON config file)
- [ ] IDSP Karnataka API (or web scrape) is polled weekly for active outbreak alerts in Bangalore/Kanakapura region
- [ ] Active outbreak flag boosts demand forecast for linked medicines by a configurable `outbreak_multiplier` (default 1.5×)
- [ ] Surge alerts are shown on inventory dashboard with disease context
- [ ] Back-test against 2023–2024 historical data shows surge predictions are triggered within 7 days of actual demand spikes
- [ ] Surge multipliers are reviewed and editable by the hospital pharmacist (with audit log)

---

## HRMP-019 — Surgery Schedule-Driven Supply Forecasting

| Field | Value |
|-------|-------|
| **Type** | Story |
| **Priority** | 🟡 Medium |
| **Status** | To Do |
| **Epic** | HRMP-E4 |
| **Story Points** | 8 |
| **Labels** | `surgical` `forecasting` `integration` |

### Description
Integrate with the hospital's OT (Operation Theatre) scheduling system to anticipate surgical supply needs 48–72 hours in advance, ensuring that procedure-specific consumables and medicines are pre-ordered before the surgery.

### Acceptance Criteria

- [ ] Integration reads confirmed OT schedule via HL7 FHIR API or direct DB query (configurable)
- [ ] Each surgery type maps to a `surgical_supply_kit` containing required medicines and consumables with standard quantities
- [ ] System generates a `pre-surgery supply check` 72h before each scheduled procedure
- [ ] Supply check flags any kit item below required quantity and triggers an order recommendation
- [ ] Emergency (unscheduled) surgeries trigger an immediate supply check and expedited order
- [ ] Surgical supply kit templates are editable by the head of anaesthesia with approval workflow
- [ ] Test: schedule a "Cardiac Bypass" surgery → system correctly flags all 12 kit items and checks stock

---

## HRMP-020 — Budget Burn Rate and Supplier Price Trend Forecasting

| Field | Value |
|-------|-------|
| **Type** | Story |
| **Priority** | 🟡 Medium |
| **Status** | To Do |
| **Epic** | HRMP-E4 |
| **Story Points** | 5 |
| **Labels** | `financial` `forecasting` `pricing` |

### Description
Track monthly procurement spend against budget, forecast end-of-month burn rate, and predict supplier price trends to recommend optimal purchase windows.

### Acceptance Criteria

- [ ] Monthly procurement budget is configurable per medicine category in `budget_config`
- [ ] Daily spend is tracked against category budgets with burn rate % shown on dashboard
- [ ] End-of-month spend forecast uses linear regression on current month's daily spend trajectory
- [ ] Budget overrun alert fires at 80% and 95% utilization
- [ ] Supplier price tracking stores `price_per_unit` at each scrape → time-series in TimescaleDB
- [ ] Price trend chart shows last 6 months per medicine with trend line
- [ ] "Buy window" recommendation: if price is ≥ 10% below 90-day average → flag as optimal purchase time
- [ ] Monthly financial report: total spend, by-category breakdown, top 10 most expensive medicines, savings vs Jan Aushadhi benchmark

---

---

# 🩸 EPIC HRMP-E5 — Blood Bank & Clinical Forecasting

---

## HRMP-021 — Blood Bank Demand Forecasting

| Field | Value |
|-------|-------|
| **Type** | Story |
| **Priority** | 🟠 High |
| **Status** | To Do |
| **Epic** | HRMP-E5 |
| **Story Points** | 8 |
| **Labels** | `blood-bank` `forecasting` |

### Description
Forecast blood product demand (by blood group and product type: whole blood, packed RBC, FFP, platelets, cryoprecipitate) by correlating surgical schedules, trauma admission trends, and historical transfusion data.

### Acceptance Criteria

- [ ] Forecasting model trained on: historical transfusion records, surgical schedule, trauma admission rate, day of week
- [ ] Forecast horizon: 7 days per blood product per blood group (8 blood groups × 5 product types = 40 forecasts)
- [ ] Forecast updates when a new surgery is scheduled or when trauma admission rate spikes > 2× baseline
- [ ] Blood bank dashboard shows current stock, forecasted demand, and days of supply per product/group
- [ ] Alert fires when any blood group/product combination drops below 3 days of forecasted supply
- [ ] Low supply alert triggers outreach recommendation to nearest blood bank (list maintained in config)
- [ ] Forecast accuracy back-tested on last 60 days; MAPE < 20% acceptable for blood products

---

## HRMP-022 — Discharge Medication Prediction

| Field | Value |
|-------|-------|
| **Type** | Story |
| **Priority** | 🟡 Medium |
| **Status** | To Do |
| **Epic** | HRMP-E5 |
| **Story Points** | 8 |
| **Labels** | `discharge` `clinical` `prediction` |

### Description
Predict discharge medications for admitted patients based on their diagnosis, length of stay, and clinical pathway, allowing the pharmacy to pre-pack prescriptions and forecast outpatient demand.

### Acceptance Criteria

- [ ] Model trained on historical admission → discharge prescription pairs (requires 12+ months of data)
- [ ] For each admitted patient: predict top-5 most likely discharge medicines with confidence scores
- [ ] Predictions are shown to ward pharmacist 24h before expected discharge date
- [ ] Pharmacist can confirm, modify, or reject predictions (feedback feeds back into model retraining)
- [ ] Aggregate discharge predictions feed into next-day pharmacy demand forecast
- [ ] Model is retrained monthly on new admission/discharge data
- [ ] Privacy: predictions are per patient but stored without PII linkage in the training dataset

---

## HRMP-023 — Chronic Disease Cohort Tracking and Supply Planning

| Field | Value |
|-------|-------|
| **Type** | Story |
| **Priority** | 🟡 Medium |
| **Status** | To Do |
| **Epic** | HRMP-E5 |
| **Story Points** | 5 |
| **Labels** | `chronic-disease` `cohort` `supply-planning` |

### Description
Track the active cohort of admitted patients with chronic conditions (diabetes, CKD, cardiac, respiratory) and use cohort size to forecast steady-state consumption of condition-specific medicines and consumables (dialysis supplies, insulin, etc.).

### Acceptance Criteria

- [ ] System reads admitted patient diagnosis list from HIS (Hospital Information System) daily
- [ ] Patients are grouped into chronic condition cohorts; cohort size is tracked over time
- [ ] For each cohort: daily medicine consumption baseline is defined in `cohort_supply_profiles` (editable by clinical pharmacist)
- [ ] Cohort-based demand is added to the base demand forecast as a component
- [ ] Dashboard shows cohort size trends with consumption impact on top-10 cohort medicines
- [ ] Alert fires if cohort size increases > 20% week-over-week (surge preparation trigger)

---

---

# 🔔 EPIC HRMP-E6 — Alerting, Observability & Compliance

---

## HRMP-024 — Multi-Channel Alert and Notification System

| Field | Value |
|-------|-------|
| **Type** | Story |
| **Priority** | 🟠 High |
| **Status** | To Do |
| **Epic** | HRMP-E6 |
| **Story Points** | 5 |
| **Labels** | `alerts` `notifications` `twilio` `firebase` |

### Description
Build a unified notification service that routes different alert types to the appropriate channels and stakeholders based on severity and role.

### Alert Routing Matrix

| Alert Type | Severity | Channels | Recipients |
|------------|----------|----------|------------|
| Stockout Risk HIGH | P1 | SMS + In-app + Email | Procurement Head, CMO |
| Stockout Risk MEDIUM | P2 | In-app + Email | Procurement Officer |
| SLA Breach | P2 | SMS + In-app | Procurement Officer |
| Expiry Risk (45 days) | P3 | In-app + Email | Pharmacist |
| Budget 80% utilized | P3 | Email | Finance, Procurement Head |
| Agent Escalation (Critical) | P1 | SMS + PagerDuty | Procurement Head, On-call |
| Supplier Suspended | P2 | Email + In-app | Procurement Team |

### Acceptance Criteria

- [ ] Notification service is a standalone microservice with `POST /notify` API
- [ ] SMS delivery via Twilio with delivery receipt tracking
- [ ] In-app notifications via Firebase Cloud Messaging (FCM)
- [ ] Email via SendGrid with HTML templates per alert type
- [ ] P1 alerts that are not acknowledged within 15 minutes are re-escalated via PagerDuty
- [ ] Users can configure notification preferences (which channels, which alert types) in their profile
- [ ] All notifications are stored in `notification_log` with delivery status and acknowledgement timestamp
- [ ] Notification deduplication: same alert for same medicine within 2 hours is suppressed (one message only)

---

## HRMP-025 — Agent Decision Audit Log and Compliance Dashboard

| Field | Value |
|-------|-------|
| **Type** | Story |
| **Priority** | 🟠 High |
| **Status** | To Do |
| **Epic** | HRMP-E6 |
| **Story Points** | 5 |
| **Labels** | `audit` `compliance` `dashboard` |

### Description
All AI agent decisions must be fully explainable and auditable for hospital compliance and accreditation purposes (NABH / JCI requirements). Build a compliance dashboard and audit log viewer for procurement auditors.

### Acceptance Criteria

- [ ] `agent_audit_log` table stores every agent session with full ReAct trace, tools called, inputs, outputs, and final decision
- [ ] Audit log is append-only — no UPDATE or DELETE permissions granted to application user
- [ ] Compliance dashboard shows: all agent decisions in the last 30/90 days, filter by decision type (auto-order / suggest / escalate), filter by medicine
- [ ] Each log entry has an "Explain this decision" view showing the full reasoning chain in plain English
- [ ] Auditor can export full audit log for a date range as CSV or PDF
- [ ] Audit log is replicated to a separate read-only database to prevent data loss
- [ ] Retention: audit logs are retained for 7 years (healthcare compliance requirement)

---

## HRMP-026 — System Health Monitoring and Observability Stack

| Field | Value |
|-------|-------|
| **Type** | Task |
| **Priority** | 🟡 Medium |
| **Status** | To Do |
| **Epic** | HRMP-E6 |
| **Story Points** | 5 |
| **Labels** | `devops` `monitoring` `observability` |

### Description
Set up end-to-end observability for all platform services including the Llama3 agent, scraping pipeline, forecasting jobs, and order management service.

### Acceptance Criteria

- [ ] **Metrics**: Prometheus exporters on all services; Grafana dashboards for: agent invocations/min, scraper success rate, forecast job duration, order volume
- [ ] **Logs**: Structured JSON logging (loguru) → Loki → Grafana
- [ ] **Traces**: OpenTelemetry on agent tool calls → Jaeger for distributed tracing
- [ ] **Alerts**: PagerDuty integration for: Ollama model down, scraper failure > 3 consecutive runs, forecast job failed, DB connection pool exhausted
- [ ] **Uptime**: Healthcheck endpoints on all services; UptimeRobot monitors with 5-min intervals
- [ ] Grafana dashboard covers: system overview, agent performance, supplier pipeline health, inventory risk summary
- [ ] Runbook documented for each PagerDuty alert in `/docs/runbooks/`

---

---

## 📊 Sprint Summary

| Priority | Count | Story Points |
|----------|-------|-------------|
| 🔴 Critical | 10 | 74 |
| 🟠 High | 10 | 57 |
| 🟡 Medium | 6 | 31 |
| **Total** | **26 tickets** | **162 points** |

---

## 🏗️ Recommended Sprint Breakdown

**Sprint 1 (Weeks 1–2): Foundation**
HRMP-007, HRMP-001, HRMP-006, HRMP-012, HRMP-016

**Sprint 2 (Weeks 3–4): Scraping + Agent Tools**
HRMP-008, HRMP-009, HRMP-002, HRMP-003, HRMP-011

**Sprint 3 (Weeks 5–6): Forecasting + Ordering**
HRMP-015, HRMP-018, HRMP-004, HRMP-005, HRMP-013

**Sprint 4 (Weeks 7–8): Clinical + Compliance**
HRMP-017, HRMP-019, HRMP-021, HRMP-024, HRMP-025, HRMP-026

**Sprint 5 (Weeks 9–10): Advanced Features + Polish**
HRMP-010, HRMP-014, HRMP-020, HRMP-022, HRMP-023
