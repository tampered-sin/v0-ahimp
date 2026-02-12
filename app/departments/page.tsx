"use client"

import { DashboardLayout } from "@/components/dashboard-layout"
import { useInventory } from "@/lib/inventory-context"
import { formatCurrency } from "@/lib/utils"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { StockStatusBadge } from "@/components/stock-status-badge"
import { Building2, Package, DollarSign, Users } from "lucide-react"
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts"

export default function DepartmentsPage() {
  return (
    <DashboardLayout title="Department Tracking">
      <DepartmentsContent />
    </DashboardLayout>
  )
}

function DepartmentsContent() {
  const { state, getItemsByDepartment } = useInventory()
  const { departments } = state

  const deptData = departments.map((dept) => {
    const items = getItemsByDepartment(dept.id)
    const totalValue = items.reduce((sum, i) => sum + i.quantity * i.unitPrice, 0)
    const utilization = dept.budget > 0 ? (dept.spent / dept.budget) * 100 : 0
    return {
      ...dept,
      items,
      itemCount: items.length,
      totalValue,
      utilization,
    }
  })

  const chartData = deptData.map((d) => ({
    name: d.name,
    budget: d.budget,
    spent: d.spent,
  }))

  return (
    <div className="flex flex-col gap-6">
      {/* Budget Overview Chart */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold text-foreground">Department Budget Overview</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} className="fill-muted-foreground" />
                <YAxis tick={{ fontSize: 11 }} className="fill-muted-foreground" tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
                <Tooltip
                  contentStyle={{ backgroundColor: "var(--color-card)", border: "1px solid var(--color-border)", borderRadius: "8px", fontSize: "12px", color: "var(--color-foreground)" }}
                  formatter={(value: number, name: string) => [formatCurrency(value), name === "budget" ? "Budget" : "Spent"]}
                />
                <Bar dataKey="budget" fill="var(--color-primary)" radius={[4, 4, 0, 0]} opacity={0.3} name="budget" />
                <Bar dataKey="spent" fill="var(--color-primary)" radius={[4, 4, 0, 0]} name="spent" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Department Cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {deptData.map((dept) => (
          <Card key={dept.id}>
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2">
                  <div className="flex size-8 items-center justify-center rounded-lg bg-primary/10">
                    <Building2 className="size-4 text-primary" />
                  </div>
                  <div>
                    <CardTitle className="text-sm font-semibold text-foreground">{dept.name}</CardTitle>
                    <div className="flex items-center gap-1 text-[11px] text-muted-foreground">
                      <Users className="size-3" />
                      {dept.head}
                    </div>
                  </div>
                </div>
                <Badge variant="outline" className="text-[10px] gap-1">
                  <Package className="size-3" />{dept.itemCount}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <div className="flex flex-col gap-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Budget Utilization</span>
                  <span className={`font-semibold ${dept.utilization > 90 ? "text-destructive" : dept.utilization > 70 ? "text-warning-foreground" : "text-success"}`}>
                    {Math.round(dept.utilization)}%
                  </span>
                </div>
                <Progress value={dept.utilization} className="h-2" />
                <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                  <span>{formatCurrency(dept.spent)} spent</span>
                  <span>{formatCurrency(dept.budget)} budget</span>
                </div>
              </div>
              <div className="flex items-center gap-2 pt-1 border-t border-border">
                <div className="flex items-center gap-1 text-xs text-muted-foreground">
                  <DollarSign className="size-3" />
                  <span>Inventory Value: <span className="font-semibold text-foreground">{formatCurrency(dept.totalValue)}</span></span>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Department Items Breakdown */}
      {deptData.map((dept) => (
        <Card key={`items-${dept.id}`}>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-foreground">{dept.name} - Allocated Items ({dept.itemCount})</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-xs">Item</TableHead>
                  <TableHead className="text-xs">Category</TableHead>
                  <TableHead className="text-xs">Quantity</TableHead>
                  <TableHead className="text-xs">Status</TableHead>
                  <TableHead className="text-xs text-right">Value</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {dept.items.slice(0, 5).map((item) => (
                  <TableRow key={item.id}>
                    <TableCell className="text-sm font-medium text-foreground">{item.name}</TableCell>
                    <TableCell><Badge variant="outline" className="text-[10px]">{item.category}</Badge></TableCell>
                    <TableCell className="text-sm text-foreground">{item.quantity.toLocaleString()} {item.unit}</TableCell>
                    <TableCell><StockStatusBadge status={item.status} /></TableCell>
                    <TableCell className="text-right text-xs font-mono text-foreground">{formatCurrency(item.quantity * item.unitPrice)}</TableCell>
                  </TableRow>
                ))}
                {dept.items.length > 5 && (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center text-xs text-muted-foreground py-2">
                      +{dept.items.length - 5} more items
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
