"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { AlertTriangle, RefreshCw } from "lucide-react"
import {
  exportAgentLogsCsv,
  getAgentLogs,
  getAgentsDashboard,
  getDataIngestionStatus,
  getSupplyChainAtRisk,
  optimizeSupplyChain,
  triggerDataIngestion,
  type AgentDashboardResponse,
  type AgentLogRecord,
  type AgentLogsResponse,
  type DataIngestionJobStatus,
  type DataIngestionTriggerPayload,
  type SupplyChainRequestPayload,
  type SupplyChainResponse,
} from "@/lib/ml-api"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { DataIngestionStatus } from "./DataIngestionStatus"
import { AtRiskItems } from "./AtRiskItems"
import { SupplierRecommendations } from "./SupplierRecommendations"
import { POTracker } from "./POTracker"
import { AgentLogs } from "./AgentLogs"

type ActionResult = {
  ok: boolean
  message: string
}

type LogsQueryState = {
  agent_name: string
  status: string
  level: string
  q: string
  limit: number
  offset: number
}

const DEFAULT_RISK_PARAMS: SupplyChainRequestPayload = {
  risk_threshold: 0.7,
  max_items: 15,
  cadence_hours: 1,
  supplier_overrides: {},
}

const DEFAULT_LOG_QUERY: LogsQueryState = {
  agent_name: "",
  status: "",
  level: "",
  q: "",
  limit: 25,
  offset: 0,
}

function formatAgo(isoTime: string | null) {
  if (!isoTime) return "-"
  const time = new Date(isoTime)
  const sec = Math.floor((Date.now() - time.getTime()) / 1000)
  if (sec < 60) return `${sec}s ago`
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`
  return `${Math.floor(sec / 86400)}d ago`
}

export function AgentDashboard() {
  const [dashboard, setDashboard] = useState<AgentDashboardResponse | null>(null)
  const [atRiskData, setAtRiskData] = useState<SupplyChainResponse | null>(null)
  const [optimizeData, setOptimizeData] = useState<SupplyChainResponse | null>(null)
  const [logsData, setLogsData] = useState<AgentLogsResponse | null>(null)
  const [jobs, setJobs] = useState<DataIngestionJobStatus[]>([])

  const [riskParams, setRiskParams] = useState<SupplyChainRequestPayload>(DEFAULT_RISK_PARAMS)
  const [logsQuery, setLogsQuery] = useState<LogsQueryState>(DEFAULT_LOG_QUERY)

  const [loadingDashboard, setLoadingDashboard] = useState(true)
  const [loadingAtRisk, setLoadingAtRisk] = useState(true)
  const [loadingLogs, setLoadingLogs] = useState(true)
  const [isTriggering, setIsTriggering] = useState(false)
  const [isOptimizing, setIsOptimizing] = useState(false)
  const [isRefreshing, setIsRefreshing] = useState(false)

  const [globalError, setGlobalError] = useState<string | null>(null)
  const [lastUpdatedAt, setLastUpdatedAt] = useState<string | null>(null)

  const loadDashboard = useCallback(async () => {
    setLoadingDashboard(true)
    const response = await getAgentsDashboard()
    if (response.ok && response.data) {
      setDashboard(response.data)
      setGlobalError(null)
    } else {
      setGlobalError(response.error ?? "Unable to load dashboard summary")
    }
    setLoadingDashboard(false)
  }, [])

  const loadAtRisk = useCallback(async (params: SupplyChainRequestPayload) => {
    setLoadingAtRisk(true)
    const response = await getSupplyChainAtRisk({
      risk_threshold: params.risk_threshold,
      max_items: params.max_items,
      cadence_hours: params.cadence_hours,
    })
    if (response.ok && response.data) {
      setAtRiskData(response.data)
      setGlobalError(null)
    } else {
      setGlobalError(response.error ?? "Unable to load at-risk analysis")
    }
    setLoadingAtRisk(false)
  }, [])

  const loadLogs = useCallback(async (query: LogsQueryState) => {
    setLoadingLogs(true)
    const response = await getAgentLogs({
      agent_name: query.agent_name || undefined,
      status: query.status || undefined,
      level: query.level || undefined,
      q: query.q || undefined,
      limit: query.limit,
      offset: query.offset,
    })
    if (response.ok && response.data) {
      setLogsData(response.data)
      setGlobalError(null)
    } else {
      setGlobalError(response.error ?? "Unable to load agent logs")
    }
    setLoadingLogs(false)
  }, [])

  const refreshAll = useCallback(async () => {
    setIsRefreshing(true)
    await Promise.all([
      loadDashboard(),
      loadAtRisk(riskParams),
      loadLogs(logsQuery),
    ])
    setLastUpdatedAt(new Date().toISOString())
    setIsRefreshing(false)
  }, [loadAtRisk, loadDashboard, loadLogs, logsQuery, riskParams])

  useEffect(() => {
    void refreshAll()
  }, [refreshAll])

  useEffect(() => {
    const interval = window.setInterval(() => {
      void loadDashboard()
      void loadAtRisk(riskParams)
      void loadLogs(logsQuery)
      setLastUpdatedAt(new Date().toISOString())
    }, 30000)

    return () => window.clearInterval(interval)
  }, [loadAtRisk, loadDashboard, loadLogs, logsQuery, riskParams])

  useEffect(() => {
    const activeJobs = jobs.filter((job) => job.status === "queued" || job.status === "running")
    if (activeJobs.length === 0) {
      return
    }

    const interval = window.setInterval(() => {
      activeJobs.forEach((job) => {
        void (async () => {
          const response = await getDataIngestionStatus(job.job_id)
          if (!response.ok || !response.data) return

          setJobs((prev) => prev.map((row) => (row.job_id === job.job_id ? response.data as DataIngestionJobStatus : row)))

          if (response.data.status === "failed" || response.data.status === "succeeded") {
            await Promise.all([loadDashboard(), loadLogs(logsQuery)])
            setLastUpdatedAt(new Date().toISOString())
          }
        })()
      })
    }, 5000)

    return () => window.clearInterval(interval)
  }, [jobs, loadDashboard, loadLogs, logsQuery])

  const handleAnalyzeAtRisk = useCallback(async (params: SupplyChainRequestPayload) => {
    setRiskParams(params)
    await loadAtRisk(params)
    setLastUpdatedAt(new Date().toISOString())
  }, [loadAtRisk])

  const handleTriggerIngestion = useCallback(async (payload: DataIngestionTriggerPayload): Promise<ActionResult> => {
    setIsTriggering(true)
    const response = await triggerDataIngestion(payload)
    setIsTriggering(false)

    if (!response.ok || !response.data) {
      const message = response.error ?? "Failed to trigger ingestion"
      setGlobalError(message)
      return { ok: false, message }
    }

    const triggerPayload = response.data
    const jobId = triggerPayload.job_id

    if (jobId !== null) {
      setJobs((prev) => [
        {
          job_id: jobId,
          status: (triggerPayload.status as DataIngestionJobStatus["status"]) ?? "queued",
          created_at: new Date().toISOString(),
          payload: {
            source_type: payload.source_type,
          },
        },
        ...prev.filter((row) => row.job_id !== jobId),
      ])
    } else {
      setJobs((prev) => [
        {
          job_id: `sync-${Date.now()}`,
          status: "completed",
          created_at: new Date().toISOString(),
          completed_at: new Date().toISOString(),
          result: triggerPayload.result,
        },
        ...prev,
      ])
    }

    await Promise.all([loadDashboard(), loadLogs(logsQuery)])
    setLastUpdatedAt(new Date().toISOString())
    return {
      ok: true,
      message: triggerPayload.job_id
        ? `Ingestion job queued: ${triggerPayload.job_id}`
        : "Ingestion completed",
    }
  }, [loadDashboard, loadLogs, logsQuery])

  const handleRefreshJob = useCallback(async (jobId: string) => {
    const response = await getDataIngestionStatus(jobId)
    if (!response.ok || !response.data) return

    setJobs((prev) => prev.map((job) => (job.job_id === jobId ? response.data as DataIngestionJobStatus : job)))

    if (response.data.status === "failed" || response.data.status === "succeeded") {
      await Promise.all([loadDashboard(), loadLogs(logsQuery)])
      setLastUpdatedAt(new Date().toISOString())
    }
  }, [loadDashboard, loadLogs, logsQuery])

  const handleOptimize = useCallback(async (payload: SupplyChainRequestPayload): Promise<ActionResult> => {
    setIsOptimizing(true)
    const response = await optimizeSupplyChain(payload)
    setIsOptimizing(false)

    if (!response.ok || !response.data) {
      const message = response.error ?? "Optimization failed"
      setGlobalError(message)
      return { ok: false, message }
    }

    setOptimizeData(response.data)
    await Promise.all([loadDashboard(), loadLogs(logsQuery), loadAtRisk(riskParams)])
    setLastUpdatedAt(new Date().toISOString())

    return {
      ok: true,
      message: `Optimization completed with ${response.data.result.decisions.length} recommendations`,
    }
  }, [loadAtRisk, loadDashboard, loadLogs, logsQuery, riskParams])

  const handleLogsSearch = useCallback(async (query: LogsQueryState) => {
    setLogsQuery(query)
    await loadLogs(query)
  }, [loadLogs])

  const handleExportLogs = useCallback(async (query: LogsQueryState): Promise<ActionResult> => {
    const response = await exportAgentLogsCsv({
      agent_name: query.agent_name || undefined,
      status: query.status || undefined,
      level: query.level || undefined,
      q: query.q || undefined,
      limit: query.limit,
      offset: query.offset,
    })

    if (!response.ok || !response.data) {
      return {
        ok: false,
        message: response.error ?? "CSV export failed",
      }
    }

    const blob = new Blob([response.data], { type: "text/csv;charset=utf-8;" })
    const url = window.URL.createObjectURL(blob)
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = `agent-logs-${Date.now()}.csv`
    anchor.click()
    window.URL.revokeObjectURL(url)

    return {
      ok: true,
      message: "CSV export downloaded",
    }
  }, [])

  const recommendationDecisions = useMemo(() => {
    if (optimizeData?.result?.decisions?.length) {
      return optimizeData.result.decisions
    }
    return atRiskData?.result?.decisions ?? []
  }, [atRiskData, optimizeData])

  const allLogRecords = useMemo<AgentLogRecord[]>(() => logsData?.records ?? [], [logsData])

  return (
    <div className="flex flex-col gap-5">
      {globalError && (
        <Card className="border-destructive/30 bg-destructive/5">
          <CardContent className="flex items-center gap-3 p-4 text-sm text-destructive">
            <AlertTriangle className="size-4" />
            <span>{globalError}</span>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent className="flex flex-col gap-4 p-4 md:flex-row md:items-center md:justify-between">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="secondary">Jobs: {dashboard?.jobs.total ?? 0}</Badge>
            <Badge variant="outline">Queued: {dashboard?.jobs.queued ?? 0}</Badge>
            <Badge variant="outline">Running: {dashboard?.jobs.running ?? 0}</Badge>
            <Badge variant="outline">Pending Audit: {dashboard?.audit.pending_count ?? 0}</Badge>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span>
              Updated {lastUpdatedAt ? formatAgo(lastUpdatedAt) : "just now"}
            </span>
            <Button size="sm" variant="outline" onClick={() => void refreshAll()} disabled={isRefreshing}>
              <RefreshCw className={`mr-2 size-3.5 ${isRefreshing ? "animate-spin" : ""}`} />
              Refresh
            </Button>
          </div>
        </CardContent>
      </Card>

      <DataIngestionStatus
        jobs={jobs}
        jobCounts={dashboard?.jobs}
        isLoading={loadingDashboard}
        isTriggering={isTriggering}
        onTrigger={handleTriggerIngestion}
        onRefreshJob={handleRefreshJob}
      />

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-5">
        <div className="xl:col-span-3">
          <AtRiskItems
            data={atRiskData}
            loading={loadingAtRisk}
            params={riskParams}
            onAnalyze={handleAnalyzeAtRisk}
          />
        </div>
        <div className="xl:col-span-2">
          <SupplierRecommendations decisions={recommendationDecisions} />
        </div>
      </div>

      <POTracker
        latestOptimize={optimizeData}
        logs={allLogRecords}
        isOptimizing={isOptimizing}
        onOptimize={handleOptimize}
      />

      <AgentLogs
        data={logsData}
        loading={loadingLogs}
        initialQuery={logsQuery}
        onSearch={handleLogsSearch}
        onExport={handleExportLogs}
      />
    </div>
  )
}
