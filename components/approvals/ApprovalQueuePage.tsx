"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { CheckCircle2, Clock, RefreshCw, ShieldCheck, XCircle } from "lucide-react"
import {
  decideApprovalQueueItem,
  getApprovalQueue,
  getApprovalQueueDetail,
  processApprovalTimeouts,
  type ApprovalQueueDetailResponse,
  type ApprovalQueueItem,
} from "@/lib/ml-api"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useInventory } from "@/lib/inventory-context"

interface QueueFilters {
  status: string
  approval_level: string
  q: string
  limit: number
  offset: number
}

const DEFAULT_FILTERS: QueueFilters = {
  status: "",
  approval_level: "",
  q: "",
  limit: 20,
  offset: 0,
}

function formatDate(value: string | null) {
  if (!value) return "-"
  return new Date(value).toLocaleString()
}

function mapRoleToReviewerRole(role: string): "analyst" | "manager" | "admin" {
  const normalized = role.trim().toLowerCase()
  if (normalized === "admin") return "admin"
  if (normalized.includes("head") || normalized === "manager") return "manager"
  return "analyst"
}

export function ApprovalQueuePage() {
  const { state } = useInventory()
  const [filters, setFilters] = useState<QueueFilters>(DEFAULT_FILTERS)
  const [queue, setQueue] = useState<ApprovalQueueItem[]>([])
  const [count, setCount] = useState(0)
  const [selectedPoId, setSelectedPoId] = useState<number | null>(null)
  const [detail, setDetail] = useState<ApprovalQueueDetailResponse | null>(null)

  const [loading, setLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [isProcessingTimeouts, setIsProcessingTimeouts] = useState(false)
  const [feedback, setFeedback] = useState<string | null>(null)

  const [reviewedBy, setReviewedBy] = useState("")
  const [reviewerRole, setReviewerRole] = useState<"analyst" | "manager" | "admin">("analyst")
  const [comment, setComment] = useState("")

  useEffect(() => {
    const fallback = state.currentUser.name || state.currentUser.id || "system.user"
    setReviewedBy(state.currentUser.email || fallback)
    setReviewerRole(mapRoleToReviewerRole(state.currentUser.role))
  }, [state.currentUser])

  const loadQueue = useCallback(async (nextFilters: QueueFilters) => {
    setLoading(true)
    const response = await getApprovalQueue({
      status: nextFilters.status || undefined,
      approval_level: nextFilters.approval_level || undefined,
      q: nextFilters.q || undefined,
      limit: nextFilters.limit,
      offset: nextFilters.offset,
    })

    if (!response.ok || !response.data) {
      setFeedback(response.error ?? "Unable to load approval queue")
      setLoading(false)
      return
    }

    setQueue(response.data.items)
    setCount(response.data.count)
    if (!selectedPoId && response.data.items.length > 0) {
      setSelectedPoId(response.data.items[0].po_id)
    }
    setLoading(false)
  }, [selectedPoId])

  const loadDetail = useCallback(async (poId: number) => {
    setDetailLoading(true)
    const response = await getApprovalQueueDetail(poId)
    if (!response.ok || !response.data) {
      setFeedback(response.error ?? "Unable to load queue detail")
      setDetailLoading(false)
      return
    }
    setDetail(response.data)
    setDetailLoading(false)
  }, [])

  useEffect(() => {
    void loadQueue(filters)
  }, [filters, loadQueue])

  useEffect(() => {
    if (!selectedPoId) {
      setDetail(null)
      return
    }
    void loadDetail(selectedPoId)
  }, [loadDetail, selectedPoId])

  useEffect(() => {
    const interval = window.setInterval(() => {
      void loadQueue(filters)
      if (selectedPoId) {
        void loadDetail(selectedPoId)
      }
    }, 30000)

    return () => window.clearInterval(interval)
  }, [filters, loadDetail, loadQueue, selectedPoId])

  const selected = useMemo(() => {
    if (!selectedPoId) return queue[0] ?? null
    return queue.find((row) => row.po_id === selectedPoId) ?? queue[0] ?? null
  }, [queue, selectedPoId])

  async function applyDecision(action: "approve" | "reject") {
    if (!selected) {
      setFeedback("Select a queue item first")
      return
    }

    const response = await decideApprovalQueueItem(selected.po_id, {
      action,
      reviewed_by: reviewedBy,
      reviewer_role: reviewerRole,
      comment: comment || undefined,
    })

    if (!response.ok || !response.data) {
      setFeedback(response.error ?? "Decision failed")
      return
    }

    setFeedback(`PO-${selected.po_id} ${action === "approve" ? "approved" : "rejected"}`)
    setComment("")
    await loadQueue(filters)
    await loadDetail(selected.po_id)
  }

  async function runTimeoutProcessing() {
    setIsProcessingTimeouts(true)
    const response = await processApprovalTimeouts()
    setIsProcessingTimeouts(false)

    if (!response.ok || !response.data) {
      setFeedback(response.error ?? "Timeout processing failed")
      return
    }

    setFeedback(`Processed ${response.data.count} timeout approvals`)
    await loadQueue(filters)
    if (selectedPoId) {
      await loadDetail(selectedPoId)
    }
  }

  function onPage(direction: -1 | 1) {
    setFilters((prev) => ({
      ...prev,
      offset: Math.max(0, prev.offset + direction * prev.limit),
    }))
  }

  return (
    <div className="flex flex-col gap-5">
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <ShieldCheck className="size-4" />
            Manual Approval Workflow
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="grid grid-cols-1 gap-3 rounded-lg border border-border p-3 md:grid-cols-6">
            <div className="space-y-1.5 md:col-span-2">
              <Label className="text-xs">Search</Label>
              <Input
                value={filters.q}
                onChange={(event) => setFilters((prev) => ({ ...prev, q: event.target.value }))}
                placeholder="PO id, supplier, item..."
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">Status</Label>
              <Select
                value={filters.status || "all"}
                onValueChange={(value) => setFilters((prev) => ({ ...prev, status: value === "all" ? "" : value }))}
              >
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Statuses</SelectItem>
                  <SelectItem value="PENDING_REVIEW">PENDING_REVIEW</SelectItem>
                  <SelectItem value="PENDING_MANAGER_REVIEW">PENDING_MANAGER_REVIEW</SelectItem>
                  <SelectItem value="APPROVED">APPROVED</SelectItem>
                  <SelectItem value="REJECTED">REJECTED</SelectItem>
                  <SelectItem value="AUTO_APPROVED_TIMEOUT">AUTO_APPROVED_TIMEOUT</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">Level</Label>
              <Select
                value={filters.approval_level || "all"}
                onValueChange={(value) => setFilters((prev) => ({ ...prev, approval_level: value === "all" ? "" : value }))}
              >
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Levels</SelectItem>
                  <SelectItem value="AUTO">AUTO</SelectItem>
                  <SelectItem value="MANUAL">MANUAL</SelectItem>
                  <SelectItem value="MANAGER">MANAGER</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">Limit</Label>
              <Input
                type="number"
                min={1}
                max={500}
                value={filters.limit}
                onChange={(event) => setFilters((prev) => ({ ...prev, limit: Number(event.target.value) || 20 }))}
              />
            </div>
            <div className="flex items-end gap-2">
              <Button onClick={() => setFilters((prev) => ({ ...prev, offset: 0 }))}>
                <RefreshCw className="mr-2 size-4" />
                Apply
              </Button>
              <Button variant="outline" onClick={() => void runTimeoutProcessing()} disabled={isProcessingTimeouts}>
                <Clock className="mr-2 size-4" />
                Timeout Sweep
              </Button>
            </div>
          </div>

          {feedback && <p className="text-sm text-muted-foreground">{feedback}</p>}

          <div className="rounded-lg border border-border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>PO</TableHead>
                  <TableHead>Supplier</TableHead>
                  <TableHead>Item</TableHead>
                  <TableHead>Total</TableHead>
                  <TableHead>Level</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Due</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  <TableRow>
                    <TableCell colSpan={7} className="h-16 text-center text-sm text-muted-foreground">Loading queue...</TableCell>
                  </TableRow>
                ) : queue.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="h-16 text-center text-sm text-muted-foreground">No approvals found.</TableCell>
                  </TableRow>
                ) : (
                  queue.map((row) => (
                    <TableRow
                      key={row.po_id}
                      className="cursor-pointer"
                      data-state={selected?.po_id === row.po_id ? "selected" : undefined}
                      onClick={() => setSelectedPoId(row.po_id)}
                    >
                      <TableCell className="font-mono text-xs">PO-{row.po_id}</TableCell>
                      <TableCell>{row.supplier_name ?? "-"}</TableCell>
                      <TableCell>{row.item_name ?? "-"}</TableCell>
                      <TableCell>{row.total_cost?.toLocaleString() ?? "-"}</TableCell>
                      <TableCell><Badge variant="outline">{row.approval_level}</Badge></TableCell>
                      <TableCell>
                        <Badge variant={row.approval_status.includes("REJECT") ? "destructive" : "secondary"}>
                          {row.approval_status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">{formatDate(row.due_at)}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>

          <div className="flex items-center justify-between gap-2">
            <p className="text-xs text-muted-foreground">Showing {queue.length} of {count}</p>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={filters.offset === 0} onClick={() => onPage(-1)}>Previous</Button>
              <Button variant="outline" size="sm" disabled={(filters.offset + filters.limit) >= count} onClick={() => onPage(1)}>Next</Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">PO Details, Decision, and Audit Trail</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {!selected || detailLoading || !detail ? (
            <p className="text-sm text-muted-foreground">{detailLoading ? "Loading detail..." : "Select a queue item."}</p>
          ) : (
            <>
              <div className="grid grid-cols-1 gap-3 rounded-lg border border-border p-3 md:grid-cols-4">
                <InfoCell label="PO" value={`PO-${detail.po_id}`} />
                <InfoCell label="Supplier" value={detail.supplier_name ?? "-"} />
                <InfoCell label="Item" value={detail.item_name ?? "-"} />
                <InfoCell label="Total Cost" value={detail.total_cost ? detail.total_cost.toLocaleString() : "-"} />
                <InfoCell label="Approval Level" value={detail.approval_level} />
                <InfoCell label="Approval Status" value={detail.approval_status} />
                <InfoCell label="Requested" value={formatDate(detail.requested_at)} />
                <InfoCell label="Due" value={formatDate(detail.due_at)} />
              </div>

              <div className="rounded-lg border border-border p-3">
                <h4 className="mb-2 text-sm font-semibold">Scoring Breakdown</h4>
                <pre className="max-h-40 overflow-auto rounded-md border border-border bg-muted/20 p-2 text-xs">
                  {JSON.stringify(detail.score_breakdown, null, 2)}
                </pre>
              </div>

              <div className="grid grid-cols-1 gap-3 rounded-lg border border-border p-3 md:grid-cols-3">
                <div className="space-y-1.5">
                  <Label className="text-xs">Reviewed By</Label>
                  <Input value={reviewedBy} onChange={(event) => setReviewedBy(event.target.value)} />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs">Reviewer Role</Label>
                  <Select value={reviewerRole} onValueChange={(value) => setReviewerRole(value as "analyst" | "manager" | "admin")}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="analyst">analyst</SelectItem>
                      <SelectItem value="manager">manager</SelectItem>
                      <SelectItem value="admin">admin</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5 md:col-span-3">
                  <Label className="text-xs">Comments</Label>
                  <Textarea value={comment} onChange={(event) => setComment(event.target.value)} className="min-h-24" />
                </div>
                <div className="flex flex-wrap gap-2 md:col-span-3">
                  <Button onClick={() => void applyDecision("approve")}>
                    <CheckCircle2 className="mr-2 size-4" /> Approve
                  </Button>
                  <Button variant="destructive" onClick={() => void applyDecision("reject")}>
                    <XCircle className="mr-2 size-4" /> Reject
                  </Button>
                </div>
              </div>

              <div className="rounded-lg border border-border p-3">
                <h4 className="mb-2 text-sm font-semibold">Audit Trail</h4>
                {detail.audit_trail.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No audit events found.</p>
                ) : (
                  <div className="space-y-2">
                    {detail.audit_trail.map((event) => (
                      <div key={event.audit_id} className="rounded-md border border-border bg-muted/20 p-2">
                        <p className="text-xs font-medium">{event.event_type} • {event.new_status}</p>
                        <p className="text-xs text-muted-foreground">{formatDate(event.created_at)} by {event.actor}</p>
                        <p className="text-xs text-muted-foreground">{event.comment ?? "-"}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function InfoCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-muted/20 p-2">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-sm font-medium">{value}</p>
    </div>
  )
}
