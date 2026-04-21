"use client"

import { useMemo, useState } from "react"
import { ClipboardList, Loader2, Truck } from "lucide-react"
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
import type { AgentLogRecord, SupplyChainDecision, SupplyChainRequestPayload, SupplyChainResponse } from "@/lib/ml-api"

type ActionResult = {
  ok: boolean
  message: string
}

interface POTrackerProps {
  latestOptimize: SupplyChainResponse | null
  logs: AgentLogRecord[]
  isOptimizing: boolean
  onOptimize: (payload: SupplyChainRequestPayload) => Promise<ActionResult>
}

type PurchaseOrderView = {
  po_id: number
  item_name: string
  supplier_name: string
  status: string
  expected_delivery: string | null
  dispatch_channel: string | null
  dispatch_status: string | null
  tracking_status: string | null
}

function parseOptimizeDecisions(log: AgentLogRecord): SupplyChainDecision[] {
  const topResult = log.result as { result?: unknown } | null
  const wrapped = topResult?.result as { result?: unknown } | undefined
  const inner = wrapped?.result as { decisions?: SupplyChainDecision[] } | undefined
  return inner?.decisions ?? []
}

function extractPOs(decisions: SupplyChainDecision[]): PurchaseOrderView[] {
  return decisions
    .filter((decision) => Boolean(decision.created_po))
    .map((decision) => ({
      po_id: decision.created_po?.po_id ?? 0,
      item_name: decision.item_name,
      supplier_name: decision.recommended_supplier.supplier_name,
      status: decision.created_po?.status ?? "UNKNOWN",
      expected_delivery: decision.created_po?.expected_delivery ?? null,
      dispatch_channel: (decision.dispatch as { channel?: string } | null)?.channel ?? null,
      dispatch_status: (decision.dispatch as { status?: string } | null)?.status ?? null,
      tracking_status: decision.tracking?.status ?? null,
    }))
}

export function POTracker({ latestOptimize, logs, isOptimizing, onOptimize }: POTrackerProps) {
  const [riskThreshold, setRiskThreshold] = useState(0.7)
  const [maxItems, setMaxItems] = useState(10)
  const [cadenceHours, setCadenceHours] = useState(1)
  const [feedback, setFeedback] = useState<string | null>(null)
  const [selectedPoId, setSelectedPoId] = useState<number | null>(null)

  const poRows = useMemo(() => {
    const fromLatest = latestOptimize ? extractPOs(latestOptimize.result.decisions) : []

    const fromLogs = logs
      .filter((row) => row.task_description === "supply_chain_optimize")
      .flatMap((row) => extractPOs(parseOptimizeDecisions(row)))

    const merged = [...fromLatest, ...fromLogs]
    const byId = new Map<number, PurchaseOrderView>()
    merged.forEach((row) => {
      if (!row.po_id) return
      byId.set(row.po_id, row)
    })

    return [...byId.values()].sort((left, right) => right.po_id - left.po_id)
  }, [latestOptimize, logs])

  const selected = useMemo(() => {
    if (!selectedPoId) return poRows[0] ?? null
    return poRows.find((row) => row.po_id === selectedPoId) ?? poRows[0] ?? null
  }, [poRows, selectedPoId])

  async function handleOptimize() {
    const result = await onOptimize({
      risk_threshold: riskThreshold,
      max_items: maxItems,
      cadence_hours: cadenceHours,
      supplier_overrides: {},
    })
    setFeedback(result.message)
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Truck className="size-4" />
          PO Tracker
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="grid grid-cols-1 gap-3 rounded-lg border border-border p-3 md:grid-cols-4">
          <div className="space-y-1.5">
            <Label className="text-xs">Risk Threshold</Label>
            <Input type="number" min={0} max={1} step={0.05} value={riskThreshold} onChange={(event) => setRiskThreshold(Number(event.target.value))} />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">Max Items</Label>
            <Input type="number" min={1} max={200} value={maxItems} onChange={(event) => setMaxItems(Number(event.target.value))} />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">Cadence (hours)</Label>
            <Input type="number" min={1} max={24} value={cadenceHours} onChange={(event) => setCadenceHours(Number(event.target.value))} />
          </div>
          <div className="flex items-end">
            <Button className="w-full" onClick={() => void handleOptimize()} disabled={isOptimizing}>
              {isOptimizing ? <Loader2 className="mr-2 size-4 animate-spin" /> : <ClipboardList className="mr-2 size-4" />}
              Run Auto-Optimize
            </Button>
          </div>
          {feedback && <p className="text-xs text-muted-foreground md:col-span-4">{feedback}</p>}
        </div>

        <div className="rounded-lg border border-border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>PO ID</TableHead>
                <TableHead>Item</TableHead>
                <TableHead>Supplier</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Delivery ETA</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {poRows.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="h-16 text-center text-sm text-muted-foreground">
                    No auto-generated POs yet. Trigger optimization to create and track POs.
                  </TableCell>
                </TableRow>
              ) : (
                poRows.map((po) => (
                  <TableRow
                    key={po.po_id}
                    className="cursor-pointer"
                    data-state={selected?.po_id === po.po_id ? "selected" : undefined}
                    onClick={() => setSelectedPoId(po.po_id)}
                  >
                    <TableCell className="font-mono text-xs">PO-{po.po_id}</TableCell>
                    <TableCell>{po.item_name}</TableCell>
                    <TableCell>{po.supplier_name}</TableCell>
                    <TableCell>
                      <Badge variant={po.status === "AUTO_CREATED" ? "secondary" : "outline"}>{po.status}</Badge>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {po.expected_delivery ? new Date(po.expected_delivery).toLocaleDateString() : "-"}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>

        {selected && (
          <div className="rounded-lg border border-border bg-muted/20 p-3 text-sm">
            <h4 className="font-semibold">Drill-down: PO-{selected.po_id}</h4>
            <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-3">
              <InfoChip label="Dispatch Channel" value={selected.dispatch_channel ?? "-"} />
              <InfoChip label="Dispatch Status" value={selected.dispatch_status ?? "-"} />
              <InfoChip label="Tracking Status" value={selected.tracking_status ?? "-"} />
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function InfoChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-background px-2 py-1.5">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-sm font-medium">{value}</p>
    </div>
  )
}
