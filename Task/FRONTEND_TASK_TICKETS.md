# AHIMP Frontend Task Tickets

This file tracks frontend work derived from completed implementation tickets in `IMPLEMENTATION_TICKETS.md`.

## FE-TICKET: FE-501
**Title:** Agent Operations Dashboard Integration
**Source Tickets:** TASK-401, TASK-402, TASK-501
**Status:** Completed
**Priority:** HIGH

**Implemented Frontend Changes:**
- Added route: `/agents`
- Added dashboard components:
  - `components/agents/AgentDashboard.tsx`
  - `components/agents/DataIngestionStatus.tsx`
  - `components/agents/AtRiskItems.tsx`
  - `components/agents/SupplierRecommendations.tsx`
  - `components/agents/POTracker.tsx`
  - `components/agents/AgentLogs.tsx`
- Added typed API integrations for:
  - dashboard summary
  - logs query/export
  - ingestion trigger/status
  - supply-chain at-risk/optimize

**Frontend Acceptance:**
- Polling-based near real-time updates
- Manual trigger support
- Search/filter/pagination support
- Drill-down JSON detail views

---

## FE-TICKET: FE-502
**Title:** Manual Approval Queue UI
**Source Ticket:** TASK-502
**Status:** Completed
**Priority:** HIGH

**Implemented Frontend Changes:**
- Added route: `/approval-queue`
- Added page component: `components/approvals/ApprovalQueuePage.tsx`
- Added navigation item for approval queue in sidebar
- Added typed API integrations for:
  - queue listing
  - queue detail
  - approve/reject decision action
  - timeout auto-processing trigger

**Frontend Acceptance:**
- Queue table with filter/search/pagination
- Approval details with score breakdown
- Approve/Reject + comments
- Audit trail timeline

---

## FE-TICKET: FE-503
**Title:** Hardcoded Frontend Cleanup (Post-Implementation)
**Source Tickets:** TASK-501, TASK-502
**Status:** Completed
**Priority:** MEDIUM

**Cleanup Done:**
- Removed hardcoded backend API host:
  - `lib/ml-api.ts` now supports `NEXT_PUBLIC_API_BASE_URL` with localhost fallback.
- Removed hardcoded approval reviewer values:
  - `components/approvals/ApprovalQueuePage.tsx` now derives reviewer identity and role from active user context.
- Removed fixed agent filter values that could drift from backend reality:
  - `components/agents/AgentLogs.tsx` now builds agent/status/level filter options dynamically from returned records.

**Purpose:**
- Reduce brittle assumptions.
- Keep frontend aligned with backend runtime outputs and current signed-in user context.

---

## FE-TICKET: FE-504
**Title:** Frontend Follow-up Sync Backlog
**Source Tickets:** TASK-107, TASK-105, TASK-106
**Status:** Completed
**Priority:** MEDIUM

**Implemented Frontend Changes:**
- Added route: `/model-insights`
- Added explainability workflow UI for:
  - `/api/explain/item/{item_id}`
  - `/api/explain/prediction/{prediction_id}`
- Added model comparison visuals for:
  - `/api/model-comparison`
- Added optimization and benchmark dashboard widgets sourced from:
  - `backend/models/best_params.json`
  - `backend/benchmark_results.json` (if present)
  - `backend/benchmark_results_catboost.json`
- Added frontend artifact proxy endpoint:
  - `/api/model-artifacts`
- Added sidebar navigation entry:
  - `Model Insights`

**Frontend Acceptance:**
- Item-level and prediction-level explanation runs from UI controls
- SHAP/LIME contribution visualizations
- Side-by-side model metrics comparison table + feature-importance chart
- Benchmark KPI cards with acceptance-criteria badges
- Hyperparameter best-parameter drilldown per model
