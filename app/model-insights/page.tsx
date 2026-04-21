"use client"

import { useEffect, useMemo, useState } from "react"
import { DashboardLayout } from "@/components/dashboard-layout"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
} from "recharts"
import {
  Activity,
  BrainCircuit,
  FlaskConical,
  RefreshCw,
  Sparkles,
  SlidersHorizontal,
} from "lucide-react"
import {
  getDemandItems,
  getExplainItem,
  getExplainPrediction,
  getModelComparison,
  type ApiResult,
  type DemandItem,
  type ExplainabilityResponse,
  type ModelComparisonResponse,
  type ModelMetrics,
} from "@/lib/ml-api"

interface ModelArtifactsResponse {
  generated_at: string
  benchmarks: {
    lightgbm: Record<string, unknown> | null
    catboost: Record<string, unknown> | null
  }
  tuning: Record<string, unknown> | null
}

type ExplainMode = "item" | "prediction"

const tooltipStyle = {
  backgroundColor: "var(--color-card)",
  border: "1px solid var(--color-border)",
  borderRadius: "8px",
  fontSize: "12px",
  color: "var(--color-foreground)",
}

function asObject(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null
  }
  return value as Record<string, unknown>
}

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null
}

function asString(value: unknown): string | null {
  return typeof value === "string" ? value : null
}

function formatMetric(value: number | null | undefined, digits = 3): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "-"
  return value.toFixed(digits)
}

function metricRows(comparison: ModelComparisonResponse | null): Array<{
  key: string
  label: string
  metrics: ModelMetrics
}> {
  if (!comparison) return []
  return [
    { key: "lgbm", label: "LightGBM", metrics: comparison.lgbm },
    { key: "lr", label: "Linear Regression", metrics: comparison.lr },
    { key: "arima", label: "ARIMA", metrics: comparison.arima },
  ]
}

function BenchmarkCard({
  title,
  payload,
}: {
  title: string
  payload: Record<string, unknown> | null
}) {
  if (!payload) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold">{title}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-xs text-muted-foreground">No benchmark artifact found.</p>
        </CardContent>
      </Card>
    )
  }

  const trainingR2 = asNumber(payload.training_r2) ?? asNumber(payload.cv_mean_r2)
  const trainingTime = asNumber(payload.training_time_sec)
  const inference = asNumber(payload.avg_inference_ms)
  const acceptance = asObject(payload.acceptance_criteria)

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold">{title}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="grid grid-cols-3 gap-2">
          <div className="rounded-md border border-border p-2">
            <p className="text-[10px] text-muted-foreground">R2</p>
            <p className="text-sm font-semibold">{formatMetric(trainingR2, 4)}</p>
          </div>
          <div className="rounded-md border border-border p-2">
            <p className="text-[10px] text-muted-foreground">Train Time (s)</p>
            <p className="text-sm font-semibold">{formatMetric(trainingTime, 2)}</p>
          </div>
          <div className="rounded-md border border-border p-2">
            <p className="text-[10px] text-muted-foreground">Inference (ms)</p>
            <p className="text-sm font-semibold">{formatMetric(inference, 2)}</p>
          </div>
        </div>

        {acceptance && (
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(acceptance).map(([key, value]) => (
              <Badge key={key} variant="outline" className={value === true ? "border-emerald-500/30 text-emerald-600" : "border-destructive/30 text-destructive"}>
                {key.replaceAll("_", " ")}: {String(value)}
              </Badge>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export default function ModelInsightsPage() {
  const [items, setItems] = useState<DemandItem[]>([])
  const [comparison, setComparison] = useState<ModelComparisonResponse | null>(null)
  const [artifacts, setArtifacts] = useState<ModelArtifactsResponse | null>(null)

  const [baseLoading, setBaseLoading] = useState(true)
  const [baseError, setBaseError] = useState<string | null>(null)

  const [explainMode, setExplainMode] = useState<ExplainMode>("item")
  const [selectedItemId, setSelectedItemId] = useState<number | null>(null)
  const [predictionId, setPredictionId] = useState("")
  const [topK, setTopK] = useState(8)
  const [explainLoading, setExplainLoading] = useState(false)
  const [explainError, setExplainError] = useState<string | null>(null)
  const [explainData, setExplainData] = useState<ExplainabilityResponse | null>(null)

  useEffect(() => {
    async function loadInitial() {
      setBaseLoading(true)
      setBaseError(null)

      try {
        const [demandItems, modelComp, artifactRes] = await Promise.all([
          getDemandItems(),
          getModelComparison(),
          fetch("/api/model-artifacts", { cache: "no-store" }),
        ])

        const artifactJson = artifactRes.ok
          ? (await artifactRes.json()) as ModelArtifactsResponse
          : null

        const nextItems = demandItems?.items ?? []
        setItems(nextItems)
        setComparison(modelComp)
        setArtifacts(artifactJson)
        if (nextItems.length > 0) {
          setSelectedItemId(nextItems[0].id)
        }
      } catch (error) {
        setBaseError(error instanceof Error ? error.message : "Failed to load model insights")
      } finally {
        setBaseLoading(false)
      }
    }

    void loadInitial()
  }, [])

  const rows = useMemo(() => metricRows(comparison), [comparison])
  const bestR2 = useMemo(() => {
    const r2Values = rows
      .map((row) => row.metrics.r2)
      .filter((value): value is number => typeof value === "number")
    return r2Values.length > 0 ? Math.max(...r2Values) : null
  }, [rows])

  const shapTop = explainData?.shap.local.top_contributions ?? []
  const limeTop = explainData?.lime.weights ?? []

  async function runExplainability() {
    setExplainError(null)
    setExplainLoading(true)

    let response: ApiResult<ExplainabilityResponse>
    if (explainMode === "item") {
      if (!selectedItemId) {
        setExplainLoading(false)
        setExplainError("Select an item first")
        return
      }
      response = await getExplainItem(selectedItemId, topK)
    } else {
      const id = Number(predictionId)
      if (!Number.isFinite(id) || id <= 0) {
        setExplainLoading(false)
        setExplainError("Enter a valid prediction ID")
        return
      }
      response = await getExplainPrediction(id, topK)
    }

    if (!response.ok || !response.data) {
      setExplainData(null)
      setExplainError(response.error ?? "Unable to generate explanation")
      setExplainLoading(false)
      return
    }

    setExplainData(response.data)
    setExplainLoading(false)
  }

  const tuningModels = useMemo(() => {
    const tuning = asObject(artifacts?.tuning)
    if (!tuning) return []

    return Object.entries(tuning)
      .filter(([, value]) => asObject(value) !== null)
      .map(([modelName, value]) => {
        const model = asObject(value) as Record<string, unknown>
        const bestValue = asNumber(model.best_value)
        const bestParams = asObject(model.best_params)
        return {
          modelName,
          bestValue,
          bestParams,
        }
      })
  }, [artifacts?.tuning])

  return (
    <DashboardLayout title="Model Insights">
      <div className="flex flex-col gap-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-xl bg-primary/10">
              <FlaskConical className="size-5 text-primary" />
            </div>
            <div>
              <p className="text-sm font-semibold text-foreground">Explainability, Comparison, and Performance Lab</p>
              <p className="text-xs text-muted-foreground">Feeds from /api/explain/*, /api/model-comparison, and optimization artifacts</p>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => window.location.reload()}
            className="gap-1.5"
          >
            <RefreshCw className="size-3.5" />
            Refresh Data
          </Button>
        </div>

        {baseError && (
          <Alert className="border-destructive/30 bg-destructive/5">
            <AlertTitle>Unable to load model insight sources</AlertTitle>
            <AlertDescription>{baseError}</AlertDescription>
          </Alert>
        )}

        <Tabs defaultValue="explain" className="w-full">
          <TabsList className="flex flex-wrap h-auto gap-1 p-1">
            <TabsTrigger value="explain" className="gap-1.5 text-xs">
              <BrainCircuit className="size-3.5" />
              Explainability
            </TabsTrigger>
            <TabsTrigger value="comparison" className="gap-1.5 text-xs">
              <Activity className="size-3.5" />
              Model Comparison
            </TabsTrigger>
            <TabsTrigger value="benchmark" className="gap-1.5 text-xs">
              <SlidersHorizontal className="size-3.5" />
              Tuning & Benchmarks
            </TabsTrigger>
          </TabsList>

          <TabsContent value="explain" className="mt-4">
            <div className="flex flex-col gap-4">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-semibold">Generate Explanation</CardTitle>
                  <CardDescription className="text-xs">Run item or prediction-level SHAP and LIME explanation from backend models.</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-5">
                    <div className="space-y-1.5">
                      <Label className="text-xs">Mode</Label>
                      <Select value={explainMode} onValueChange={(value: ExplainMode) => setExplainMode(value)}>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="item">Item ID</SelectItem>
                          <SelectItem value="prediction">Prediction ID</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    {explainMode === "item" ? (
                      <div className="space-y-1.5 md:col-span-2">
                        <Label className="text-xs">Inventory Item</Label>
                        <Select
                          value={selectedItemId?.toString()}
                          onValueChange={(value) => setSelectedItemId(Number(value))}
                        >
                          <SelectTrigger>
                            <SelectValue placeholder="Select an item" />
                          </SelectTrigger>
                          <SelectContent>
                            {items.map((item) => (
                              <SelectItem key={item.id} value={item.id.toString()}>{item.name}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    ) : (
                      <div className="space-y-1.5 md:col-span-2">
                        <Label className="text-xs">Prediction ID</Label>
                        <Input
                          value={predictionId}
                          onChange={(event) => setPredictionId(event.target.value)}
                          placeholder="e.g. 1001"
                        />
                      </div>
                    )}

                    <div className="space-y-1.5">
                      <Label className="text-xs">Top K Features</Label>
                      <Input
                        type="number"
                        min={3}
                        max={20}
                        value={topK}
                        onChange={(event) => setTopK(Math.max(3, Math.min(20, Number(event.target.value) || 8)))}
                      />
                    </div>

                    <div className="flex items-end">
                      <Button onClick={() => void runExplainability()} className="w-full gap-1.5" disabled={explainLoading || baseLoading}>
                        {explainLoading ? <RefreshCw className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
                        Run
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {explainError && (
                <Alert className="border-destructive/30 bg-destructive/5">
                  <AlertTitle>Explainability request failed</AlertTitle>
                  <AlertDescription>{explainError}</AlertDescription>
                </Alert>
              )}

              {explainData && (
                <>
                  <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                    <Card>
                      <CardContent className="p-3">
                        <p className="text-[10px] text-muted-foreground">Model</p>
                        <p className="text-sm font-semibold">{explainData.model}</p>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="p-3">
                        <p className="text-[10px] text-muted-foreground">Item</p>
                        <p className="text-sm font-semibold">{explainData.item_name}</p>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="p-3">
                        <p className="text-[10px] text-muted-foreground">Usage Date</p>
                        <p className="text-sm font-semibold">{explainData.usage_date}</p>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="p-3">
                        <p className="text-[10px] text-muted-foreground">Prediction</p>
                        <p className="text-sm font-semibold">{formatMetric(explainData.shap.local.prediction, 3)}</p>
                      </CardContent>
                    </Card>
                  </div>

                  <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-semibold">SHAP Top Contributions</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="h-64">
                          <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={shapTop} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
                              <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                              <XAxis dataKey="feature" interval={0} angle={-20} textAnchor="end" height={70} tick={{ fontSize: 10 }} />
                              <YAxis tick={{ fontSize: 10 }} />
                              <Tooltip contentStyle={tooltipStyle} formatter={(value: number) => [value.toFixed(4), "SHAP"]} />
                              <Bar dataKey="shap_value">
                                {shapTop.map((entry) => (
                                  <Cell key={entry.feature} fill={entry.shap_value >= 0 ? "#059669" : "#dc2626"} />
                                ))}
                              </Bar>
                            </BarChart>
                          </ResponsiveContainer>
                        </div>
                      </CardContent>
                    </Card>

                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-semibold">LIME Local Weights</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="h-64">
                          <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={limeTop} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
                              <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                              <XAxis dataKey="feature" interval={0} angle={-20} textAnchor="end" height={70} tick={{ fontSize: 10 }} />
                              <YAxis tick={{ fontSize: 10 }} />
                              <Tooltip contentStyle={tooltipStyle} formatter={(value: number) => [value.toFixed(4), "Weight"]} />
                              <Bar dataKey="weight">
                                {limeTop.map((entry) => (
                                  <Cell key={entry.feature} fill={entry.weight >= 0 ? "#0369a1" : "#d97706"} />
                                ))}
                              </Bar>
                            </BarChart>
                          </ResponsiveContainer>
                        </div>
                      </CardContent>
                    </Card>
                  </div>

                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm font-semibold">Feature Snapshot</CardTitle>
                    </CardHeader>
                    <CardContent className="p-0">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Feature</TableHead>
                            <TableHead className="text-right">Value</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {explainData.feature_snapshot.map((row) => (
                            <TableRow key={row.feature}>
                              <TableCell>{row.feature}</TableCell>
                              <TableCell className="text-right">{formatMetric(row.value, 4)}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </CardContent>
                  </Card>
                </>
              )}
            </div>
          </TabsContent>

          <TabsContent value="comparison" className="mt-4">
            <div className="flex flex-col gap-4">
              {!comparison ? (
                <Alert>
                  <AlertTitle>Model comparison is unavailable</AlertTitle>
                  <AlertDescription>Ensure backend model metadata is generated before using this section.</AlertDescription>
                </Alert>
              ) : (
                <>
                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm font-semibold">Primary Production Model</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <Badge className="bg-primary/15 text-primary border-primary/30">{comparison.primary_model}</Badge>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm font-semibold">Metrics Comparison</CardTitle>
                    </CardHeader>
                    <CardContent className="p-0">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Model</TableHead>
                            <TableHead className="text-right">MAE</TableHead>
                            <TableHead className="text-right">RMSE</TableHead>
                            <TableHead className="text-right">R2</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {rows.map((row) => (
                            <TableRow key={row.key}>
                              <TableCell>
                                <div className="flex items-center gap-2">
                                  <span>{row.label}</span>
                                  {bestR2 !== null && row.metrics.r2 === bestR2 && (
                                    <Badge variant="outline" className="text-[10px] border-emerald-500/30 text-emerald-600">Best R2</Badge>
                                  )}
                                </div>
                              </TableCell>
                              <TableCell className="text-right">{formatMetric(row.metrics.mae, 3)}</TableCell>
                              <TableCell className="text-right">{formatMetric(row.metrics.rmse, 3)}</TableCell>
                              <TableCell className="text-right">{formatMetric(row.metrics.r2, 4)}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm font-semibold">Feature Importance</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="h-72">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={comparison.feature_importance.slice(0, 10)} layout="vertical" margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
                            <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                            <XAxis type="number" tick={{ fontSize: 10 }} />
                            <YAxis type="category" dataKey="feature" tick={{ fontSize: 10 }} width={110} />
                            <Tooltip contentStyle={tooltipStyle} formatter={(value: number) => [value.toFixed(4), "Importance"]} />
                            <Bar dataKey="importance" fill="var(--color-primary)" radius={[0, 4, 4, 0]} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </CardContent>
                  </Card>
                </>
              )}
            </div>
          </TabsContent>

          <TabsContent value="benchmark" className="mt-4">
            <div className="flex flex-col gap-4">
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                <BenchmarkCard title="LightGBM Benchmark" payload={artifacts?.benchmarks.lightgbm ?? null} />
                <BenchmarkCard title="CatBoost Benchmark" payload={artifacts?.benchmarks.catboost ?? null} />
              </div>

              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-semibold">Hyperparameter Optimization Results</CardTitle>
                  <CardDescription className="text-xs">Derived from backend optimization artifact outputs.</CardDescription>
                </CardHeader>
                <CardContent className="flex flex-col gap-3">
                  {tuningModels.length === 0 ? (
                    <p className="text-xs text-muted-foreground">No tuning report found.</p>
                  ) : (
                    tuningModels.map((model) => (
                      <div key={model.modelName} className="rounded-lg border border-border p-3">
                        <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                          <p className="text-sm font-semibold uppercase">{model.modelName}</p>
                          <Badge variant="outline">Best Score: {model.bestValue !== null ? String(model.bestValue) : "-"}</Badge>
                        </div>
                        {model.bestParams ? (
                          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                            {Object.entries(model.bestParams).map(([param, value]) => (
                              <div key={param} className="rounded border border-border bg-muted/20 px-2 py-1.5 text-xs">
                                <span className="text-muted-foreground">{param}: </span>
                                <span className="font-medium text-foreground">{String(value)}</span>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="text-xs text-muted-foreground">No parameters captured for this model.</p>
                        )}
                      </div>
                    ))
                  )}
                </CardContent>
              </Card>

              <p className="text-[11px] text-muted-foreground">
                Artifact generated at: {asString(artifacts?.generated_at) ?? "unknown"}
              </p>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </DashboardLayout>
  )
}
