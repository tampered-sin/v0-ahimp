import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
import { StockStatus, AlertSeverity } from './types'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: amount < 1 ? 2 : 0,
    maximumFractionDigits: 2,
  }).format(amount)
}

export function formatDate(dateString: string): string {
  if (dateString === "N/A") return "N/A"
  return new Date(dateString).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  })
}

export function formatDateTime(dateString: string): string {
  return new Date(dateString).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

export function getStockStatusColor(status: StockStatus): string {
  switch (status) {
    case StockStatus.InStock:
      return "bg-success/15 text-success border-success/30"
    case StockStatus.LowStock:
      return "bg-warning/15 text-warning-foreground border-warning/30"
    case StockStatus.OutOfStock:
      return "bg-destructive/15 text-destructive border-destructive/30"
    case StockStatus.Expired:
      return "bg-destructive/15 text-destructive border-destructive/30"
    default:
      return "bg-muted text-muted-foreground border-border"
  }
}

export function getAlertSeverityColor(severity: AlertSeverity): string {
  switch (severity) {
    case AlertSeverity.Critical:
      return "bg-destructive/15 text-destructive border-destructive/30"
    case AlertSeverity.Warning:
      return "bg-warning/15 text-warning-foreground border-warning/30"
    case AlertSeverity.Info:
      return "bg-primary/15 text-primary border-primary/30"
    default:
      return "bg-muted text-muted-foreground border-border"
  }
}

export function getDaysUntilExpiry(expiryDate: string): number | null {
  if (expiryDate === "N/A") return null
  const now = new Date()
  const expiry = new Date(expiryDate)
  const diff = expiry.getTime() - now.getTime()
  return Math.ceil(diff / (1000 * 60 * 60 * 24))
}

export function exportToCSV(data: Record<string, unknown>[], filename: string): void {
  if (data.length === 0) return
  const headers = Object.keys(data[0])
  const csvContent = [
    headers.join(","),
    ...data.map((row) =>
      headers
        .map((header) => {
          const cell = String(row[header] ?? "")
          return cell.includes(",") ? `"${cell}"` : cell
        })
        .join(",")
    ),
  ].join("\n")

  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" })
  const link = document.createElement("a")
  link.href = URL.createObjectURL(blob)
  link.setAttribute("download", `${filename}.csv`)
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}
