"use client"

import { DashboardLayout } from "@/components/dashboard-layout"
import { ApprovalQueuePage } from "@/components/approvals/ApprovalQueuePage"

export default function ApprovalQueueRoute() {
  return (
    <DashboardLayout title="Approval Queue">
      <ApprovalQueuePage />
    </DashboardLayout>
  )
}
