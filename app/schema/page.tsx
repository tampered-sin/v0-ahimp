"use client"

import { DashboardLayout } from "@/components/dashboard-layout"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Database } from "lucide-react"

const TABLE_GROUPS = {
  Master:      { color: "bg-blue-500/10 border-blue-500/30 text-blue-600", badge: "bg-blue-500/10 text-blue-600 border-blue-500/30" },
  Inventory:   { color: "bg-purple-500/10 border-purple-500/30 text-purple-600", badge: "bg-purple-500/10 text-purple-600 border-purple-500/30" },
  Procurement: { color: "bg-amber-500/10 border-amber-500/30 text-amber-600", badge: "bg-amber-500/10 text-amber-600 border-amber-500/30" },
  ML:          { color: "bg-emerald-500/10 border-emerald-500/30 text-emerald-600", badge: "bg-emerald-500/10 text-emerald-600 border-emerald-500/30" },
  Equipment:   { color: "bg-orange-500/10 border-orange-500/30 text-orange-600", badge: "bg-orange-500/10 text-orange-600 border-orange-500/30" },
  Predictions: { color: "bg-primary/10 border-primary/30 text-primary", badge: "bg-primary/10 text-primary border-primary/30" },
  Audit:       { color: "bg-rose-500/10 border-rose-500/30 text-rose-600", badge: "bg-rose-500/10 text-rose-600 border-rose-500/30" },
}

type GroupKey = keyof typeof TABLE_GROUPS

interface Field { name: string; type: string; constraint?: string }
interface TableDef { name: string; group: GroupKey; fields: Field[]; fks?: string[] }

const TABLES: TableDef[] = [
  {
    name: "Departments", group: "Master",
    fields: [
      { name: "department_id",   type: "INT",          constraint: "PK" },
      { name: "department_name", type: "VARCHAR(100)",  constraint: "NOT NULL" },
      { name: "location",        type: "VARCHAR(100)" },
    ],
  },
  {
    name: "Suppliers", group: "Master",
    fields: [
      { name: "supplier_id",        type: "INT",          constraint: "PK" },
      { name: "supplier_name",      type: "VARCHAR(150)", constraint: "NOT NULL" },
      { name: "contact_email",      type: "VARCHAR(150)" },
      { name: "contact_phone",      type: "VARCHAR(20)" },
      { name: "avg_lead_time_days", type: "INT" },
      { name: "reliability_score",  type: "FLOAT" },
    ],
  },
  {
    name: "Items", group: "Master",
    fields: [
      { name: "item_id",            type: "INT",          constraint: "PK" },
      { name: "item_name",          type: "VARCHAR(150)", constraint: "NOT NULL" },
      { name: "category",           type: "VARCHAR(100)" },
      { name: "unit_type",          type: "VARCHAR(50)" },
      { name: "safety_stock_level", type: "INT" },
      { name: "reorder_point",      type: "INT" },
    ],
  },
  {
    name: "Batches", group: "Inventory",
    fks: ["Items", "Suppliers"],
    fields: [
      { name: "batch_id",          type: "INT",   constraint: "PK" },
      { name: "item_id",           type: "INT",   constraint: "FK → Items" },
      { name: "supplier_id",       type: "INT",   constraint: "FK → Suppliers" },
      { name: "manufacture_date",  type: "DATE" },
      { name: "expiry_date",       type: "DATE" },
      { name: "purchase_price",    type: "FLOAT" },
      { name: "quantity_received", type: "INT" },
    ],
  },
  {
    name: "Inventory_Stock", group: "Inventory",
    fks: ["Items", "Batches", "Departments"],
    fields: [
      { name: "stock_id",         type: "INT",       constraint: "PK" },
      { name: "item_id",          type: "INT",       constraint: "FK → Items" },
      { name: "batch_id",         type: "INT",       constraint: "FK → Batches" },
      { name: "department_id",    type: "INT",       constraint: "FK → Departments" },
      { name: "current_quantity", type: "INT",       constraint: "NOT NULL" },
      { name: "last_updated",     type: "TIMESTAMP" },
    ],
  },
  {
    name: "Purchase_Orders", group: "Procurement",
    fks: ["Suppliers"],
    fields: [
      { name: "po_id",             type: "INT",         constraint: "PK" },
      { name: "supplier_id",       type: "INT",         constraint: "FK → Suppliers" },
      { name: "order_date",        type: "DATE" },
      { name: "expected_delivery", type: "DATE" },
      { name: "status",            type: "VARCHAR(50)" },
    ],
  },
  {
    name: "Goods_Receipts", group: "Procurement",
    fks: ["Purchase_Orders"],
    fields: [
      { name: "grn_id",        type: "INT",          constraint: "PK" },
      { name: "po_id",         type: "INT",          constraint: "FK → Purchase_Orders" },
      { name: "received_date", type: "DATE" },
      { name: "verified_by",   type: "VARCHAR(100)" },
    ],
  },
  {
    name: "Consumption_Records", group: "ML",
    fks: ["Items", "Batches", "Departments"],
    fields: [
      { name: "consumption_id", type: "INT",         constraint: "PK" },
      { name: "item_id",        type: "INT",         constraint: "FK → Items" },
      { name: "batch_id",       type: "INT",         constraint: "FK → Batches" },
      { name: "department_id",  type: "INT",         constraint: "FK → Departments" },
      { name: "quantity_used",  type: "INT" },
      { name: "usage_date",     type: "DATE" },
      { name: "patient_type",   type: "VARCHAR(50)" },
    ],
  },
  {
    name: "Equipment", group: "Equipment",
    fks: ["Departments"],
    fields: [
      { name: "equipment_id",   type: "INT",          constraint: "PK" },
      { name: "equipment_name", type: "VARCHAR(150)" },
      { name: "serial_number",  type: "VARCHAR(150)" },
      { name: "department_id",  type: "INT",          constraint: "FK → Departments" },
      { name: "purchase_date",  type: "DATE" },
      { name: "maintenance_due",type: "DATE" },
    ],
  },
  {
    name: "Equipment_Usage", group: "Equipment",
    fks: ["Equipment"],
    fields: [
      { name: "usage_id",     type: "INT",   constraint: "PK" },
      { name: "equipment_id", type: "INT",   constraint: "FK → Equipment" },
      { name: "usage_date",   type: "DATE" },
      { name: "usage_hours",  type: "FLOAT" },
    ],
  },
  {
    name: "Demand_Predictions", group: "Predictions",
    fks: ["Items"],
    fields: [
      { name: "prediction_id",      type: "INT",         constraint: "PK" },
      { name: "item_id",            type: "INT",         constraint: "FK → Items" },
      { name: "prediction_date",    type: "DATE" },
      { name: "predicted_quantity", type: "FLOAT" },
      { name: "model_version",      type: "VARCHAR(50)" },
    ],
  },
  {
    name: "Stockout_Risk", group: "Predictions",
    fks: ["Items"],
    fields: [
      { name: "risk_id",          type: "INT",     constraint: "PK" },
      { name: "item_id",          type: "INT",     constraint: "FK → Items" },
      { name: "prediction_date",  type: "DATE" },
      { name: "risk_probability", type: "FLOAT" },
      { name: "risk_flag",        type: "BOOLEAN" },
    ],
  },
  {
    name: "Expiry_Risk", group: "Predictions",
    fks: ["Batches"],
    fields: [
      { name: "expiry_id",               type: "INT",     constraint: "PK" },
      { name: "batch_id",                type: "INT",     constraint: "FK → Batches" },
      { name: "prediction_date",         type: "DATE" },
      { name: "expiry_risk_probability", type: "FLOAT" },
      { name: "high_risk_flag",          type: "BOOLEAN" },
    ],
  },
  {
    name: "Inventory_Audit_Log", group: "Audit",
    fks: ["Items", "Batches"],
    fields: [
      { name: "audit_id",         type: "INT",          constraint: "PK" },
      { name: "item_id",          type: "INT",          constraint: "FK → Items" },
      { name: "batch_id",         type: "INT",          constraint: "FK → Batches" },
      { name: "old_quantity",     type: "INT" },
      { name: "new_quantity",     type: "INT" },
      { name: "updated_by",       type: "VARCHAR(100)" },
      { name: "update_timestamp", type: "TIMESTAMP" },
    ],
  },
  {
    name: "Cost_Analysis", group: "Audit",
    fks: ["Items"],
    fields: [
      { name: "cost_id",           type: "INT",   constraint: "PK" },
      { name: "item_id",           type: "INT",   constraint: "FK → Items" },
      { name: "holding_cost",      type: "FLOAT" },
      { name: "shortage_cost",     type: "FLOAT" },
      { name: "expiry_loss_cost",  type: "FLOAT" },
      { name: "estimated_savings", type: "FLOAT" },
    ],
  },
]

export default function SchemaPage() {
  return (
    <DashboardLayout title="Database Schema">
      <div className="flex flex-col gap-6">
        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-xl bg-primary/10">
              <Database className="size-5 text-primary" />
            </div>
            <div>
              <p className="text-sm font-semibold text-foreground">AHIMP Relational Schema</p>
              <p className="text-xs text-muted-foreground">{TABLES.length} tables · SQLite (dev) / PostgreSQL (prod)</p>
            </div>
          </div>
          {/* Legend */}
          <div className="flex flex-wrap gap-2">
            {(Object.keys(TABLE_GROUPS) as GroupKey[]).map(g => (
              <Badge key={g} variant="outline" className={`text-[10px] ${TABLE_GROUPS[g].badge}`}>{g}</Badge>
            ))}
          </div>
        </div>

        {/* Table cards grid */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {TABLES.map(table => {
            const style = TABLE_GROUPS[table.group]
            return (
              <Card key={table.name} className={`border ${style.color}`}>
                <CardHeader className="pb-2 pt-3 px-4">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-sm font-semibold font-mono">{table.name}</CardTitle>
                    <Badge variant="outline" className={`text-[10px] ${style.badge}`}>{table.group}</Badge>
                  </div>
                  {table.fks && (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {table.fks.map(fk => (
                        <span key={fk} className="text-[9px] bg-muted text-muted-foreground px-1.5 py-0.5 rounded font-mono">
                          → {fk}
                        </span>
                      ))}
                    </div>
                  )}
                </CardHeader>
                <CardContent className="px-4 pb-3">
                  <div className="flex flex-col gap-0.5">
                    {table.fields.map(f => (
                      <div key={f.name} className="flex items-center justify-between text-[10px] py-0.5 border-b border-border/40 last:border-0">
                        <div className="flex items-center gap-1.5">
                          {f.constraint?.includes("PK") && (
                            <span className="size-1.5 rounded-full bg-amber-500 shrink-0" title="Primary Key"/>
                          )}
                          {f.constraint?.includes("FK") && (
                            <span className="size-1.5 rounded-full bg-blue-500 shrink-0" title="Foreign Key"/>
                          )}
                          {!f.constraint && <span className="size-1.5 shrink-0"/>}
                          <span className="font-mono text-foreground">{f.name}</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <span className="text-muted-foreground font-mono">{f.type}</span>
                          {f.constraint && !f.constraint.includes("FK") && (
                            <Badge variant="outline" className="text-[8px] py-0 px-1 h-3.5">
                              {f.constraint.split(" ")[0]}
                            </Badge>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>

        {/* Legend */}
        <Card>
          <CardContent className="py-3 px-4">
            <div className="flex flex-wrap gap-4 text-[10px] text-muted-foreground">
              <span className="flex items-center gap-1.5"><span className="size-2 rounded-full bg-amber-500 inline-block"/>Primary Key</span>
              <span className="flex items-center gap-1.5"><span className="size-2 rounded-full bg-blue-500 inline-block"/>Foreign Key (relationship)</span>
              <span className="flex items-center gap-1.5"><span className="font-mono bg-muted px-1 rounded">FLOAT</span>Model prediction output</span>
              <span className="flex items-center gap-1.5"><span className="font-mono bg-muted px-1 rounded">BOOLEAN</span>Binary risk flag</span>
            </div>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  )
}
