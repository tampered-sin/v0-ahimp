"use client"

import { DashboardLayout } from "@/components/dashboard-layout"
import { AgentDashboard } from "@/components/agents/AgentDashboard"

export default function AgentsPage() {
  return (
    <DashboardLayout title="AI Agents">
      <AgentDashboard />
    </DashboardLayout>
  )
}
