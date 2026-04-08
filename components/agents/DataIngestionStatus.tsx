"use client"

import { useMemo, useState } from "react"
import { Activity, Database, RefreshCw, PlayCircle } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type { DataIngestionJobStatus, DataIngestionTriggerPayload } from "@/lib/ml-api"

type ActionResult = {
  ok: boolean
  message: string
}

interface DataIngestionStatusProps {
  jobs: DataIngestionJobStatus[]
  jobCounts?: {
    total: number
    queued: number
    running: number
    succeeded: number
    failed: number
  }
  isLoading: boolean
  isTriggering: boolean
  onTrigger: (payload: DataIngestionTriggerPayload) => Promise<ActionResult>
  onRefreshJob: (jobId: string) => Promise<void>
}

function formatTime(value?: string) {
  if (!value) return "-"
  return new Date(value).toLocaleString()
}

export function DataIngestionStatus({
  jobs,
  jobCounts,
  isLoading,
  isTriggering,
  onTrigger,
  onRefreshJob,
}: DataIngestionStatusProps) {
  const [sourceType, setSourceType] = useState<"records" | "csv" | "api">("records")
  const [csvPath, setCsvPath] = useState("")
  const [apiUrl, setApiUrl] = useState("")
  const [apiFormat, setApiFormat] = useState<"json" | "xml">("json")
  const [recordsText, setRecordsText] = useState(
    JSON.stringify(
      [
        {
          item_id: 1,
          department_id: 1,
          quantity_used: 5,
          usage_date: "2026-01-01",
          patient_type: "general",
        },
      ],
      null,
      2
    )
  )
  const [runAsync, setRunAsync] = useState(true)
  const [feedback, setFeedback] = useState<string | null>(null)

  const sortedJobs = useMemo(() => {
    return [...jobs].sort((a, b) => {
      const left = new Date(a.created_at ?? 0).getTime()
      const right = new Date(b.created_at ?? 0).getTime()
      return right - left
    })
  }, [jobs])

  async function handleSubmit() {
    let records: Array<Record<string, unknown>> | undefined

    if (sourceType === "records") {
      try {
        const parsed = JSON.parse(recordsText) as unknown
        if (!Array.isArray(parsed) || parsed.length === 0) {
          setFeedback("Records input must be a non-empty JSON array")
          return
        }
        records = parsed as Array<Record<string, unknown>>
      } catch {
        setFeedback("Invalid JSON in records payload")
        return
      }
    }

    const payload: DataIngestionTriggerPayload = {
      source_type: sourceType,
      run_async: runAsync,
      allow_partial: true,
      max_retries: 2,
      api_format: apiFormat,
      csv_path: csvPath || undefined,
      api_url: apiUrl || undefined,
      records,
    }

    const result = await onTrigger(payload)
    setFeedback(result.message)
  }

  const statusTone: Record<string, "secondary" | "destructive" | "default" | "outline"> = {
    queued: "secondary",
    running: "default",
    succeeded: "outline",
    completed: "outline",
    failed: "destructive",
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex flex-wrap items-center gap-2 text-base">
          <Database className="size-4" />
          Data Ingestion Status
          {isLoading && <Badge variant="secondary">Loading…</Badge>}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
          <StatCell label="Total" value={jobCounts?.total ?? 0} />
          <StatCell label="Queued" value={jobCounts?.queued ?? 0} />
          <StatCell label="Running" value={jobCounts?.running ?? 0} />
          <StatCell label="Succeeded" value={jobCounts?.succeeded ?? 0} />
          <StatCell label="Failed" value={jobCounts?.failed ?? 0} />
        </div>

        <div className="rounded-lg border border-border p-3">
          <div className="mb-3 flex items-center gap-2">
            <PlayCircle className="size-4 text-primary" />
            <h3 className="text-sm font-semibold">Manual Trigger</h3>
          </div>

          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <div className="space-y-1.5">
              <Label className="text-xs">Source</Label>
              <Select value={sourceType} onValueChange={(value) => setSourceType(value as "records" | "csv" | "api") }>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="records">Inline records</SelectItem>
                  <SelectItem value="csv">CSV path</SelectItem>
                  <SelectItem value="api">API source</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs">Run Async</Label>
              <div className="flex h-10 items-center justify-between rounded-md border border-border px-3">
                <span className="text-sm text-muted-foreground">Background job execution</span>
                <Switch checked={runAsync} onCheckedChange={setRunAsync} />
              </div>
            </div>

            {sourceType === "csv" && (
              <div className="space-y-1.5 lg:col-span-2">
                <Label className="text-xs">CSV Path</Label>
                <Input
                  value={csvPath}
                  onChange={(event) => setCsvPath(event.target.value)}
                  placeholder="/data/uploads/consumption.csv"
                />
              </div>
            )}

            {sourceType === "api" && (
              <>
                <div className="space-y-1.5 lg:col-span-2">
                  <Label className="text-xs">API URL</Label>
                  <Input
                    value={apiUrl}
                    onChange={(event) => setApiUrl(event.target.value)}
                    placeholder="https://example.com/consumption"
                  />
                </div>
                <div className="space-y-1.5 lg:col-span-2">
                  <Label className="text-xs">API Format</Label>
                  <Select value={apiFormat} onValueChange={(value) => setApiFormat(value as "json" | "xml") }>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="json">JSON</SelectItem>
                      <SelectItem value="xml">XML</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </>
            )}

            {sourceType === "records" && (
              <div className="space-y-1.5 lg:col-span-2">
                <Label className="text-xs">Records JSON</Label>
                <Textarea
                  value={recordsText}
                  onChange={(event) => setRecordsText(event.target.value)}
                  className="min-h-32 font-mono text-xs"
                />
              </div>
            )}
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Button onClick={() => void handleSubmit()} disabled={isTriggering}>
              <Activity className="mr-2 size-4" />
              {isTriggering ? "Submitting..." : "Trigger Ingestion"}
            </Button>
            {feedback && (
              <p className="text-xs text-muted-foreground">{feedback}</p>
            )}
          </div>
        </div>

        <div className="rounded-lg border border-border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Job ID</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Created</TableHead>
                <TableHead>Completed</TableHead>
                <TableHead className="text-right">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedJobs.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="h-16 text-center text-sm text-muted-foreground">
                    No ingestion jobs yet.
                  </TableCell>
                </TableRow>
              ) : (
                sortedJobs.map((job) => (
                  <TableRow key={job.job_id}>
                    <TableCell className="max-w-52 truncate font-mono text-xs">{job.job_id}</TableCell>
                    <TableCell>
                      <Badge variant={statusTone[job.status] ?? "secondary"}>{job.status}</Badge>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">{formatTime(job.created_at)}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{formatTime(job.completed_at)}</TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => void onRefreshJob(job.job_id)}
                        disabled={!job.job_id || job.job_id.startsWith("sync-")}
                      >
                        <RefreshCw className="mr-1 size-3.5" />
                        Refresh
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  )
}

function StatCell({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-border bg-muted/30 px-3 py-2">
      <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="text-lg font-bold">{value}</p>
    </div>
  )
}
