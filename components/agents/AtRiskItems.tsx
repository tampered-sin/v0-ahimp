"use client"

import { useMemo, useState } from "react"
import { Search, ShieldAlert, SlidersHorizontal } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type { SupplyChainDecision, SupplyChainRequestPayload, SupplyChainResponse } from "@/lib/ml-api"

interface AtRiskItemsProps {
  data: SupplyChainResponse | null
  loading: boolean
  params: SupplyChainRequestPayload
  onAnalyze: (params: SupplyChainRequestPayload) => Promise<void>
}

export function AtRiskItems({ data, loading, params, onAnalyze }: AtRiskItemsProps) {
  const [search, setSearch] = useState("")
  const [threshold, setThreshold] = useState(params.risk_threshold)
  const [maxItems, setMaxItems] = useState(params.max_items)
  const [cadenceHours, setCadenceHours] = useState(params.cadence_hours)
  const [selectedItemId, setSelectedItemId] = useState<number | null>(null)

  const decisions = useMemo(() => data?.result?.decisions ?? [], [data?.result?.decisions])
  const filtered = useMemo(() => {
    return decisions.filter((row) => {
      if (!search) return true
      const q = search.toLowerCase()
      return (
        row.item_name.toLowerCase().includes(q) ||
        String(row.item_id).includes(q) ||
        row.recommended_supplier.supplier_name.toLowerCase().includes(q)
      )
    })
  }, [decisions, search])

  const selected = useMemo(() => {
    if (!selectedItemId) return filtered[0] ?? null
    return filtered.find((row) => row.item_id === selectedItemId) ?? filtered[0] ?? null
  }, [filtered, selectedItemId])

  async function runAnalysis() {
    const next: SupplyChainRequestPayload = {
      risk_threshold: Number(threshold),
      max_items: Number(maxItems),
      cadence_hours: Number(cadenceHours),
      supplier_overrides: {},
    }
    await onAnalyze(next)
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <ShieldAlert className="size-4" />
          At-Risk Items
          {loading && <Badge variant="secondary">Analyzing...</Badge>}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="grid grid-cols-1 gap-3 rounded-lg border border-border p-3 md:grid-cols-4">
          <div className="space-y-1.5">
            <Label className="text-xs">Risk Threshold</Label>
            <Input
              type="number"
              min={0}
              max={1}
              step={0.05}
              value={threshold}
              onChange={(event) => setThreshold(Number(event.target.value))}
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">Max Items</Label>
            <Input
              type="number"
              min={1}
              max={200}
              value={maxItems}
              onChange={(event) => setMaxItems(Number(event.target.value))}
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">Cadence (hours)</Label>
            <Input
              type="number"
              min={1}
              max={24}
              value={cadenceHours}
              onChange={(event) => setCadenceHours(Number(event.target.value))}
            />
          </div>
          <div className="flex items-end">
            <Button className="w-full" onClick={() => void runAnalysis()}>
              <SlidersHorizontal className="mr-2 size-4" />
              Run Analysis
            </Button>
          </div>
        </div>

        <div className="relative max-w-sm">
          <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search at-risk decisions..."
            className="pl-8"
          />
        </div>

        <div className="rounded-lg border border-border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Item</TableHead>
                <TableHead>Risk</TableHead>
                <TableHead>Supplier</TableHead>
                <TableHead>Score</TableHead>
                <TableHead className="text-right">Qty</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="h-16 text-center text-sm text-muted-foreground">
                    No items matched this filter.
                  </TableCell>
                </TableRow>
              ) : (
                filtered.map((decision) => (
                  <TableRow
                    key={decision.item_id}
                    className="cursor-pointer"
                    data-state={selected?.item_id === decision.item_id ? "selected" : undefined}
                    onClick={() => setSelectedItemId(decision.item_id)}
                  >
                    <TableCell>
                      <div className="flex flex-col">
                        <span className="font-medium">{decision.item_name}</span>
                        <span className="text-xs text-muted-foreground">#{decision.item_id}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant={decision.risk_prob >= 0.9 ? "destructive" : "secondary"}>
                        {(decision.risk_prob * 100).toFixed(1)}%
                      </Badge>
                    </TableCell>
                    <TableCell>{decision.recommended_supplier.supplier_name}</TableCell>
                    <TableCell>{decision.recommended_supplier.score.toFixed(2)}</TableCell>
                    <TableCell className="text-right">{decision.recommended_order_qty}</TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>

        {selected && <DecisionDetails decision={selected} />}
      </CardContent>
    </Card>
  )
}

function DecisionDetails({ decision }: { decision: SupplyChainDecision }) {
  const breakdown = decision.recommended_supplier.breakdown ?? {}

  return (
    <div className="rounded-lg border border-border bg-muted/20 p-4">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h4 className="text-sm font-semibold">Drill-down: {decision.item_name}</h4>
        <Badge variant="outline">Supplier #{decision.recommended_supplier.supplier_id}</Badge>
      </div>
      <p className="text-xs text-muted-foreground">{decision.reason}</p>
      <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
        <div className="rounded-md border border-border bg-background p-3 text-sm">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Suggested Supplier</p>
          <p className="font-medium">{decision.recommended_supplier.supplier_name}</p>
          <p className="text-xs text-muted-foreground">Score: {decision.recommended_supplier.score.toFixed(2)}</p>
        </div>
        <div className="rounded-md border border-border bg-background p-3 text-sm">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Suggested Quantity</p>
          <p className="font-medium">{decision.recommended_order_qty} units</p>
          <p className="text-xs text-muted-foreground">Risk: {(decision.risk_prob * 100).toFixed(1)}%</p>
        </div>
      </div>
      {Object.keys(breakdown).length > 0 && (
        <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-3">
          {Object.entries(breakdown).map(([key, value]) => (
            <div key={key} className="rounded-md border border-border bg-background px-2 py-1.5 text-xs">
              <p className="text-muted-foreground">{key.replaceAll("_", " ")}</p>
              <p className="font-semibold">{Number(value).toFixed(3)}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
