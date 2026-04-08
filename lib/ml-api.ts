/**
 * Typed API client for the FastAPI ML backend.
 * Configure host via NEXT_PUBLIC_API_BASE_URL, fallback is localhost.
 * All functions return null if the backend is offline.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/+$/, "") || "http://localhost:8000"
const BASE = `${API_BASE}/api`
const AGENTS_API_KEY = process.env.NEXT_PUBLIC_AGENTS_API_KEY

type PrimitiveQuery = string | number | boolean | null | undefined

export interface ApiResult<T> {
  ok: boolean
  status: number
  data: T | null
  error: string | null
}

interface ApiRequestOptions {
  method?: "GET" | "POST"
  query?: Record<string, PrimitiveQuery>
  body?: unknown
  responseType?: "json" | "text"
}

// ─── Response Types ───────────────────────────────────────────────────────────

export interface ModelMetrics {
  mae?: number | null
  rmse?: number | null
  r2?: number | null
  accuracy?: number | null
  precision?: number | null
  recall?: number | null
  f1?: number | null
  auc?: number | null
}

export interface FeatureImportance {
  feature: string
  importance: number
}

export interface ForecastPoint {
  date: string
  predicted: number
  lower: number
  upper: number
}

export interface DemandForecastResponse {
  item_id: number
  item_name: string
  forecast: ForecastPoint[]
  metrics: {
    xgb: ModelMetrics
    lr: ModelMetrics
    arima: ModelMetrics
    feature_importance: FeatureImportance[]
  }
  feature_importance: FeatureImportance[]
}

export interface StockoutItem {
  item_id: number
  item_name: string
  risk_prob: number
  risk_flag: boolean
  rolling_7d: number
  stock_ratio: number
}

export interface StockoutRiskResponse {
  items: StockoutItem[]
  metrics: {
    accuracy: number
    precision: number
    recall: number
    f1: number
    confusion_matrix: number[][]
    feature_importance: FeatureImportance[]
  }
}

export interface ExpiryItem {
  item_id: number
  item_name: string
  expiry_risk_prob: number
  high_risk: boolean
  days_until_expiry: number
  avg_daily_usage: number
  projected_consumption: number
}

export interface RocPoint {
  fpr: number
  tpr: number
}

export interface ExpiryRiskResponse {
  items: ExpiryItem[]
  metrics: {
    auc: number
    roc_curve: RocPoint[]
    coefficients: Record<string, number>
  }
}

export interface CostSavingsResponse {
  total_savings: number
  expiry_savings: number
  stockout_savings: number
  stockouts_at_risk: number
  expiry_at_risk: number
  stockout_reduction_pct: number
  expiry_reduction_pct: number
  stockout_items: (StockoutItem & { unit_price: number; reorder_lot: number; stockout_saving: number })[]
  expiry_items: (ExpiryItem & { unit_price: number; at_risk_units: number; expiry_saving: number })[]
}

export interface ArchitectureStep {
  step: number
  name: string
  desc: string
  icon: string
}

export interface ModelOverviewResponse {
  demand_metrics: ModelMetrics
  demand_lr_metrics: ModelMetrics
  demand_arima_metrics: ModelMetrics
  stockout_metrics: ModelMetrics
  stockout_confusion_matrix: number[][]
  expiry_metrics: ModelMetrics
  feature_importance: FeatureImportance[]
  architecture: ArchitectureStep[]
}

export interface DemandItem {
  id: number
  name: string
}

export interface AgentLogRecord {
  log_id: number
  agent_name: string
  task_description: string
  status: string
  level: string
  created_at: string | null
  completed_at: string | null
  result: Record<string, unknown> | null
  errors: Record<string, unknown> | null
}

export interface AgentLogsResponse {
  count: number
  records: AgentLogRecord[]
}

export interface AgentDashboardResponse {
  generated_at: string
  jobs: {
    total: number
    queued: number
    running: number
    succeeded: number
    failed: number
  }
  log_counts: Record<string, number>
  audit: {
    pending_count: number
  }
  logs_preview: AgentLogRecord[]
}

export interface SupplyChainRequestPayload {
  risk_threshold: number
  max_items: number
  cadence_hours: number
  supplier_overrides?: Record<string, Array<Record<string, unknown>>>
}

export interface SupplierRecommendation {
  supplier_id: number
  supplier_name: string
  score: number
  breakdown?: Record<string, number>
}

export interface SupplyChainDecision {
  item_id: number
  item_name: string
  risk_prob: number
  recommended_supplier: SupplierRecommendation
  recommended_order_qty: number
  reason: string
  created_po: {
    po_id: number
    supplier_id: number | null
    order_date: string | null
    expected_delivery: string | null
    status: string
  } | null
  dispatch: Record<string, unknown> | null
  tracking: {
    po_id: number
    status: string
    expected_delivery: string | null
  } | null
}

export interface SupplyChainResponse {
  ok: boolean
  agent: string
  task?: string
  result: {
    risk_threshold: number
    auto_purchase: boolean
    cadence_hours: number
    items_evaluated: number
    decisions: SupplyChainDecision[]
    cycle_duration_sec: number
    performance_target_sec: number
    sla_under_30s: boolean
  }
}

export interface DataIngestionTriggerPayload {
  source_type: "records" | "csv" | "api"
  csv_path?: string
  api_url?: string
  api_format?: "json" | "xml"
  records?: Array<Record<string, unknown>>
  allow_partial?: boolean
  run_async?: boolean
  max_retries?: number
}

export interface DataIngestionTriggerResponse {
  job_id: string | null
  status: string
  status_endpoint?: string
  result?: Record<string, unknown>
}

export interface DataIngestionJobStatus {
  job_id: string
  status: "queued" | "running" | "succeeded" | "failed" | "completed"
  created_at?: string
  started_at?: string
  completed_at?: string
  payload?: Record<string, unknown>
  result?: Record<string, unknown>
  error?: string
}

export interface ApprovalAuditEvent {
  audit_id: number
  event_type: string
  previous_status: string | null
  new_status: string
  actor: string
  comment: string | null
  metadata: Record<string, unknown> | null
  created_at: string | null
}

export interface ApprovalQueueItem {
  po_id: number
  supplier_id: number | null
  supplier_name: string | null
  item_id: number | null
  item_name: string | null
  quantity: number | null
  total_cost: number | null
  po_status: string
  approval_level: string
  approval_status: string
  escalation_required: boolean
  approval_reason: string | null
  score_breakdown: Record<string, unknown> | null
  rule_snapshot: Record<string, unknown> | null
  requested_at: string | null
  due_at: string | null
  decided_at: string | null
  decided_by: string | null
  decision_comment: string | null
  last_audit_event: {
    event_type: string
    new_status: string
    actor: string
    comment: string | null
    created_at: string | null
  } | null
}

export interface ApprovalQueueResponse {
  count: number
  items: ApprovalQueueItem[]
}

export interface ApprovalQueueDetailResponse extends ApprovalQueueItem {
  audit_trail: ApprovalAuditEvent[]
}

export interface ApprovalDecisionPayload {
  action: "approve" | "reject"
  reviewed_by: string
  reviewer_role: string
  comment?: string
}

export interface ApprovalDecisionResponse {
  po_id: number
  action: "approve" | "reject"
  approval_status: string
  po_status: string
  reviewed_by: string
  reviewer_role: string
  comment: string | null
  decided_at: string | null
}

export interface ApprovalTimeoutResponse {
  count: number
  items: Array<{
    po_id: number
    previous_status: string
    new_status: string
  }>
}

// ─── Fetch Helper ─────────────────────────────────────────────────────────────

function buildQuery(query?: Record<string, PrimitiveQuery>): string {
  if (!query) return ""
  const params = new URLSearchParams()
  Object.entries(query).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== "") {
      params.set(key, String(value))
    }
  })
  const encoded = params.toString()
  return encoded ? `?${encoded}` : ""
}

function buildHeaders(hasBody: boolean): HeadersInit {
  const headers: Record<string, string> = {}
  if (hasBody) {
    headers["Content-Type"] = "application/json"
  }
  if (AGENTS_API_KEY) {
    headers["X-API-Key"] = AGENTS_API_KEY
  }
  return headers
}

async function apiRequest<T>(path: string, options: ApiRequestOptions = {}): Promise<ApiResult<T>> {
  const {
    method = "GET",
    query,
    body,
    responseType = "json",
  } = options

  try {
    const hasBody = body !== undefined
    const res = await fetch(`${BASE}${path}${buildQuery(query)}`, {
      method,
      cache: "no-store",
      headers: buildHeaders(hasBody),
      body: hasBody ? JSON.stringify(body) : undefined,
    })

    if (!res.ok) {
      let errorMessage = `${res.status} ${res.statusText}`
      try {
        const errJson = (await res.json()) as { detail?: string }
        if (errJson?.detail) {
          errorMessage = errJson.detail
        }
      } catch {
        const text = await res.text()
        if (text) errorMessage = text
      }
      return {
        ok: false,
        status: res.status,
        data: null,
        error: errorMessage,
      }
    }

    const data = responseType === "text"
      ? ((await res.text()) as T)
      : ((await res.json()) as T)

    return {
      ok: true,
      status: res.status,
      data,
      error: null,
    }
  } catch (error) {
    return {
      ok: false,
      status: 0,
      data: null,
      error: error instanceof Error ? error.message : "Network request failed",
    }
  }
}

async function apiFetch<T>(path: string): Promise<T | null> {
  try {
    const response = await apiRequest<T>(path)
    return response.ok ? response.data : null
  } catch {
    return null
  }
}

// ─── Exports ──────────────────────────────────────────────────────────────────

export const getDemandItems  = () => apiFetch<{ items: DemandItem[] }>("/demand-items")
export const getDemandForecast = (itemId: number) =>
  apiFetch<DemandForecastResponse>(`/demand-forecast?item_id=${itemId}`)
export const getStockoutRisk  = () => apiFetch<StockoutRiskResponse>("/stockout-risk")
export const getExpiryRisk    = () => apiFetch<ExpiryRiskResponse>("/expiry-risk")
export const getCostSavings   = () => apiFetch<CostSavingsResponse>("/cost-savings")
export const getModelOverview = () => apiFetch<ModelOverviewResponse>("/model-overview")
export const getHealth        = () => apiFetch<{ status: string }>("/health")

export const getAgentsDashboard = () =>
  apiRequest<AgentDashboardResponse>("/agents/dashboard")

export const getAgentLogs = (params: {
  agent_name?: string
  status?: string
  level?: string
  q?: string
  limit?: number
  offset?: number
}) =>
  apiRequest<AgentLogsResponse>("/agents/logs", {
    query: {
      export: "json",
      ...params,
    },
  })

export const exportAgentLogsCsv = (params: {
  agent_name?: string
  status?: string
  level?: string
  q?: string
  limit?: number
  offset?: number
}) =>
  apiRequest<string>("/agents/logs", {
    query: {
      export: "csv",
      ...params,
    },
    responseType: "text",
  })

export const getSupplyChainAtRisk = (params: {
  risk_threshold: number
  max_items: number
  cadence_hours: number
}) =>
  apiRequest<SupplyChainResponse>("/agents/supply-chain/at-risk", {
    query: params,
  })

export const optimizeSupplyChain = (payload: SupplyChainRequestPayload) =>
  apiRequest<SupplyChainResponse>("/agents/supply-chain/optimize", {
    method: "POST",
    body: payload,
  })

export const triggerDataIngestion = (payload: DataIngestionTriggerPayload) =>
  apiRequest<DataIngestionTriggerResponse>("/agents/data-ingestion", {
    method: "POST",
    body: payload,
  })

export const getDataIngestionStatus = (jobId: string) =>
  apiRequest<DataIngestionJobStatus>(`/agents/data-ingestion/status/${jobId}`)

export const getApprovalQueue = (params: {
  status?: string
  approval_level?: string
  q?: string
  limit?: number
  offset?: number
}) =>
  apiRequest<ApprovalQueueResponse>("/approval-queue", {
    query: params,
  })

export const getApprovalQueueDetail = (poId: number) =>
  apiRequest<ApprovalQueueDetailResponse>(`/approval-queue/${poId}`)

export const decideApprovalQueueItem = (poId: number, payload: ApprovalDecisionPayload) =>
  apiRequest<ApprovalDecisionResponse>(`/approval-queue/${poId}/decision`, {
    method: "POST",
    body: payload,
  })

export const processApprovalTimeouts = () =>
  apiRequest<ApprovalTimeoutResponse>("/approval-queue/auto-timeout", {
    method: "POST",
  })
