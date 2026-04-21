"use client"

import { useState, useMemo } from "react"
import { DashboardLayout } from "@/components/dashboard-layout"
import { StockStatusBadge } from "@/components/stock-status-badge"
import { useInventory } from "@/lib/inventory-context"
import {
  formatCurrency,
  formatDate,
  getDaysUntilExpiry,
  exportToCSV,
} from "@/lib/utils"
import { Category, StockStatus } from "@/lib/types"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  BarChart3,
  Download,
  Package,
  TrendingDown,
  Clock,
  Building2,
  Truck,
  DollarSign,
  AlertTriangle,
  PieChart as PieChartIcon,
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
} from "recharts"

export default function ReportsPage() {
  return (
    <DashboardLayout title="Reports & Analytics">
      <ReportsContent />
    </DashboardLayout>
  )
}

function ReportsContent() {
  const {
    state,
    getLowStockItems,
    getExpiringItems,
    getExpiredItems,
    getItemsByCategory,
    getItemsByDepartment,
    getItemsBySupplier,
    getSupplierById,
  } = useInventory()
  const { items, suppliers, departments, purchaseOrders } = state

  return (
    <div className="flex flex-col gap-6">
      {/* Report Tabs */}
      <Tabs defaultValue="overview" className="w-full">
        <TabsList className="flex flex-wrap h-auto gap-1 p-1">
          <TabsTrigger value="overview" className="gap-1.5 text-xs">
            <BarChart3 className="size-3.5" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="stock" className="gap-1.5 text-xs">
            <TrendingDown className="size-3.5" />
            Stock Report
          </TabsTrigger>
          <TabsTrigger value="expiry" className="gap-1.5 text-xs">
            <Clock className="size-3.5" />
            Expiry Report
          </TabsTrigger>
          <TabsTrigger value="department" className="gap-1.5 text-xs">
            <Building2 className="size-3.5" />
            Department Usage
          </TabsTrigger>
          <TabsTrigger value="supplier" className="gap-1.5 text-xs">
            <Truck className="size-3.5" />
            Supplier Report
          </TabsTrigger>
          <TabsTrigger value="valuation" className="gap-1.5 text-xs">
            <DollarSign className="size-3.5" />
            Valuation
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-4">
          <OverviewReport
            items={items}
          />
        </TabsContent>

        <TabsContent value="stock" className="mt-4">
          <StockReport
            items={items}
            lowStockItems={getLowStockItems()}
            getSupplierById={getSupplierById}
          />
        </TabsContent>

        <TabsContent value="expiry" className="mt-4">
          <ExpiryReport
            items={items}
            expiringItems={getExpiringItems(90)}
            expiredItems={getExpiredItems()}
          />
        </TabsContent>

        <TabsContent value="department" className="mt-4">
          <DepartmentReport
            departments={departments}
            getItemsByDepartment={getItemsByDepartment}
          />
        </TabsContent>

        <TabsContent value="supplier" className="mt-4">
          <SupplierReport
            suppliers={suppliers}
            purchaseOrders={purchaseOrders}
            getItemsBySupplier={getItemsBySupplier}
          />
        </TabsContent>

        <TabsContent value="valuation" className="mt-4">
          <ValuationReport
            items={items}
            getItemsByCategory={getItemsByCategory}
          />
        </TabsContent>
      </Tabs>
    </div>
  )
}

// Overview Report
function OverviewReport({
  items,
}: {
  items: typeof import("@/lib/types").InventoryItem extends never ? never : ReturnType<typeof useInventory>["state"]["items"]
}) {
  const totalItems = items.length
  const totalQuantity = items.reduce((sum, i) => sum + i.quantity, 0)
  const totalValue = items.reduce((sum, i) => sum + i.quantity * i.unitPrice, 0)
  const avgValue = totalValue / totalItems || 0
  const outOfStock = items.filter((i) => i.status === StockStatus.OutOfStock).length
  const lowStock = items.filter((i) => i.status === StockStatus.LowStock).length

  const categoryData = Object.values(Category).map((cat) => {
    const catItems = items.filter((i) => i.category === cat)
    return {
      name: cat.length > 14 ? cat.slice(0, 14) + "..." : cat,
      fullName: cat,
      items: catItems.length,
      quantity: catItems.reduce((sum, i) => sum + i.quantity, 0),
      value: catItems.reduce((sum, i) => sum + i.quantity * i.unitPrice, 0),
    }
  })

  const statusPieData = [
    { name: "In Stock", value: items.filter((i) => i.status === StockStatus.InStock).length, fill: "var(--color-success)" },
    { name: "Low Stock", value: items.filter((i) => i.status === StockStatus.LowStock).length, fill: "var(--color-warning)" },
    { name: "Out of Stock", value: items.filter((i) => i.status === StockStatus.OutOfStock).length, fill: "var(--color-destructive)" },
    { name: "Expired", value: items.filter((i) => i.status === StockStatus.Expired).length, fill: "var(--color-chart-5)" },
  ].filter((d) => d.value > 0)

  return (
    <div className="flex flex-col gap-4">
      {/* Summary cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Card>
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground">Total Unique Items</p>
            <p className="text-2xl font-bold text-foreground mt-1">{totalItems}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground">Total Quantity</p>
            <p className="text-2xl font-bold text-foreground mt-1">{totalQuantity.toLocaleString()}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground">Total Inventory Value</p>
            <p className="text-2xl font-bold text-foreground mt-1">{formatCurrency(totalValue)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground">Items Needing Attention</p>
            <p className="text-2xl font-bold text-destructive mt-1">{outOfStock + lowStock}</p>
          </CardContent>
        </Card>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-foreground">Value by Category</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={categoryData} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                  <XAxis dataKey="name" tick={{ fontSize: 10 }} className="fill-muted-foreground" />
                  <YAxis tick={{ fontSize: 10 }} className="fill-muted-foreground" tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "var(--color-card)",
                      border: "1px solid var(--color-border)",
                      borderRadius: "8px",
                      fontSize: "12px",
                      color: "var(--color-foreground)",
                    }}
                    formatter={(value: number) => [formatCurrency(value), "Value"]}
                  />
                  <Bar dataKey="value" fill="var(--color-primary)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-foreground">Status Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-72 flex items-center">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={statusPieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={95}
                    paddingAngle={3}
                    dataKey="value"
                    label={({ name, value }) => `${name}: ${value}`}
                  >
                    {statusPieData.map((entry, index) => (
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
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Category Breakdown Table */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-sm font-semibold text-foreground">Category Breakdown</CardTitle>
          <Button
            size="sm"
            variant="outline"
            onClick={() => exportToCSV(
              categoryData.map((c) => ({ Category: c.fullName, Items: c.items, Quantity: c.quantity, Value: c.value })),
              "category-breakdown"
            )}
          >
            <Download className="size-4 mr-1.5" />
            Export CSV
          </Button>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Category</TableHead>
                <TableHead className="text-right">Items</TableHead>
                <TableHead className="text-right">Total Quantity</TableHead>
                <TableHead className="text-right">Total Value</TableHead>
                <TableHead className="text-right">Avg Value/Item</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {categoryData.map((cat) => (
                <TableRow key={cat.fullName}>
                  <TableCell className="font-medium text-foreground">{cat.fullName}</TableCell>
                  <TableCell className="text-right">{cat.items}</TableCell>
                  <TableCell className="text-right">{cat.quantity.toLocaleString()}</TableCell>
                  <TableCell className="text-right font-medium">{formatCurrency(cat.value)}</TableCell>
                  <TableCell className="text-right">{cat.items > 0 ? formatCurrency(cat.value / cat.items) : "$0"}</TableCell>
                </TableRow>
              ))}
              <TableRow className="font-bold border-t-2">
                <TableCell className="text-foreground">Total</TableCell>
                <TableCell className="text-right">{totalItems}</TableCell>
                <TableCell className="text-right">{totalQuantity.toLocaleString()}</TableCell>
                <TableCell className="text-right">{formatCurrency(totalValue)}</TableCell>
                <TableCell className="text-right">{formatCurrency(avgValue)}</TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}

// Stock Report
function StockReport({
  items,
  lowStockItems,
  getSupplierById,
}: {
  items: ReturnType<typeof useInventory>["state"]["items"]
  lowStockItems: ReturnType<typeof useInventory>["state"]["items"]
  getSupplierById: ReturnType<typeof useInventory>["getSupplierById"]
}) {
  const [categoryFilter, setCategoryFilter] = useState<string>("all")

  const filteredLowStock = useMemo(() => {
    if (categoryFilter === "all") return lowStockItems
    return lowStockItems.filter((i) => i.category === categoryFilter)
  }, [lowStockItems, categoryFilter])

  const outOfStock = items.filter((i) => i.status === StockStatus.OutOfStock)

  return (
    <div className="flex flex-col gap-4">
      {outOfStock.length > 0 && (
        <Card className="border-destructive/30">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-destructive flex items-center gap-2">
              <AlertTriangle className="size-4" />
              Out of Stock Items - Immediate Action Required
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col gap-2">
              {outOfStock.map((item) => (
                <div key={item.id} className="flex items-center justify-between rounded-lg border border-destructive/20 bg-destructive/5 p-3">
                  <div>
                    <p className="text-sm font-medium text-foreground">{item.name}</p>
                    <p className="text-xs text-muted-foreground">{item.sku} | Supplier: {getSupplierById(item.supplierId)?.name ?? "Unknown"}</p>
                  </div>
                  <div className="text-right">
                    <StockStatusBadge status={item.status} />
                    <p className="text-xs text-muted-foreground mt-1">Reorder: {item.reorderLevel} {item.unit}</p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h3 className="text-sm font-semibold text-foreground">Low Stock Items ({filteredLowStock.length})</h3>
          <Select value={categoryFilter} onValueChange={setCategoryFilter}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Category" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Categories</SelectItem>
              {Object.values(Category).map((cat) => (
                <SelectItem key={cat} value={cat}>{cat}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={() => exportToCSV(
            filteredLowStock.map((i) => ({
              Name: i.name,
              SKU: i.sku,
              Category: i.category,
              Current: i.quantity,
              ReorderLevel: i.reorderLevel,
              Unit: i.unit,
              Status: i.status,
              Supplier: getSupplierById(i.supplierId)?.name ?? "Unknown",
            })),
            "low-stock-report"
          )}
        >
          <Download className="size-4 mr-1.5" />
          Export
        </Button>
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Item Name</TableHead>
                <TableHead>SKU</TableHead>
                <TableHead>Category</TableHead>
                <TableHead className="text-right">Current</TableHead>
                <TableHead className="text-right">Reorder Level</TableHead>
                <TableHead className="text-right">Deficit</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Supplier</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredLowStock.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={8} className="text-center py-8 text-muted-foreground">
                    No low stock items found for this category.
                  </TableCell>
                </TableRow>
              ) : (
                filteredLowStock.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell className="font-medium text-foreground">{item.name}</TableCell>
                    <TableCell className="text-xs text-muted-foreground font-mono">{item.sku}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className="text-[10px]">{item.category}</Badge>
                    </TableCell>
                    <TableCell className="text-right font-semibold text-destructive">{item.quantity}</TableCell>
                    <TableCell className="text-right">{item.reorderLevel}</TableCell>
                    <TableCell className="text-right font-medium text-destructive">
                      -{Math.max(0, item.reorderLevel - item.quantity)}
                    </TableCell>
                    <TableCell><StockStatusBadge status={item.status} /></TableCell>
                    <TableCell className="text-xs">{getSupplierById(item.supplierId)?.name ?? "Unknown"}</TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}

// Expiry Report
function ExpiryReport({
  items,
  expiringItems,
  expiredItems,
}: {
  items: ReturnType<typeof useInventory>["state"]["items"]
  expiringItems: ReturnType<typeof useInventory>["state"]["items"]
  expiredItems: ReturnType<typeof useInventory>["state"]["items"]
}) {
  const allExpirableItems = items
    .filter((i) => i.expiryDate !== "N/A")
    .sort((a, b) => new Date(a.expiryDate).getTime() - new Date(b.expiryDate).getTime())

  const expiryBuckets = [
    { label: "Expired", items: expiredItems, color: "bg-destructive text-destructive-foreground" },
    { label: "0-7 days", items: allExpirableItems.filter((i) => { const d = getDaysUntilExpiry(i.expiryDate); return d !== null && d >= 0 && d <= 7 }), color: "bg-destructive text-destructive-foreground" },
    { label: "8-30 days", items: allExpirableItems.filter((i) => { const d = getDaysUntilExpiry(i.expiryDate); return d !== null && d > 7 && d <= 30 }), color: "bg-warning text-warning-foreground" },
    { label: "31-90 days", items: allExpirableItems.filter((i) => { const d = getDaysUntilExpiry(i.expiryDate); return d !== null && d > 30 && d <= 90 }), color: "bg-primary text-primary-foreground" },
    { label: "90+ days", items: allExpirableItems.filter((i) => { const d = getDaysUntilExpiry(i.expiryDate); return d !== null && d > 90 }), color: "bg-success text-success-foreground" },
  ]

  const bucketChartData = expiryBuckets.map((b) => ({
    name: b.label,
    count: b.items.length,
  }))

  const COLORS = ["var(--color-destructive)", "var(--color-destructive)", "var(--color-warning)", "var(--color-primary)", "var(--color-success)"]

  return (
    <div className="flex flex-col gap-4">
      {/* Expiry Buckets */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        {expiryBuckets.map((bucket) => (
          <Card key={bucket.label}>
            <CardContent className="p-3 text-center">
              <Badge className={`${bucket.color} text-[10px] mb-1.5`}>{bucket.label}</Badge>
              <p className="text-xl font-bold text-foreground">{bucket.items.length}</p>
              <p className="text-[10px] text-muted-foreground">items</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold text-foreground">Expiry Timeline</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={bucketChartData} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
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
                />
                <Bar dataKey="count" name="Items" radius={[4, 4, 0, 0]}>
                  {bucketChartData.map((_, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Detailed table */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-sm font-semibold text-foreground">Items Expiring Within 90 Days</CardTitle>
          <Button
            size="sm"
            variant="outline"
            onClick={() => exportToCSV(
              [...expiredItems, ...expiringItems].map((i) => ({
                Name: i.name,
                SKU: i.sku,
                Category: i.category,
                Batch: i.batchNumber,
                ExpiryDate: i.expiryDate,
                DaysLeft: getDaysUntilExpiry(i.expiryDate) ?? "Expired",
                Quantity: i.quantity,
                Status: i.status,
              })),
              "expiry-report"
            )}
          >
            <Download className="size-4 mr-1.5" />
            Export
          </Button>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Item Name</TableHead>
                <TableHead>Batch</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Expiry Date</TableHead>
                <TableHead className="text-right">Days Left</TableHead>
                <TableHead className="text-right">Quantity</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {[...expiredItems, ...expiringItems]
                .sort((a, b) => {
                  const dA = getDaysUntilExpiry(a.expiryDate) ?? -999
                  const dB = getDaysUntilExpiry(b.expiryDate) ?? -999
                  return dA - dB
                })
                .map((item) => {
                  const days = getDaysUntilExpiry(item.expiryDate)
                  return (
                    <TableRow key={item.id}>
                      <TableCell className="font-medium text-foreground">{item.name}</TableCell>
                      <TableCell className="text-xs font-mono text-muted-foreground">{item.batchNumber}</TableCell>
                      <TableCell>
                        <Badge variant="outline" className="text-[10px]">{item.category}</Badge>
                      </TableCell>
                      <TableCell>{formatDate(item.expiryDate)}</TableCell>
                      <TableCell className={`text-right font-semibold ${
                        days === null ? "" : days < 0 ? "text-destructive" : days <= 7 ? "text-destructive" : days <= 30 ? "text-warning-foreground" : "text-primary"
                      }`}>
                        {days === null ? "N/A" : days < 0 ? "Expired" : `${days} days`}
                      </TableCell>
                      <TableCell className="text-right">{item.quantity} {item.unit}</TableCell>
                      <TableCell><StockStatusBadge status={item.status} /></TableCell>
                    </TableRow>
                  )
                })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}

// Department Report
function DepartmentReport({
  departments,
  getItemsByDepartment,
}: {
  departments: ReturnType<typeof useInventory>["state"]["departments"]
  getItemsByDepartment: ReturnType<typeof useInventory>["getItemsByDepartment"]
}) {
  const deptData = departments.map((dept) => {
    const deptItems = getItemsByDepartment(dept.id)
    const value = deptItems.reduce((sum, i) => sum + i.quantity * i.unitPrice, 0)
    return {
      name: dept.name,
      head: dept.head,
      items: deptItems.length,
      value,
      budget: dept.budget,
      spent: dept.spent,
      budgetUsed: Math.round((dept.spent / dept.budget) * 100),
      lowStock: deptItems.filter((i) => i.status === StockStatus.LowStock || i.status === StockStatus.OutOfStock).length,
    }
  })

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold text-foreground">Department Inventory Value</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={deptData} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} className="fill-muted-foreground" />
                <YAxis tick={{ fontSize: 11 }} className="fill-muted-foreground" tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "var(--color-card)",
                    border: "1px solid var(--color-border)",
                    borderRadius: "8px",
                    fontSize: "12px",
                    color: "var(--color-foreground)",
                  }}
                  formatter={(value: number, name: string) => {
                    if (name === "value") return [formatCurrency(value), "Inventory Value"]
                    return [formatCurrency(value), "Budget Spent"]
                  }}
                />
                <Bar dataKey="value" fill="var(--color-primary)" radius={[4, 4, 0, 0]} name="value" />
                <Bar dataKey="spent" fill="var(--color-chart-4)" radius={[4, 4, 0, 0]} name="spent" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-sm font-semibold text-foreground">Department Summary</CardTitle>
          <Button
            size="sm"
            variant="outline"
            onClick={() => exportToCSV(
              deptData.map((d) => ({
                Department: d.name,
                Head: d.head,
                Items: d.items,
                InventoryValue: d.value,
                Budget: d.budget,
                Spent: d.spent,
                BudgetUsed: `${d.budgetUsed}%`,
                LowStockItems: d.lowStock,
              })),
              "department-report"
            )}
          >
            <Download className="size-4 mr-1.5" />
            Export
          </Button>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Department</TableHead>
                <TableHead>Head</TableHead>
                <TableHead className="text-right">Items</TableHead>
                <TableHead className="text-right">Inventory Value</TableHead>
                <TableHead className="text-right">Budget</TableHead>
                <TableHead className="text-right">Spent</TableHead>
                <TableHead className="text-right">Budget Used</TableHead>
                <TableHead className="text-right">Low Stock</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {deptData.map((dept) => (
                <TableRow key={dept.name}>
                  <TableCell className="font-medium text-foreground">{dept.name}</TableCell>
                  <TableCell className="text-muted-foreground">{dept.head}</TableCell>
                  <TableCell className="text-right">{dept.items}</TableCell>
                  <TableCell className="text-right">{formatCurrency(dept.value)}</TableCell>
                  <TableCell className="text-right">{formatCurrency(dept.budget)}</TableCell>
                  <TableCell className="text-right">{formatCurrency(dept.spent)}</TableCell>
                  <TableCell className="text-right">
                    <Badge
                      variant="outline"
                      className={`text-[10px] ${
                        dept.budgetUsed > 85
                          ? "border-destructive/30 text-destructive"
                          : dept.budgetUsed > 70
                          ? "border-warning/30 text-warning-foreground"
                          : "border-success/30 text-success"
                      }`}
                    >
                      {dept.budgetUsed}%
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    {dept.lowStock > 0 ? (
                      <Badge variant="destructive" className="text-[10px]">{dept.lowStock}</Badge>
                    ) : (
                      <span className="text-muted-foreground text-xs">0</span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}

// Supplier Report
function SupplierReport({
  suppliers,
  purchaseOrders,
  getItemsBySupplier,
}: {
  suppliers: ReturnType<typeof useInventory>["state"]["suppliers"]
  purchaseOrders: ReturnType<typeof useInventory>["state"]["purchaseOrders"]
  getItemsBySupplier: ReturnType<typeof useInventory>["getItemsBySupplier"]
}) {
  const supplierData = suppliers.map((supplier) => {
    const supItems = getItemsBySupplier(supplier.id)
    const totalValue = supItems.reduce((sum, i) => sum + i.quantity * i.unitPrice, 0)
    const orderCount = purchaseOrders.filter((o) => o.supplierId === supplier.id).length
    const orderValue = purchaseOrders
      .filter((o) => o.supplierId === supplier.id)
      .reduce((sum, o) => sum + o.totalAmount, 0)

    return {
      ...supplier,
      totalItems: supItems.length,
      inventoryValue: totalValue,
      orderCount,
      orderValue,
    }
  })

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-sm font-semibold text-foreground">Supplier Performance</CardTitle>
          <Button
            size="sm"
            variant="outline"
            onClick={() => exportToCSV(
              supplierData.map((s) => ({
                Name: s.name,
                Contact: s.contact,
                Email: s.email,
                Rating: s.rating,
                ItemsSupplied: s.totalItems,
                InventoryValue: s.inventoryValue,
                Orders: s.orderCount,
                OrderValue: s.orderValue,
              })),
              "supplier-report"
            )}
          >
            <Download className="size-4 mr-1.5" />
            Export
          </Button>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Supplier</TableHead>
                <TableHead>Contact</TableHead>
                <TableHead className="text-right">Rating</TableHead>
                <TableHead className="text-right">Items</TableHead>
                <TableHead className="text-right">Inventory Value</TableHead>
                <TableHead className="text-right">Orders</TableHead>
                <TableHead className="text-right">Order Value</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {supplierData
                .sort((a, b) => b.inventoryValue - a.inventoryValue)
                .map((supplier) => (
                <TableRow key={supplier.id}>
                  <TableCell>
                    <div>
                      <p className="text-sm font-medium text-foreground">{supplier.name}</p>
                      <p className="text-[10px] text-muted-foreground">{supplier.email}</p>
                    </div>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">{supplier.contact}</TableCell>
                  <TableCell className="text-right">
                    <Badge
                      variant="outline"
                      className={`text-[10px] ${
                        supplier.rating >= 4.5
                          ? "border-success/30 text-success"
                          : supplier.rating >= 4.0
                          ? "border-primary/30 text-primary"
                          : "border-warning/30 text-warning-foreground"
                      }`}
                    >
                      {supplier.rating}/5
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">{supplier.totalItems}</TableCell>
                  <TableCell className="text-right font-medium">{formatCurrency(supplier.inventoryValue)}</TableCell>
                  <TableCell className="text-right">{supplier.orderCount}</TableCell>
                  <TableCell className="text-right font-medium">{formatCurrency(supplier.orderValue)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}

// Valuation Report
function ValuationReport({
  items,
  getItemsByCategory,
}: {
  items: ReturnType<typeof useInventory>["state"]["items"]
  getItemsByCategory: ReturnType<typeof useInventory>["getItemsByCategory"]
}) {
  const totalValue = items.reduce((sum, i) => sum + i.quantity * i.unitPrice, 0)

  // Top 10 most valuable items
  const topItems = [...items]
    .map((i) => ({ ...i, totalValue: i.quantity * i.unitPrice }))
    .sort((a, b) => b.totalValue - a.totalValue)
    .slice(0, 10)

  const categoryValues = Object.values(Category).map((cat) => {
    const catItems = getItemsByCategory(cat)
    return {
      name: cat,
      value: catItems.reduce((sum, i) => sum + i.quantity * i.unitPrice, 0),
    }
  }).sort((a, b) => b.value - a.value)

  const COLORS = [
    "var(--color-chart-1)",
    "var(--color-chart-2)",
    "var(--color-chart-3)",
    "var(--color-chart-4)",
    "var(--color-chart-5)",
    "var(--color-primary)",
  ]

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card>
          <CardContent className="p-4 text-center">
            <DollarSign className="size-8 mx-auto text-primary mb-2" />
            <p className="text-xs text-muted-foreground">Total Inventory Value</p>
            <p className="text-2xl font-bold text-foreground mt-1">{formatCurrency(totalValue)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <Package className="size-8 mx-auto text-primary mb-2" />
            <p className="text-xs text-muted-foreground">Avg Value per Item Type</p>
            <p className="text-2xl font-bold text-foreground mt-1">{formatCurrency(totalValue / items.length)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <PieChartIcon className="size-8 mx-auto text-primary mb-2" />
            <p className="text-xs text-muted-foreground">Most Valuable Category</p>
            <p className="text-lg font-bold text-foreground mt-1">{categoryValues[0]?.name}</p>
            <p className="text-xs text-muted-foreground">{formatCurrency(categoryValues[0]?.value ?? 0)}</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-foreground">Value Distribution by Category</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-72 flex items-center">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={categoryValues}
                    cx="50%"
                    cy="50%"
                    outerRadius={95}
                    dataKey="value"
                    label={({ name, percent }) => `${name.length > 10 ? name.slice(0, 10) + "..." : name} (${(percent * 100).toFixed(0)}%)`}
                  >
                    {categoryValues.map((_, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
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
                    formatter={(value: number) => [formatCurrency(value), "Value"]}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-semibold text-foreground">Top 10 Most Valuable Items</CardTitle>
            <Button
              size="sm"
              variant="outline"
              onClick={() => exportToCSV(
                topItems.map((i) => ({
                  Name: i.name,
                  SKU: i.sku,
                  Category: i.category,
                  Quantity: i.quantity,
                  UnitPrice: i.unitPrice,
                  TotalValue: i.totalValue,
                })),
                "top-value-items"
              )}
            >
              <Download className="size-4 mr-1.5" />
              Export
            </Button>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col gap-2.5 max-h-72 overflow-y-auto">
              {topItems.map((item, index) => (
                <div
                  key={item.id}
                  className="flex items-center gap-3 rounded-lg border border-border p-2.5"
                >
                  <span className="flex size-6 items-center justify-center rounded-md bg-primary/10 text-[10px] font-bold text-primary shrink-0">
                    {index + 1}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-foreground truncate">{item.name}</p>
                    <p className="text-[10px] text-muted-foreground">
                      {item.quantity} {item.unit} x {formatCurrency(item.unitPrice)}
                    </p>
                  </div>
                  <span className="text-sm font-bold text-foreground shrink-0">
                    {formatCurrency(item.totalValue)}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
