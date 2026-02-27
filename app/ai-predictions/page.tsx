"use client"

import { useEffect, useState, useCallback } from "react"
import { DashboardLayout } from "@/components/dashboard-layout"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Progress } from "@/components/ui/progress"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table"
import {
  TrendingUp, AlertTriangle, Clock, DollarSign, BrainCircuit,
  WifiOff, RefreshCw, CheckCircle2, XCircle,
} from "lucide-react"
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, Cell,
  ScatterChart, Scatter, Legend,
} from "recharts"
import {
  getDemandItems, getDemandForecast, getStockoutRisk,
  getExpiryRisk, getCostSavings, getModelOverview,
  type DemandForecastResponse, type StockoutRiskResponse,
  type ExpiryRiskResponse, type CostSavingsResponse,
  type ModelOverviewResponse, type DemandItem,
} from "@/lib/ml-api"
import { formatCurrency } from "@/lib/utils"

export default function AIPredictionsPage() {
  return (
    <DashboardLayout title="AI Predictions">
      <AIPredictionsContent />
    </DashboardLayout>
  )
}

// ─── Tooltip style helper ─────────────────────────────────────────────────────
const ttStyle = {
  backgroundColor: "var(--color-card)",
  border: "1px solid var(--color-border)",
  borderRadius: "8px",
  fontSize: "12px",
  color: "var(--color-foreground)",
}

function OfflineBanner() {
  return (
    <Alert className="border-destructive/30 bg-destructive/5 mb-4">
      <WifiOff className="size-4 text-destructive" />
      <AlertDescription className="text-destructive font-medium ml-2">
        Python backend offline. Run:{" "}
        <code className="bg-muted px-1.5 py-0.5 rounded text-xs">
          cd backend &amp;&amp; uvicorn main:app --port 8000
        </code>
      </AlertDescription>
    </Alert>
  )
}

function LoadingSkeleton() {
  return (
    <div className="flex flex-col gap-4">
      {[...Array(3)].map((_, i) => (
        <Skeleton key={i} className="h-32 w-full rounded-xl" />
      ))}
    </div>
  )
}

// ─── Main content ─────────────────────────────────────────────────────────────
function AIPredictionsContent() {
  const [online, setOnline]     = useState<boolean | null>(null)
  const [items,  setItems]      = useState<DemandItem[]>([])

  useEffect(() => {
    fetch("http://localhost:8000/api/health")
      .then(r => r.ok ? setOnline(true) : setOnline(false))
      .catch(() => setOnline(false))
    getDemandItems().then(d => d && setItems(d.items))
  }, [])

  const statusBadge =
    online === null ? <Badge variant="outline" className="text-xs animate-pulse">Connecting…</Badge>
    : online        ? <Badge className="bg-emerald-500/20 text-emerald-600 border-emerald-500/30 text-xs gap-1"><CheckCircle2 className="size-3"/>Backend Online</Badge>
                    : <Badge variant="destructive" className="text-xs gap-1"><XCircle className="size-3"/>Backend Offline</Badge>

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-xl bg-primary/10">
            <BrainCircuit className="size-5 text-primary" />
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Powered by XGBoost · Random Forest · Logistic Regression</p>
          </div>
        </div>
        {statusBadge}
      </div>

      {online === false && <OfflineBanner />}

      <Tabs defaultValue="demand" className="w-full">
        <TabsList className="flex flex-wrap h-auto gap-1 p-1">
          <TabsTrigger value="demand"   className="gap-1.5 text-xs"><TrendingUp  className="size-3.5"/>Demand Forecast</TabsTrigger>
          <TabsTrigger value="stockout" className="gap-1.5 text-xs"><AlertTriangle className="size-3.5"/>Stockout Risk</TabsTrigger>
          <TabsTrigger value="expiry"   className="gap-1.5 text-xs"><Clock       className="size-3.5"/>Expiry Risk</TabsTrigger>
          <TabsTrigger value="savings"  className="gap-1.5 text-xs"><DollarSign  className="size-3.5"/>Cost Savings</TabsTrigger>
          <TabsTrigger value="overview" className="gap-1.5 text-xs"><BrainCircuit className="size-3.5"/>Model Overview</TabsTrigger>
        </TabsList>

        <TabsContent value="demand"   className="mt-4"><DemandTab   items={items} backendOnline={online === true} /></TabsContent>
        <TabsContent value="stockout" className="mt-4"><StockoutTab backendOnline={online === true} /></TabsContent>
        <TabsContent value="expiry"   className="mt-4"><ExpiryTab   backendOnline={online === true} /></TabsContent>
        <TabsContent value="savings"  className="mt-4"><SavingsTab  backendOnline={online === true} /></TabsContent>
        <TabsContent value="overview" className="mt-4"><OverviewTab backendOnline={online === true} /></TabsContent>
      </Tabs>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// TAB 1: Demand Forecast
// ─────────────────────────────────────────────────────────────────────────────
function DemandTab({ items, backendOnline }: { items: DemandItem[]; backendOnline: boolean }) {
  const [selectedId,  setSelectedId]  = useState<number | null>(null)
  const [data,        setData]        = useState<DemandForecastResponse | null>(null)
  const [loading,     setLoading]     = useState(false)

  useEffect(() => {
    if (items.length > 0 && !selectedId) setSelectedId(items[0].id)
  }, [items])

  useEffect(() => {
    if (!selectedId || !backendOnline) return
    setLoading(true)
    getDemandForecast(selectedId).then(d => { setData(d); setLoading(false) })
  }, [selectedId, backendOnline])

  const modelComparison = data ? [
    { model: "Linear Reg.", mae: data.metrics.lr?.mae ?? 0,    rmse: data.metrics.lr?.rmse ?? 0,    r2: data.metrics.lr?.r2 ?? 0 },
    { model: "ARIMA",       mae: data.metrics.arima?.mae ?? 0, rmse: data.metrics.arima?.rmse ?? 0, r2: data.metrics.arima?.r2 ?? 0 },
    { model: "XGBoost",     mae: data.metrics.xgb?.mae ?? 0,   rmse: data.metrics.xgb?.rmse ?? 0,   r2: data.metrics.xgb?.r2 ?? 0 },
  ] : []

  return (
    <div className="flex flex-col gap-4">
      {/* Item selector */}
      <Card>
        <CardContent className="pt-4 pb-3">
          <div className="flex items-center gap-3">
            <span className="text-sm font-medium text-foreground">Select Item:</span>
            <Select value={selectedId?.toString()} onValueChange={v => setSelectedId(Number(v))}>
              <SelectTrigger className="w-[280px]">
                <SelectValue placeholder="Choose an inventory item…" />
              </SelectTrigger>
              <SelectContent className="max-h-64">
                {items.map(item => (
                  <SelectItem key={item.id} value={item.id.toString()}>{item.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            {loading && <RefreshCw className="size-4 animate-spin text-primary" />}
          </div>
        </CardContent>
      </Card>

      {!backendOnline && <LoadingSkeleton />}
      {backendOnline && loading && <LoadingSkeleton />}

      {data && !loading && (
        <>
          {/* 14-day Forecast Chart */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold">14-Day Demand Forecast — {data.item_name}</CardTitle>
              <CardDescription className="text-xs">XGBoost prediction with 80% confidence band</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={data.forecast} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                    <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={d => d.slice(5)} />
                    <YAxis tick={{ fontSize: 10 }} />
                    <Tooltip contentStyle={ttStyle} />
                    <Line type="monotone" dataKey="upper"     stroke="var(--color-primary)" strokeWidth={0} dot={false} name="Upper" strokeDasharray="4 4" opacity={0.3} />
                    <Line type="monotone" dataKey="lower"     stroke="var(--color-primary)" strokeWidth={0} dot={false} name="Lower" strokeDasharray="4 4" opacity={0.3} />
                    <Line type="monotone" dataKey="predicted" stroke="var(--color-primary)" strokeWidth={2.5} dot={{ r: 3 }} name="Predicted Demand" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>

          {/* Model comparison + Feature importance */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold">Model Comparison</CardTitle>
                <CardDescription className="text-xs">Lower MAE/RMSE = better; Higher R² = better</CardDescription>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Model</TableHead>
                      <TableHead className="text-right">MAE</TableHead>
                      <TableHead className="text-right">RMSE</TableHead>
                      <TableHead className="text-right">R²</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {modelComparison.map((m, i) => (
                      <TableRow key={m.model} className={i === 2 ? "bg-primary/5 font-semibold" : ""}>
                        <TableCell className="font-medium">
                          {m.model}
                          {i === 2 && <Badge className="ml-2 text-[10px] py-0 bg-primary/20 text-primary border-primary/30">Best</Badge>}
                        </TableCell>
                        <TableCell className="text-right">{m.mae.toFixed(2)}</TableCell>
                        <TableCell className="text-right">{m.rmse.toFixed(2)}</TableCell>
                        <TableCell className="text-right">{m.r2.toFixed(3)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold">Feature Importance (XGBoost)</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-52">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={data.feature_importance.slice(0, 7)} layout="vertical" margin={{ top: 0, right: 10, bottom: 0, left: 60 }}>
                      <XAxis type="number" tick={{ fontSize: 10 }} />
                      <YAxis type="category" dataKey="feature" tick={{ fontSize: 10 }} width={60} />
                      <Tooltip contentStyle={ttStyle} formatter={(v: number) => [v.toFixed(4), "Importance"]} />
                      <Bar dataKey="importance" fill="var(--color-primary)" radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// TAB 2: Stockout Risk
// ─────────────────────────────────────────────────────────────────────────────
function StockoutTab({ backendOnline }: { backendOnline: boolean }) {
  const [data, setData] = useState<StockoutRiskResponse | null>(null)

  useEffect(() => {
    if (!backendOnline) return
    getStockoutRisk().then(setData)
  }, [backendOnline])

  const m = data?.metrics
  const cm = m?.confusion_matrix ?? [[0, 0], [0, 0]]
  const cmLabels = ["No Stockout", "Stockout"]
  const highRisk = data?.items.filter(i => i.risk_flag) ?? []

  return (
    <div className="flex flex-col gap-4">
      {!backendOnline && <LoadingSkeleton />}
      {backendOnline && !data && <LoadingSkeleton />}
      {data && (
        <>
          {/* Metrics row */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              { label: "Accuracy",  value: m?.accuracy,  color: "text-primary" },
              { label: "Precision", value: m?.precision, color: "text-emerald-600" },
              { label: "Recall",    value: m?.recall,    color: "text-amber-600" },
              { label: "F1 Score",  value: m?.f1,        color: "text-purple-600" },
            ].map(({ label, value, color }) => (
              <Card key={label}>
                <CardContent className="p-4 text-center">
                  <p className="text-xs text-muted-foreground">{label}</p>
                  <p className={`text-2xl font-bold mt-1 ${color}`}>{((value ?? 0) * 100).toFixed(1)}%</p>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Risk table + Confusion matrix */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold flex items-center gap-2">
                  <AlertTriangle className="size-4 text-destructive" />
                  High-Risk Items ({highRisk.length} at risk)
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Item</TableHead>
                      <TableHead>Risk Probability</TableHead>
                      <TableHead className="text-right">7-day Avg</TableHead>
                      <TableHead>Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.items.slice(0, 12).map(item => (
                      <TableRow key={item.item_id}>
                        <TableCell className="font-medium text-xs">{item.item_name}</TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <Progress
                              value={item.risk_prob * 100}
                              className="h-2 w-28"
                            />
                            <span className={`text-xs font-semibold ${item.risk_prob > 0.7 ? "text-destructive" : item.risk_prob > 0.4 ? "text-amber-600" : "text-emerald-600"}`}>
                              {(item.risk_prob * 100).toFixed(0)}%
                            </span>
                          </div>
                        </TableCell>
                        <TableCell className="text-right text-xs">{item.rolling_7d.toFixed(1)}</TableCell>
                        <TableCell>
                          {item.risk_flag
                            ? <Badge variant="destructive" className="text-[10px]">At Risk</Badge>
                            : <Badge variant="outline" className="text-[10px] border-emerald-500/30 text-emerald-600">Safe</Badge>}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>

            {/* Confusion Matrix */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold">Confusion Matrix</CardTitle>
                <CardDescription className="text-xs">Random Forest Classifier</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex flex-col gap-1 text-xs">
                  <div className="flex gap-1 justify-end pr-1">
                    {cmLabels.map(l => <span key={l} className="w-24 text-center text-muted-foreground font-medium">{l}</span>)}
                  </div>
                  {cm.map((row, ri) => (
                    <div key={ri} className="flex items-center gap-1">
                      <span className="w-24 text-right pr-2 text-muted-foreground font-medium shrink-0">{cmLabels[ri]}</span>
                      {row.map((val, ci) => (
                        <div key={ci} className={`w-24 h-14 rounded-lg flex items-center justify-center font-bold text-lg ${
                          ri === ci ? "bg-primary/20 text-primary" : "bg-destructive/10 text-destructive"
                        }`}>
                          {val}
                        </div>
                      ))}
                    </div>
                  ))}
                  <div className="flex gap-4 mt-3 text-[10px] text-muted-foreground">
                    <span className="flex items-center gap-1"><span className="size-2 rounded bg-primary/40 inline-block"/>Correct predictions</span>
                    <span className="flex items-center gap-1"><span className="size-2 rounded bg-destructive/40 inline-block"/>Errors</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// TAB 3: Expiry Risk
// ─────────────────────────────────────────────────────────────────────────────
function ExpiryTab({ backendOnline }: { backendOnline: boolean }) {
  const [data, setData] = useState<ExpiryRiskResponse | null>(null)

  useEffect(() => {
    if (!backendOnline) return
    getExpiryRisk().then(setData)
  }, [backendOnline])

  const auc = data?.metrics?.auc ?? 0
  const roc = data?.metrics?.roc_curve ?? []

  return (
    <div className="flex flex-col gap-4">
      {!backendOnline && <LoadingSkeleton />}
      {backendOnline && !data && <LoadingSkeleton />}
      {data && (
        <>
          {/* AUC + high risk count */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Card>
              <CardContent className="p-4 text-center">
                <p className="text-xs text-muted-foreground">AUC Score</p>
                <p className="text-2xl font-bold text-primary mt-1">{auc.toFixed(3)}</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 text-center">
                <p className="text-xs text-muted-foreground">High Risk Batches</p>
                <p className="text-2xl font-bold text-destructive mt-1">{data.items.filter(i => i.high_risk).length}</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 text-center">
                <p className="text-xs text-muted-foreground">Safe Batches</p>
                <p className="text-2xl font-bold text-emerald-600 mt-1">{data.items.filter(i => !i.high_risk).length}</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 text-center">
                <p className="text-xs text-muted-foreground">Model</p>
                <p className="text-sm font-bold text-foreground mt-2">Logistic Regression</p>
              </CardContent>
            </Card>
          </div>

          {/* ROC Curve + Risk table */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold">ROC Curve</CardTitle>
                <CardDescription className="text-xs">AUC = {auc.toFixed(4)} — higher is better</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={roc} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                      <XAxis dataKey="fpr" type="number" domain={[0, 1]} tick={{ fontSize: 10 }} label={{ value: "FPR", position: "insideBottom", fontSize: 10, offset: -2 }} />
                      <YAxis type="number" domain={[0, 1]} tick={{ fontSize: 10 }} label={{ value: "TPR", angle: -90, position: "insideLeft", fontSize: 10 }} />
                      <Tooltip contentStyle={ttStyle} formatter={(v: number) => [v.toFixed(3)]} />
                      <Line type="monotone" dataKey="tpr" stroke="var(--color-primary)" strokeWidth={2} dot={false} name="ROC" />
                      <ReferenceLine x={0} y={0} stroke="var(--color-muted-foreground)" strokeDasharray="4 4" />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold">Batch Expiry Risk</CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <div className="max-h-64 overflow-y-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Item</TableHead>
                        <TableHead className="text-right">Days Left</TableHead>
                        <TableHead>Risk</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {data.items.slice(0, 15).map(item => (
                        <TableRow key={item.item_id}>
                          <TableCell className="text-xs font-medium">{item.item_name}</TableCell>
                          <TableCell className="text-right text-xs">{item.days_until_expiry}</TableCell>
                          <TableCell>
                            <div className="flex items-center gap-1.5">
                              <Progress value={item.expiry_risk_prob * 100} className="h-1.5 w-16" />
                              <span className={`text-[10px] font-semibold ${item.high_risk ? "text-destructive" : "text-emerald-600"}`}>
                                {(item.expiry_risk_prob * 100).toFixed(0)}%
                              </span>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// TAB 4: Cost Savings
// ─────────────────────────────────────────────────────────────────────────────
function SavingsTab({ backendOnline }: { backendOnline: boolean }) {
  const [data, setData] = useState<CostSavingsResponse | null>(null)

  useEffect(() => {
    if (!backendOnline) return
    getCostSavings().then(setData)
  }, [backendOnline])

  const barData = data ? [
    { name: "Stockout\nSavings", value: data.stockout_savings, fill: "var(--color-primary)" },
    { name: "Expiry\nSavings",   value: data.expiry_savings,   fill: "var(--color-chart-4)" },
    { name: "Total",             value: data.total_savings,    fill: "var(--color-success)" },
  ] : []

  return (
    <div className="flex flex-col gap-4">
      {!backendOnline && <LoadingSkeleton />}
      {backendOnline && !data && <LoadingSkeleton />}
      {data && (
        <>
          {/* KPI cards */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Card className="border-emerald-500/30 bg-emerald-500/5">
              <CardContent className="p-4">
                <p className="text-xs text-muted-foreground">Estimated Total Savings</p>
                <p className="text-2xl font-bold text-emerald-600 mt-1">{formatCurrency(data.total_savings)}</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <p className="text-xs text-muted-foreground">Stockout Savings</p>
                <p className="text-xl font-bold text-primary mt-1">{formatCurrency(data.stockout_savings)}</p>
                <p className="text-[10px] text-muted-foreground mt-0.5">{data.stockout_reduction_pct}% reduction</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <p className="text-xs text-muted-foreground">Expiry Savings</p>
                <p className="text-xl font-bold text-amber-600 mt-1">{formatCurrency(data.expiry_savings)}</p>
                <p className="text-[10px] text-muted-foreground mt-0.5">{data.expiry_reduction_pct}% reduction</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <p className="text-xs text-muted-foreground">Items At Risk</p>
                <p className="text-xl font-bold text-destructive mt-1">{data.stockouts_at_risk + data.expiry_at_risk}</p>
                <p className="text-[10px] text-muted-foreground mt-0.5">{data.stockouts_at_risk} stockout · {data.expiry_at_risk} expiry</p>
              </CardContent>
            </Card>
          </div>

          {/* Savings chart */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold">Cost Savings Breakdown</CardTitle>
              <CardDescription className="text-xs">
                Formula: (Expired Units Reduced × Unit Cost) + (Stockouts Avoided × Emergency Premium)
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={barData} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                    <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} tickFormatter={v => `$${(v / 1000).toFixed(0)}k`} />
                    <Tooltip contentStyle={ttStyle} formatter={(v: number) => [formatCurrency(v), "Savings"]} />
                    <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                      {barData.map((entry, index) => <Cell key={index} fill={entry.fill} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>

          {/* Per-item stockout table */}
          {data.stockout_items.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold">Stockout Avoidance Detail</CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Item</TableHead>
                      <TableHead className="text-right">Unit Price</TableHead>
                      <TableHead className="text-right">Risk %</TableHead>
                      <TableHead className="text-right">Savings</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.stockout_items.slice(0, 8).map(item => (
                      <TableRow key={item.item_id}>
                        <TableCell className="text-xs font-medium">{item.item_name}</TableCell>
                        <TableCell className="text-right text-xs">{formatCurrency(item.unit_price)}</TableCell>
                        <TableCell className="text-right text-xs text-destructive font-semibold">{(item.risk_prob * 100).toFixed(0)}%</TableCell>
                        <TableCell className="text-right text-xs text-emerald-600 font-semibold">{formatCurrency(item.stockout_saving)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// TAB 5: Model Overview
// ─────────────────────────────────────────────────────────────────────────────
function OverviewTab({ backendOnline }: { backendOnline: boolean }) {
  const [data, setData] = useState<ModelOverviewResponse | null>(null)

  useEffect(() => {
    if (!backendOnline) return
    getModelOverview().then(setData)
  }, [backendOnline])

  return (
    <div className="flex flex-col gap-4">
      {!backendOnline && <LoadingSkeleton />}
      {backendOnline && !data && <LoadingSkeleton />}
      {data && (
        <>
          {/* Architecture Flow */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold">System Architecture Pipeline</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2 items-center">
                {data.architecture.map((step, i) => (
                  <div key={step.step} className="flex items-center gap-2">
                    <div className="flex flex-col items-center gap-1 text-center w-28">
                      <div className="size-9 rounded-lg bg-primary/10 flex items-center justify-center text-primary font-bold text-sm shrink-0">
                        {step.step}
                      </div>
                      <span className="text-[10px] font-semibold text-foreground leading-tight">{step.name}</span>
                      <span className="text-[9px] text-muted-foreground leading-tight">{step.desc}</span>
                    </div>
                    {i < data.architecture.length - 1 && (
                      <span className="text-muted-foreground font-bold text-lg shrink-0">→</span>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Model metrics comparison table */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold">All Model Metrics Summary</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Model</TableHead>
                    <TableHead>Task</TableHead>
                    <TableHead>Algorithm</TableHead>
                    <TableHead className="text-right">Primary Metric</TableHead>
                    <TableHead className="text-right">Value</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow>
                    <TableCell className="font-medium">Demand Forecast</TableCell>
                    <TableCell>Regression</TableCell>
                    <TableCell><Badge variant="outline" className="text-[10px]">XGBoost</Badge></TableCell>
                    <TableCell className="text-right text-xs">R²</TableCell>
                    <TableCell className="text-right font-semibold text-primary">{(data.demand_metrics?.r2 ?? 0).toFixed(3)}</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell className="font-medium">Demand (LR)</TableCell>
                    <TableCell>Regression</TableCell>
                    <TableCell><Badge variant="outline" className="text-[10px]">Linear Reg.</Badge></TableCell>
                    <TableCell className="text-right text-xs">R²</TableCell>
                    <TableCell className="text-right font-semibold">{(data.demand_lr_metrics?.r2 ?? 0).toFixed(3)}</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell className="font-medium">Stockout Risk</TableCell>
                    <TableCell>Classification</TableCell>
                    <TableCell><Badge variant="outline" className="text-[10px]">Random Forest</Badge></TableCell>
                    <TableCell className="text-right text-xs">F1</TableCell>
                    <TableCell className="text-right font-semibold text-primary">{(data.stockout_metrics?.f1 ?? 0).toFixed(3)}</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell className="font-medium">Expiry Risk</TableCell>
                    <TableCell>Classification</TableCell>
                    <TableCell><Badge variant="outline" className="text-[10px]">Logistic Reg.</Badge></TableCell>
                    <TableCell className="text-right text-xs">AUC</TableCell>
                    <TableCell className="text-right font-semibold text-primary">{(data.expiry_metrics?.auc ?? 0).toFixed(3)}</TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          {/* SHAP/Feature importance */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold">Feature Importance (SHAP-proxy via XGBoost)</CardTitle>
              <CardDescription className="text-xs">Features ranked by contribution to demand forecast accuracy</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-60">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data.feature_importance} layout="vertical" margin={{ top: 0, right: 10, bottom: 0, left: 80 }}>
                    <XAxis type="number" tick={{ fontSize: 10 }} />
                    <YAxis type="category" dataKey="feature" tick={{ fontSize: 10 }} width={80} />
                    <Tooltip contentStyle={ttStyle} formatter={(v: number) => [v.toFixed(4), "Importance"]} />
                    <Bar dataKey="importance" radius={[0, 4, 4, 0]}>
                      {data.feature_importance.map((_, i) => (
                        <Cell key={i} fill={i === 0 ? "var(--color-primary)" : i < 3 ? "var(--color-chart-4)" : "var(--color-chart-2)"} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}
