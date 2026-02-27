/**
 * Typed API client for the FastAPI ML backend (http://localhost:8000)
 * All functions return null if the backend is offline.
 */

const BASE = "http://localhost:8000/api"

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

// ─── Fetch Helper ─────────────────────────────────────────────────────────────

async function apiFetch<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${BASE}${path}`, { cache: "no-store" })
    if (!res.ok) return null
    return (await res.json()) as T
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
