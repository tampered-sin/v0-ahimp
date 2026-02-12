"use client"

import { use } from "react"
import { useRouter } from "next/navigation"
import { DashboardLayout } from "@/components/dashboard-layout"
import { StockStatusBadge } from "@/components/stock-status-badge"
import { useInventory } from "@/lib/inventory-context"
import { formatCurrency, formatDate, getDaysUntilExpiry, cn } from "@/lib/utils"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Progress } from "@/components/ui/progress"
import {
  ArrowLeft,
  Package,
  MapPin,
  Calendar,
  Truck,
  Building2,
  Hash,
  DollarSign,
  AlertTriangle,
} from "lucide-react"
import Link from "next/link"

export default function ItemDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  return (
    <DashboardLayout title="Item Details">
      <ItemDetailContent itemId={id} />
    </DashboardLayout>
  )
}

function ItemDetailContent({ itemId }: { itemId: string }) {
  const router = useRouter()
  const { getItemById, getSupplierById, getDepartmentById, state } = useInventory()
  const item = getItemById(itemId)

  if (!item) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-20">
        <Package className="size-12 text-muted-foreground" />
        <h2 className="text-lg font-semibold text-foreground">Item Not Found</h2>
        <p className="text-sm text-muted-foreground">The item you are looking for does not exist.</p>
        <Button variant="outline" size="sm" asChild>
          <Link href="/inventory">Back to Inventory</Link>
        </Button>
      </div>
    )
  }

  const supplier = getSupplierById(item.supplierId)
  const department = getDepartmentById(item.departmentId)
  const daysUntilExpiry = getDaysUntilExpiry(item.expiryDate)
  const stockPercentage = item.reorderLevel > 0 ? Math.min((item.quantity / (item.reorderLevel * 3)) * 100, 100) : 100
  const totalValue = item.quantity * item.unitPrice

  // Related alerts
  const relatedAlerts = state.alerts.filter((a) => a.itemId === item.id)

  // Related orders
  const relatedOrders = state.purchaseOrders.filter((o) =>
    o.items.some((oi) => oi.itemId === item.id)
  )

  return (
    <div className="flex flex-col gap-6">
      {/* Back button */}
      <Button variant="ghost" size="sm" className="w-fit gap-1.5 -ml-2" onClick={() => router.back()}>
        <ArrowLeft className="size-4" />
        Back to Inventory
      </Button>

      {/* Header */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold text-foreground text-balance">{item.name}</h2>
            <StockStatusBadge status={item.status} />
          </div>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Badge variant="outline" className="text-[10px]">{item.category}</Badge>
            <span className="font-mono text-xs">{item.sku}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" asChild>
            <Link href="/inventory">View All Items</Link>
          </Button>
        </div>
      </div>

      {/* Detail Cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {/* Stock Info */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-sm font-semibold">
              <Package className="size-4 text-primary" />
              Stock Information
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="flex items-end justify-between">
              <div>
                <span className="text-3xl font-bold text-foreground">{item.quantity.toLocaleString()}</span>
                <span className="ml-1 text-sm text-muted-foreground">{item.unit}</span>
              </div>
              <div className="text-right">
                <p className="text-xs text-muted-foreground">Reorder Level</p>
                <p className="text-sm font-semibold text-foreground">{item.reorderLevel.toLocaleString()}</p>
              </div>
            </div>
            <div className="flex flex-col gap-1.5">
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">Stock Level</span>
                <span className={cn("font-medium", stockPercentage < 33 ? "text-destructive" : stockPercentage < 66 ? "text-warning-foreground" : "text-success")}>
                  {Math.round(stockPercentage)}%
                </span>
              </div>
              <Progress value={stockPercentage} className="h-2" />
            </div>
            <Separator />
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div>
                <p className="text-muted-foreground">Unit Price</p>
                <p className="font-semibold text-foreground">{formatCurrency(item.unitPrice)}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Total Value</p>
                <p className="font-semibold text-foreground">{formatCurrency(totalValue)}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Item Details */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-sm font-semibold">
              <Hash className="size-4 text-primary" />
              Item Details
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <DetailRow icon={MapPin} label="Location" value={item.location} />
            <DetailRow icon={Hash} label="Batch Number" value={item.batchNumber} mono />
            <DetailRow icon={Calendar} label="Last Restocked" value={formatDate(item.lastRestocked)} />
            <DetailRow
              icon={Calendar}
              label="Expiry Date"
              value={
                item.expiryDate === "N/A"
                  ? "N/A"
                  : `${formatDate(item.expiryDate)}${daysUntilExpiry !== null ? ` (${daysUntilExpiry <= 0 ? "EXPIRED" : `${daysUntilExpiry}d left`})` : ""}`
              }
              highlight={daysUntilExpiry !== null && daysUntilExpiry <= 30}
            />
            <DetailRow icon={Truck} label="Supplier" value={supplier?.name ?? "Unknown"} />
            <DetailRow icon={Building2} label="Department" value={department?.name ?? "Unknown"} />
            {item.notes && (
              <div className="mt-1 rounded-md bg-muted/50 p-2.5">
                <p className="text-[11px] text-muted-foreground leading-relaxed">{item.notes}</p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Alerts & Orders */}
        <div className="flex flex-col gap-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-sm font-semibold">
                <AlertTriangle className="size-4 text-destructive" />
                Related Alerts ({relatedAlerts.length})
              </CardTitle>
            </CardHeader>
            <CardContent>
              {relatedAlerts.length === 0 ? (
                <p className="text-xs text-muted-foreground">No active alerts for this item.</p>
              ) : (
                <div className="flex flex-col gap-2">
                  {relatedAlerts.slice(0, 4).map((alert) => (
                    <div key={alert.id} className="rounded-md border border-border p-2 text-xs">
                      <div className="flex items-center gap-2 mb-1">
                        <Badge
                          variant="outline"
                          className={cn(
                            "text-[10px]",
                            alert.severity === "Critical" ? "border-destructive/30 text-destructive" : "border-warning/30 text-warning-foreground"
                          )}
                        >
                          {alert.severity}
                        </Badge>
                      </div>
                      <p className="text-muted-foreground leading-relaxed">{alert.message}</p>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-sm font-semibold">
                <DollarSign className="size-4 text-primary" />
                Related Orders ({relatedOrders.length})
              </CardTitle>
            </CardHeader>
            <CardContent>
              {relatedOrders.length === 0 ? (
                <p className="text-xs text-muted-foreground">No purchase orders for this item.</p>
              ) : (
                <div className="flex flex-col gap-2">
                  {relatedOrders.map((order) => (
                    <Link
                      key={order.id}
                      href="/orders"
                      className="flex items-center justify-between rounded-md border border-border p-2 text-xs hover:bg-muted/50 transition-colors"
                    >
                      <div>
                        <span className="font-medium text-foreground">{order.id.toUpperCase()}</span>
                        <span className="ml-2 text-muted-foreground">{formatDate(order.orderDate)}</span>
                      </div>
                      <Badge variant="outline" className="text-[10px]">{order.status}</Badge>
                    </Link>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

function DetailRow({
  icon: Icon,
  label,
  value,
  mono,
  highlight,
}: {
  icon: React.ComponentType<{ className?: string }>
  label: string
  value: string
  mono?: boolean
  highlight?: boolean
}) {
  return (
    <div className="flex items-center gap-3">
      <Icon className="size-3.5 shrink-0 text-muted-foreground" />
      <div className="flex flex-1 items-center justify-between gap-2">
        <span className="text-xs text-muted-foreground">{label}</span>
        <span className={cn("text-xs font-medium text-foreground text-right", mono && "font-mono", highlight && "text-destructive")}>
          {value}
        </span>
      </div>
    </div>
  )
}
