"use client"

import { useMemo, useState } from "react"
import { Download, FileSearch, Filter } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
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
import type { AgentLogsResponse } from "@/lib/ml-api"

type LogsQueryState = {
  agent_name: string
  status: string
  level: string
  q: string
  limit: number
  offset: number
}

type ActionResult = {
  ok: boolean
  message: string
}

interface AgentLogsProps {
  data: AgentLogsResponse | null
  loading: boolean
  initialQuery: LogsQueryState
  onSearch: (query: LogsQueryState) => Promise<void>
  onExport: (query: LogsQueryState) => Promise<ActionResult>
}

function formatTimestamp(value: string | null) {
  if (!value) return "-"
  return new Date(value).toLocaleString()
}

export function AgentLogs({ data, loading, initialQuery, onSearch, onExport }: AgentLogsProps) {
  const [query, setQuery] = useState<LogsQueryState>(initialQuery)
  const [selectedLogId, setSelectedLogId] = useState<number | null>(null)
  const [feedback, setFeedback] = useState<string | null>(null)

  const records = useMemo(() => data?.records ?? [], [data?.records])
  const agentOptions = useMemo(() => {
    return Array.from(new Set(records.map((row) => row.agent_name).filter(Boolean))).sort()
  }, [records])
  const statusOptions = useMemo(() => {
    return Array.from(new Set(records.map((row) => row.status).filter(Boolean))).sort()
  }, [records])
  const levelOptions = useMemo(() => {
    return Array.from(new Set(records.map((row) => row.level).filter(Boolean))).sort()
  }, [records])

  const selected = useMemo(() => {
    if (!selectedLogId) return records[0] ?? null
    return records.find((row) => row.log_id === selectedLogId) ?? records[0] ?? null
  }, [records, selectedLogId])

  async function applyFilters(next: LogsQueryState) {
    setQuery(next)
    await onSearch(next)
  }

  async function exportCsv() {
    const result = await onExport(query)
    setFeedback(result.message)
  }

  async function goToPage(direction: -1 | 1) {
    const nextOffset = Math.max(0, query.offset + direction * query.limit)
    const next = {
      ...query,
      offset: nextOffset,
    }
    await applyFilters(next)
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <FileSearch className="size-4" />
          Agent Logs
          {loading && <Badge variant="secondary">Loading...</Badge>}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="grid grid-cols-1 gap-3 rounded-lg border border-border p-3 md:grid-cols-6">
          <div className="space-y-1.5 md:col-span-2">
            <Label className="text-xs">Search</Label>
            <Input
              value={query.q}
              onChange={(event) => setQuery((prev) => ({ ...prev, q: event.target.value }))}
              placeholder="task or error text"
            />
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs">Agent</Label>
            <Select
              value={query.agent_name || "all"}
              onValueChange={(value) => setQuery((prev) => ({ ...prev, agent_name: value === "all" ? "" : value }))}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Agents</SelectItem>
                {agentOptions.map((agentName) => (
                  <SelectItem key={agentName} value={agentName}>{agentName}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs">Status</Label>
            <Select
              value={query.status || "all"}
              onValueChange={(value) => setQuery((prev) => ({ ...prev, status: value === "all" ? "" : value }))}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                {statusOptions.length > 0 ? statusOptions.map((status) => (
                  <SelectItem key={status} value={status}>{status}</SelectItem>
                )) : (
                  <>
                    <SelectItem value="queued">queued</SelectItem>
                    <SelectItem value="running">running</SelectItem>
                    <SelectItem value="succeeded">succeeded</SelectItem>
                    <SelectItem value="failed">failed</SelectItem>
                    <SelectItem value="completed">completed</SelectItem>
                  </>
                )}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs">Level</Label>
            <Select
              value={query.level || "all"}
              onValueChange={(value) => setQuery((prev) => ({ ...prev, level: value === "all" ? "" : value }))}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Levels</SelectItem>
                {levelOptions.length > 0 ? levelOptions.map((level) => (
                  <SelectItem key={level} value={level}>{level}</SelectItem>
                )) : (
                  <>
                    <SelectItem value="INFO">INFO</SelectItem>
                    <SelectItem value="ERROR">ERROR</SelectItem>
                    <SelectItem value="WARNING">WARNING</SelectItem>
                    <SelectItem value="DEBUG">DEBUG</SelectItem>
                  </>
                )}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs">Limit</Label>
            <Input
              type="number"
              min={1}
              max={500}
              value={query.limit}
              onChange={(event) => setQuery((prev) => ({ ...prev, limit: Number(event.target.value) || 25 }))}
            />
          </div>

          <div className="md:col-span-6 flex flex-wrap items-center gap-2">
            <Button onClick={() => void applyFilters({ ...query, offset: 0 })}>
              <Filter className="mr-2 size-4" />
              Apply Filters
            </Button>
            <Button variant="outline" onClick={() => void exportCsv()}>
              <Download className="mr-2 size-4" />
              Export CSV
            </Button>
            {feedback && <p className="text-xs text-muted-foreground">{feedback}</p>}
          </div>
        </div>

        <div className="rounded-lg border border-border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Agent</TableHead>
                <TableHead>Task</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Level</TableHead>
                <TableHead>Created</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {!data || data.records.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="h-16 text-center text-sm text-muted-foreground">
                    No logs found for current filters.
                  </TableCell>
                </TableRow>
              ) : (
                data.records.map((row) => (
                  <TableRow
                    key={row.log_id}
                    className="cursor-pointer"
                    data-state={selected?.log_id === row.log_id ? "selected" : undefined}
                    onClick={() => setSelectedLogId(row.log_id)}
                  >
                    <TableCell className="font-mono text-xs">{row.log_id}</TableCell>
                    <TableCell>{row.agent_name}</TableCell>
                    <TableCell className="max-w-44 truncate">{row.task_description}</TableCell>
                    <TableCell>
                      <Badge variant={row.status === "failed" ? "destructive" : "outline"}>{row.status}</Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary">{row.level}</Badge>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">{formatTimestamp(row.created_at)}</TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs text-muted-foreground">Showing {data?.records.length ?? 0} of {data?.count ?? 0} logs</p>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={query.offset === 0}
              onClick={() => void goToPage(-1)}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={(query.offset + query.limit) >= (data?.count ?? 0)}
              onClick={() => void goToPage(1)}
            >
              Next
            </Button>
          </div>
        </div>

        {selected && (
          <div className="rounded-lg border border-border bg-muted/20 p-3">
            <h4 className="mb-2 text-sm font-semibold">Drill-down: Log #{selected.log_id}</h4>
            <div className="grid grid-cols-1 gap-2 lg:grid-cols-2">
              <div>
                <p className="mb-1 text-xs font-medium text-muted-foreground">Result</p>
                <pre className="max-h-52 overflow-auto rounded-md border border-border bg-background p-2 text-[11px]">
                  {JSON.stringify(selected.result, null, 2)}
                </pre>
              </div>
              <div>
                <p className="mb-1 text-xs font-medium text-muted-foreground">Errors</p>
                <pre className="max-h-52 overflow-auto rounded-md border border-border bg-background p-2 text-[11px]">
                  {JSON.stringify(selected.errors, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
