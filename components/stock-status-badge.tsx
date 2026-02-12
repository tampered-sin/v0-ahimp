import { Badge } from "@/components/ui/badge"
import { StockStatus, OrderStatus, AlertSeverity } from "@/lib/types"
import { cn } from "@/lib/utils"

export function StockStatusBadge({ status }: { status: StockStatus }) {
  const styles: Record<StockStatus, string> = {
    [StockStatus.InStock]: "bg-success/15 text-success border-success/30 hover:bg-success/20",
    [StockStatus.LowStock]: "bg-warning/15 text-warning-foreground border-warning/30 hover:bg-warning/20",
    [StockStatus.OutOfStock]: "bg-destructive/15 text-destructive border-destructive/30 hover:bg-destructive/20",
    [StockStatus.Expired]: "bg-destructive/15 text-destructive border-destructive/30 hover:bg-destructive/20",
  }

  return (
    <Badge variant="outline" className={cn("text-[11px] font-medium", styles[status])}>
      {status}
    </Badge>
  )
}

export function OrderStatusBadge({ status }: { status: OrderStatus }) {
  const styles: Record<OrderStatus, string> = {
    [OrderStatus.Pending]: "bg-warning/15 text-warning-foreground border-warning/30",
    [OrderStatus.Approved]: "bg-primary/15 text-primary border-primary/30",
    [OrderStatus.Shipped]: "bg-chart-5/15 text-chart-5 border-chart-5/30",
    [OrderStatus.Delivered]: "bg-success/15 text-success border-success/30",
    [OrderStatus.Cancelled]: "bg-destructive/15 text-destructive border-destructive/30",
  }

  return (
    <Badge variant="outline" className={cn("text-[11px] font-medium", styles[status])}>
      {status}
    </Badge>
  )
}

export function SeverityBadge({ severity }: { severity: AlertSeverity }) {
  const styles: Record<AlertSeverity, string> = {
    [AlertSeverity.Critical]: "bg-destructive/15 text-destructive border-destructive/30",
    [AlertSeverity.Warning]: "bg-warning/15 text-warning-foreground border-warning/30",
    [AlertSeverity.Info]: "bg-primary/15 text-primary border-primary/30",
  }

  return (
    <Badge variant="outline" className={cn("text-[11px] font-medium", styles[severity])}>
      {severity}
    </Badge>
  )
}
