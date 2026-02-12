"use client"

import { DashboardLayout } from "@/components/dashboard-layout"
import { StatsCard } from "@/components/stats-card"
import { StockStatusBadge, SeverityBadge } from "@/components/stock-status-badge"
import { useInventory } from "@/lib/inventory-context"
import { formatCurrency, formatDateTime, formatDate } from "@/lib/utils"
import { Category, StockStatus, AlertSeverity } from "@/lib/types"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import {
  Package,
  AlertTriangle,
  Clock,
  DollarSign,
  ClipboardList,
  TrendingDown,
} from "lucide-react"
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
} from "recharts"

export default function DashboardPage() {
  return (
    <DashboardLayout title="Dashboard">
      <DashboardContent />
    </DashboardLayout>
  )
}

function DashboardContent() {
  const { state, getLowStockItems, getExpiringItems, getUnacknowledgedAlerts } = useInventory()
  const { items, purchaseOrders, activityLogs, alerts } = state

  const totalItems = items.length
  const totalValue = items.reduce((sum, item) => sum + item.quantity * item.unitPrice, 0)
  const lowStockCount = getLowStockItems().length
  const expiringSoonCount = getExpiringItems(30).length
  const pendingOrders = purchaseOrders.filter((o) => o.status === "Pending").length

  // Category chart data
  const categoryData = Object.values(Category).map((cat) => {
    const catItems = items.filter((i) => i.category === cat)
    return {
      name: cat.length > 12 ? cat.slice(0, 12) + "..." : cat,
      fullName: cat,
      count: catItems.length,
      value: catItems.reduce((sum, i) => sum + i.quantity * i.unitPrice, 0),
    }
  })

  // Status distribution for pie chart
  const statusData = [
    { name: "In Stock", value: items.filter((i) => i.status === StockStatus.InStock).length, fill: "var(--color-success)" },
    { name: "Low Stock", value: items.filter((i) => i.status === StockStatus.LowStock).length, fill: "var(--color-warning)" },
    { name: "Out of Stock", value: items.filter((i) => i.status === StockStatus.OutOfStock).length, fill: "var(--color-destructive)" },
    { name: "Expired", value: items.filter((i) => i.status === StockStatus.Expired).length, fill: "var(--color-chart-5)" },
  ].filter((d) => d.value > 0)

  // Monthly trend data (simulated)
  const monthlyTrend = [
    { month: "Sep", consumption: 12400, restocked: 15200 },
    { month: "Oct", consumption: 13800, restocked: 11500 },
    { month: "Nov", consumption: 14200, restocked: 16800 },
    { month: "Dec", consumption: 15600, restocked: 14200 },
    { month: "Jan", consumption: 13200, restocked: 17500 },
    { month: "Feb", consumption: 11800, restocked: 13400 },
  ]

  // Critical alerts (unacknowledged)
  const criticalAlerts = getUnacknowledgedAlerts()
    .filter((a) => a.severity === AlertSeverity.Critical || a.severity === AlertSeverity.Warning)
    .slice(0, 6)

  return (
    <div className="flex flex-col gap-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <StatsCard
          title="Total Items"
          value={totalItems}
          subtitle="Across all categories"
          icon={Package}
          variant="default"
        />
        <StatsCard
          title="Low Stock"
          value={lowStockCount}
          subtitle="Items below reorder level"
          icon={TrendingDown}
          variant={lowStockCount > 5 ? "destructive" : "warning"}
        />
        <StatsCard
          title="Expiring Soon"
          value={expiringSoonCount}
          subtitle="Within next 30 days"
          icon={Clock}
          variant={expiringSoonCount > 3 ? "warning" : "default"}
        />
        <StatsCard
          title="Total Value"
          value={formatCurrency(totalValue)}
          subtitle="Current inventory value"
          icon={DollarSign}
          variant="success"
        />
        <StatsCard
          title="Pending Orders"
          value={pendingOrders}
          subtitle="Awaiting processing"
          icon={ClipboardList}
          variant="default"
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-7">
        {/* Category Breakdown */}
        <Card className="lg:col-span-4">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-foreground">Inventory by Category</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={categoryData} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} className="fill-muted-foreground" />
                  <YAxis tick={{ fontSize: 11 }} className="fill-muted-foreground" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "var(--color-card)",
                      border: "1px solid var(--color-border)",
                      borderRadius: "8px",
                      fontSize: "12px",
                      color: "var(--color-foreground)",
                    }}
                    formatter={(value: number, name: string) => {
                      if (name === "value") return [formatCurrency(value), "Value"]
                      return [value, "Items"]
                    }}
                  />
                  <Bar dataKey="count" fill="var(--color-primary)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Status Distribution */}
        <Card className="lg:col-span-3">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-foreground">Stock Status Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64 flex items-center">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={statusData}
                    cx="50%"
                    cy="50%"
                    innerRadius={55}
                    outerRadius={85}
                    paddingAngle={3}
                    dataKey="value"
                  >
                    {statusData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.fill} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "var(--color-card)",
                      border: "1px solid var(--color-border)",
                      borderRadius: "8px",
                      fontSize: "12px",
                      color: "var(--color-foreground)",
                    }}
                    formatter={(value: number, name: string) => [`${value} items`, name]}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="flex flex-col gap-2 pr-4">
                {statusData.map((entry, index) => (
                  <div key={index} className="flex items-center gap-2 text-xs whitespace-nowrap">
                    <div
                      className="size-2.5 rounded-full shrink-0"
                      style={{ backgroundColor: entry.fill }}
                    />
                    <span className="text-muted-foreground">{entry.name}</span>
                    <span className="ml-auto font-semibold text-foreground">{entry.value}</span>
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Second Charts Row */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-7">
        {/* Consumption Trend */}
        <Card className="lg:col-span-4">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-foreground">Monthly Consumption vs Restocking</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={monthlyTrend} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                  <XAxis dataKey="month" tick={{ fontSize: 11 }} className="fill-muted-foreground" />
                  <YAxis tick={{ fontSize: 11 }} className="fill-muted-foreground" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "var(--color-card)",
                      border: "1px solid var(--color-border)",
                      borderRadius: "8px",
                      fontSize: "12px",
                      color: "var(--color-foreground)",
                    }}
                  />
                  <Line type="monotone" dataKey="consumption" stroke="var(--color-destructive)" strokeWidth={2} dot={{ r: 3 }} name="Consumption" />
                  <Line type="monotone" dataKey="restocked" stroke="var(--color-primary)" strokeWidth={2} dot={{ r: 3 }} name="Restocked" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Critical Alerts */}
        <Card className="lg:col-span-3">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-semibold text-foreground">
              <span className="flex items-center gap-2">
                <AlertTriangle className="size-4 text-destructive" />
                Active Alerts
              </span>
            </CardTitle>
            <Badge variant="outline" className="text-[10px] border-destructive/30 text-destructive">
              {criticalAlerts.length} active
            </Badge>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col gap-2.5 max-h-56 overflow-y-auto">
              {criticalAlerts.map((alert) => (
                <div
                  key={alert.id}
                  className="flex flex-col gap-1 rounded-lg border border-border bg-card p-2.5"
                >
                  <div className="flex items-center gap-2">
                    <SeverityBadge severity={alert.severity} />
                    <span className="text-[10px] text-muted-foreground ml-auto">
                      {formatDateTime(alert.timestamp)}
                    </span>
                  </div>
                  <p className="text-xs text-foreground leading-relaxed">{alert.message}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Activity & Top Low Stock */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Recent Activity */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-foreground">Recent Activity</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col gap-3">
              {activityLogs.slice(0, 8).map((log) => (
                <div key={log.id} className="flex items-start gap-3">
                  <div className="mt-0.5 size-2 shrink-0 rounded-full bg-primary" />
                  <div className="flex flex-col gap-0.5 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium text-foreground">{log.action}</span>
                      <span className="text-[10px] text-muted-foreground">{formatDateTime(log.timestamp)}</span>
                    </div>
                    <p className="text-xs text-muted-foreground truncate">{log.details}</p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Items Needing Attention */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-foreground">Items Needing Attention</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col gap-2">
              {items
                .filter(
                  (i) =>
                    i.status === StockStatus.OutOfStock ||
                    i.status === StockStatus.LowStock ||
                    i.status === StockStatus.Expired
                )
                .slice(0, 8)
                .map((item) => (
                  <div
                    key={item.id}
                    className="flex items-center justify-between rounded-lg border border-border p-2.5"
                  >
                    <div className="flex flex-col gap-0.5 min-w-0 flex-1">
                      <span className="text-xs font-medium text-foreground truncate">{item.name}</span>
                      <span className="text-[10px] text-muted-foreground">
                        {item.quantity} {item.unit} | Reorder: {item.reorderLevel}
                        {item.expiryDate !== "N/A" && ` | Exp: ${formatDate(item.expiryDate)}`}
                      </span>
                    </div>
                    <StockStatusBadge status={item.status} />
                  </div>
                ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
