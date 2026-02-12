"use client"

import { useState, useMemo } from "react"
import { DashboardLayout } from "@/components/dashboard-layout"
import { SeverityBadge } from "@/components/stock-status-badge"
import { useInventory } from "@/lib/inventory-context"
import { formatDateTime, getDaysUntilExpiry, getAlertSeverityColor } from "@/lib/utils"
import { AlertType, AlertSeverity, StockStatus, type Alert } from "@/lib/types"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  AlertTriangle,
  Bell,
  BellOff,
  CheckCircle2,
  Clock,
  Filter,
  Package,
  Search,
  ShieldAlert,
  Trash2,
  XCircle,
} from "lucide-react"

export default function AlertsPage() {
  return (
    <DashboardLayout title="Alerts & Notifications">
      <AlertsContent />
    </DashboardLayout>
  )
}

function AlertsContent() {
  const {
    state,
    dispatch,
    getItemById,
    getLowStockItems,
    getExpiringItems,
    getExpiredItems,
    getUnacknowledgedAlerts,
  } = useInventory()
  const { alerts, items } = state

  const [searchQuery, setSearchQuery] = useState("")
  const [severityFilter, setSeverityFilter] = useState<string>("all")
  const [typeFilter, setTypeFilter] = useState<string>("all")

  // Stats
  const unacknowledgedCount = getUnacknowledgedAlerts().length
  const criticalCount = alerts.filter((a) => a.severity === AlertSeverity.Critical && !a.acknowledged).length
  const warningCount = alerts.filter((a) => a.severity === AlertSeverity.Warning && !a.acknowledged).length
  const lowStockItems = getLowStockItems()
  const expiringItems = getExpiringItems(30)
  const expiredItems = getExpiredItems()

  // Filter alerts
  const filteredAlerts = useMemo(() => {
    return alerts.filter((alert) => {
      const matchesSearch = alert.message.toLowerCase().includes(searchQuery.toLowerCase())
      const matchesSeverity = severityFilter === "all" || alert.severity === severityFilter
      const matchesType = typeFilter === "all" || alert.type === typeFilter
      return matchesSearch && matchesSeverity && matchesType
    })
  }, [alerts, searchQuery, severityFilter, typeFilter])

  const activeAlerts = filteredAlerts.filter((a) => !a.acknowledged)
  const acknowledgedAlerts = filteredAlerts.filter((a) => a.acknowledged)

  const handleAcknowledge = (alertId: string) => {
    dispatch({ type: "ACKNOWLEDGE_ALERT", payload: alertId })
  }

  const handleAcknowledgeAll = () => {
    activeAlerts.forEach((alert) => {
      dispatch({ type: "ACKNOWLEDGE_ALERT", payload: alert.id })
    })
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="border-destructive/20">
          <CardContent className="flex items-center gap-4 p-4">
            <div className="flex size-10 items-center justify-center rounded-lg bg-destructive/10">
              <ShieldAlert className="size-5 text-destructive" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">{criticalCount}</p>
              <p className="text-xs text-muted-foreground">Critical Alerts</p>
            </div>
          </CardContent>
        </Card>
        <Card className="border-warning/20">
          <CardContent className="flex items-center gap-4 p-4">
            <div className="flex size-10 items-center justify-center rounded-lg bg-warning/10">
              <AlertTriangle className="size-5 text-warning-foreground" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">{warningCount}</p>
              <p className="text-xs text-muted-foreground">Warnings</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-4 p-4">
            <div className="flex size-10 items-center justify-center rounded-lg bg-primary/10">
              <Bell className="size-5 text-primary" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">{unacknowledgedCount}</p>
              <p className="text-xs text-muted-foreground">Unacknowledged</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-4 p-4">
            <div className="flex size-10 items-center justify-center rounded-lg bg-muted">
              <BellOff className="size-5 text-muted-foreground" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">{alerts.filter((a) => a.acknowledged).length}</p>
              <p className="text-xs text-muted-foreground">Acknowledged</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Auto-detected Issues */}
      {(lowStockItems.length > 0 || expiringItems.length > 0 || expiredItems.length > 0) && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold text-foreground flex items-center gap-2">
              <Package className="size-4" />
              Auto-Detected Inventory Issues
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              {/* Low Stock */}
              <div className="rounded-lg border border-warning/30 bg-warning/5 p-3">
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle className="size-4 text-warning-foreground" />
                  <span className="text-xs font-semibold text-foreground">Low Stock ({lowStockItems.length})</span>
                </div>
                <div className="flex flex-col gap-1.5 max-h-32 overflow-y-auto">
                  {lowStockItems.slice(0, 5).map((item) => (
                    <div key={item.id} className="flex items-center justify-between text-xs">
                      <span className="text-foreground truncate flex-1">{item.name}</span>
                      <span className="text-muted-foreground ml-2 shrink-0">
                        {item.quantity}/{item.reorderLevel} {item.unit}
                      </span>
                    </div>
                  ))}
                  {lowStockItems.length > 5 && (
                    <span className="text-[10px] text-muted-foreground">
                      +{lowStockItems.length - 5} more items
                    </span>
                  )}
                </div>
              </div>

              {/* Expiring Soon */}
              <div className="rounded-lg border border-primary/30 bg-primary/5 p-3">
                <div className="flex items-center gap-2 mb-2">
                  <Clock className="size-4 text-primary" />
                  <span className="text-xs font-semibold text-foreground">Expiring in 30 days ({expiringItems.length})</span>
                </div>
                <div className="flex flex-col gap-1.5 max-h-32 overflow-y-auto">
                  {expiringItems.slice(0, 5).map((item) => {
                    const days = getDaysUntilExpiry(item.expiryDate)
                    return (
                      <div key={item.id} className="flex items-center justify-between text-xs">
                        <span className="text-foreground truncate flex-1">{item.name}</span>
                        <span className="text-muted-foreground ml-2 shrink-0">
                          {days} days left
                        </span>
                      </div>
                    )
                  })}
                  {expiringItems.length > 5 && (
                    <span className="text-[10px] text-muted-foreground">
                      +{expiringItems.length - 5} more items
                    </span>
                  )}
                </div>
              </div>

              {/* Expired */}
              <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3">
                <div className="flex items-center gap-2 mb-2">
                  <XCircle className="size-4 text-destructive" />
                  <span className="text-xs font-semibold text-foreground">Expired ({expiredItems.length})</span>
                </div>
                <div className="flex flex-col gap-1.5 max-h-32 overflow-y-auto">
                  {expiredItems.slice(0, 5).map((item) => (
                    <div key={item.id} className="flex items-center justify-between text-xs">
                      <span className="text-foreground truncate flex-1">{item.name}</span>
                      <Badge variant="destructive" className="text-[9px] h-4 px-1.5">{item.quantity} {item.unit}</Badge>
                    </div>
                  ))}
                  {expiredItems.length > 5 && (
                    <span className="text-[10px] text-muted-foreground">
                      +{expiredItems.length - 5} more items
                    </span>
                  )}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Filters */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-1 items-center gap-3">
          <div className="relative flex-1 max-w-xs">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search alerts..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>
          <Select value={severityFilter} onValueChange={setSeverityFilter}>
            <SelectTrigger className="w-[140px]">
              <Filter className="size-4 mr-2 text-muted-foreground" />
              <SelectValue placeholder="Severity" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Severity</SelectItem>
              <SelectItem value={AlertSeverity.Critical}>Critical</SelectItem>
              <SelectItem value={AlertSeverity.Warning}>Warning</SelectItem>
              <SelectItem value={AlertSeverity.Info}>Info</SelectItem>
            </SelectContent>
          </Select>
          <Select value={typeFilter} onValueChange={setTypeFilter}>
            <SelectTrigger className="w-[160px]">
              <SelectValue placeholder="Type" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Types</SelectItem>
              <SelectItem value={AlertType.LowStock}>Low Stock</SelectItem>
              <SelectItem value={AlertType.ExpiringSoon}>Expiring Soon</SelectItem>
              <SelectItem value={AlertType.Expired}>Expired</SelectItem>
              <SelectItem value={AlertType.OrderUpdate}>Order Update</SelectItem>
            </SelectContent>
          </Select>
        </div>
        {activeAlerts.length > 0 && (
          <Button
            size="sm"
            variant="outline"
            onClick={handleAcknowledgeAll}
            className="shrink-0"
          >
            <CheckCircle2 className="size-4 mr-2" />
            Acknowledge All ({activeAlerts.length})
          </Button>
        )}
      </div>

      {/* Alerts Tabs */}
      <Tabs defaultValue="active" className="w-full">
        <TabsList>
          <TabsTrigger value="active" className="gap-2">
            Active
            {activeAlerts.length > 0 && (
              <Badge variant="destructive" className="text-[9px] h-4 px-1.5 rounded-full">
                {activeAlerts.length}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="acknowledged" className="gap-2">
            Acknowledged
            <Badge variant="secondary" className="text-[9px] h-4 px-1.5 rounded-full">
              {acknowledgedAlerts.length}
            </Badge>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="active" className="mt-4">
          {activeAlerts.length === 0 ? (
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-12">
                <CheckCircle2 className="size-12 text-success mb-3" />
                <p className="text-sm font-medium text-foreground">All Clear</p>
                <p className="text-xs text-muted-foreground mt-1">No active alerts at this time.</p>
              </CardContent>
            </Card>
          ) : (
            <div className="flex flex-col gap-3">
              {activeAlerts.map((alert) => (
                <AlertCard
                  key={alert.id}
                  alert={alert}
                  onAcknowledge={handleAcknowledge}
                  itemName={alert.itemId ? getItemById(alert.itemId)?.name : undefined}
                />
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="acknowledged" className="mt-4">
          {acknowledgedAlerts.length === 0 ? (
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-12">
                <BellOff className="size-12 text-muted-foreground mb-3" />
                <p className="text-sm font-medium text-foreground">No Acknowledged Alerts</p>
                <p className="text-xs text-muted-foreground mt-1">Acknowledged alerts will appear here.</p>
              </CardContent>
            </Card>
          ) : (
            <div className="flex flex-col gap-3">
              {acknowledgedAlerts.map((alert) => (
                <AlertCard
                  key={alert.id}
                  alert={alert}
                  itemName={alert.itemId ? getItemById(alert.itemId)?.name : undefined}
                />
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}

interface AlertCardProps {
  alert: Alert
  onAcknowledge?: (id: string) => void
  itemName?: string
}

function AlertCard({ alert, onAcknowledge, itemName }: AlertCardProps) {
  const getAlertIcon = () => {
    switch (alert.type) {
      case AlertType.LowStock:
        return <AlertTriangle className="size-4" />
      case AlertType.ExpiringSoon:
        return <Clock className="size-4" />
      case AlertType.Expired:
        return <XCircle className="size-4" />
      case AlertType.OrderUpdate:
        return <Package className="size-4" />
      default:
        return <Bell className="size-4" />
    }
  }

  return (
    <Card className={`transition-colors ${!alert.acknowledged ? "border-l-4" : "opacity-70"} ${
      alert.severity === AlertSeverity.Critical
        ? "border-l-destructive"
        : alert.severity === AlertSeverity.Warning
        ? "border-l-warning"
        : "border-l-primary"
    }`}>
      <CardContent className="flex items-start gap-4 p-4">
        <div className={`flex size-9 shrink-0 items-center justify-center rounded-lg ${getAlertSeverityColor(alert.severity)}`}>
          {getAlertIcon()}
        </div>
        <div className="flex flex-1 flex-col gap-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <SeverityBadge severity={alert.severity} />
            <Badge variant="outline" className="text-[10px] h-5">
              {alert.type}
            </Badge>
            {alert.acknowledged && (
              <Badge variant="secondary" className="text-[10px] h-5">
                <CheckCircle2 className="size-3 mr-1" />
                Acknowledged
              </Badge>
            )}
          </div>
          <p className="text-sm text-foreground leading-relaxed">{alert.message}</p>
          {itemName && (
            <p className="text-xs text-muted-foreground">
              Related item: <span className="font-medium text-foreground">{itemName}</span>
            </p>
          )}
          <p className="text-[10px] text-muted-foreground mt-0.5">
            {formatDateTime(alert.timestamp)}
          </p>
        </div>
        {!alert.acknowledged && onAcknowledge && (
          <Button
            size="sm"
            variant="outline"
            onClick={() => onAcknowledge(alert.id)}
            className="shrink-0"
          >
            <CheckCircle2 className="size-4 mr-1.5" />
            Acknowledge
          </Button>
        )}
      </CardContent>
    </Card>
  )
}
