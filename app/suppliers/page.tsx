"use client"

import { useState } from "react"
import { DashboardLayout } from "@/components/dashboard-layout"
import { useInventory } from "@/lib/inventory-context"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Plus,
  Star,
  Phone,
  Mail,
  MapPin,
  Package,
  Search,
  Pencil,
} from "lucide-react"
import type { Supplier } from "@/lib/types"

export default function SuppliersPage() {
  return (
    <DashboardLayout title="Supplier Management">
      <SuppliersContent />
    </DashboardLayout>
  )
}

function SuppliersContent() {
  const {
    state,
    getItemsBySupplier,
    hasPermission,
    addSupplierPersisted,
    updateSupplierPersisted,
  } = useInventory()
  const { suppliers } = state
  const [search, setSearch] = useState("")
  const [isAddOpen, setIsAddOpen] = useState(false)
  const [editSupplier, setEditSupplier] = useState<Supplier | null>(null)
  const [viewMode, setViewMode] = useState<"cards" | "table">("cards")

  const filtered = suppliers.filter(
    (s) =>
      s.name.toLowerCase().includes(search.toLowerCase()) ||
      s.contact.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input placeholder="Search suppliers..." className="pl-8 h-9 text-sm" value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <div className="flex items-center gap-1 border border-border rounded-md p-0.5">
            <Button variant={viewMode === "cards" ? "default" : "ghost"} size="sm" className="h-7 text-xs px-2.5" onClick={() => setViewMode("cards")}>Cards</Button>
            <Button variant={viewMode === "table" ? "default" : "ghost"} size="sm" className="h-7 text-xs px-2.5" onClick={() => setViewMode("table")}>Table</Button>
          </div>
        </div>
        {hasPermission("manage_suppliers") && (
          <Dialog open={isAddOpen} onOpenChange={setIsAddOpen}>
            <DialogTrigger asChild>
              <Button size="sm" className="h-9 gap-1.5"><Plus className="size-4" />Add Supplier</Button>
            </DialogTrigger>
            <DialogContent className="max-w-lg">
              <DialogHeader><DialogTitle>Add New Supplier</DialogTitle></DialogHeader>
              <SupplierForm
                onSubmit={async (supplier) => {
                  try {
                    await addSupplierPersisted(supplier)
                    setIsAddOpen(false)
                  } catch (error) {
                    console.error("Failed to add supplier", error)
                    window.alert("Unable to add supplier right now. Please try again.")
                  }
                }}
              />
            </DialogContent>
          </Dialog>
        )}
      </div>

      {viewMode === "cards" ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filtered.map((supplier) => {
            const itemCount = getItemsBySupplier(supplier.id).length
            const activeOrders = state.purchaseOrders.filter(
              (o) => o.supplierId === supplier.id && o.status !== "Delivered" && o.status !== "Cancelled"
            ).length
            return (
              <Card key={supplier.id} className="hover:shadow-md transition-shadow">
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between">
                    <CardTitle className="text-sm font-semibold text-foreground">{supplier.name}</CardTitle>
                    {hasPermission("manage_suppliers") && (
                      <Dialog open={editSupplier?.id === supplier.id} onOpenChange={(open) => !open && setEditSupplier(null)}>
                        <DialogTrigger asChild>
                          <Button variant="ghost" size="icon" className="size-7" onClick={() => setEditSupplier(supplier)}>
                            <Pencil className="size-3.5" />
                          </Button>
                        </DialogTrigger>
                        <DialogContent className="max-w-lg">
                          <DialogHeader><DialogTitle>Edit Supplier</DialogTitle></DialogHeader>
                          <SupplierForm
                            defaultValues={supplier}
                            onSubmit={async (updated) => {
                              try {
                                await updateSupplierPersisted(updated)
                                setEditSupplier(null)
                              } catch (error) {
                                console.error("Failed to update supplier", error)
                                window.alert("Unable to update supplier right now. Please try again.")
                              }
                            }}
                          />
                        </DialogContent>
                      </Dialog>
                    )}
                  </div>
                  <div className="flex items-center gap-1">
                    {Array.from({ length: 5 }).map((_, i) => (
                      <Star key={i} className={`size-3 ${i < Math.floor(supplier.rating) ? "fill-warning text-warning" : "text-muted"}`} />
                    ))}
                    <span className="ml-1 text-xs text-muted-foreground">{supplier.rating}</span>
                  </div>
                </CardHeader>
                <CardContent className="flex flex-col gap-3">
                  <div className="flex flex-col gap-1.5 text-xs">
                    <div className="flex items-center gap-2 text-muted-foreground">
                      <Mail className="size-3 shrink-0" />
                      <span className="truncate">{supplier.email}</span>
                    </div>
                    <div className="flex items-center gap-2 text-muted-foreground">
                      <Phone className="size-3 shrink-0" />
                      <span>{supplier.phone}</span>
                    </div>
                    <div className="flex items-center gap-2 text-muted-foreground">
                      <MapPin className="size-3 shrink-0" />
                      <span className="truncate">{supplier.address}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 pt-1 border-t border-border">
                    <Badge variant="outline" className="text-[10px] gap-1">
                      <Package className="size-3" />{itemCount} items
                    </Badge>
                    {activeOrders > 0 && (
                      <Badge variant="outline" className="text-[10px] border-primary/30 text-primary">
                        {activeOrders} active orders
                      </Badge>
                    )}
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      ) : (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-xs">Supplier</TableHead>
                  <TableHead className="text-xs">Contact</TableHead>
                  <TableHead className="text-xs">Email</TableHead>
                  <TableHead className="text-xs">Phone</TableHead>
                  <TableHead className="text-xs">Rating</TableHead>
                  <TableHead className="text-xs text-right">Items</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((supplier) => (
                  <TableRow key={supplier.id}>
                    <TableCell className="text-sm font-medium text-foreground">{supplier.name}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{supplier.contact}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{supplier.email}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{supplier.phone}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        <Star className="size-3 fill-warning text-warning" />
                        <span className="text-xs font-medium text-foreground">{supplier.rating}</span>
                      </div>
                    </TableCell>
                    <TableCell className="text-right text-xs font-medium text-foreground">{supplier.itemsSupplied}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

function SupplierForm({ defaultValues, onSubmit }: { defaultValues?: Supplier; onSubmit: (s: Supplier) => void | Promise<void> }) {
  const [form, setForm] = useState<Partial<Supplier>>(
    defaultValues ?? {
      id: "",
      name: "",
      contact: "",
      email: "",
      phone: "",
      address: "",
      rating: 4.0,
      itemsSupplied: 0,
    }
  )

  const update = (field: string, value: string | number) => setForm((prev) => ({ ...prev, [field]: value }))

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    void onSubmit({
      ...(form as Supplier),
      id: form.id || `s-${crypto.randomUUID().slice(0, 8)}`,
    })
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div className="flex flex-col gap-1.5">
        <Label className="text-xs">Company Name</Label>
        <Input className="h-9 text-sm" value={form.name ?? ""} onChange={(e) => update("name", e.target.value)} required />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="flex flex-col gap-1.5">
          <Label className="text-xs">Contact Person</Label>
          <Input className="h-9 text-sm" value={form.contact ?? ""} onChange={(e) => update("contact", e.target.value)} required />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label className="text-xs">Phone</Label>
          <Input className="h-9 text-sm" value={form.phone ?? ""} onChange={(e) => update("phone", e.target.value)} required />
        </div>
      </div>
      <div className="flex flex-col gap-1.5">
        <Label className="text-xs">Email</Label>
        <Input className="h-9 text-sm" type="email" value={form.email ?? ""} onChange={(e) => update("email", e.target.value)} required />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label className="text-xs">Address</Label>
        <Input className="h-9 text-sm" value={form.address ?? ""} onChange={(e) => update("address", e.target.value)} />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label className="text-xs">Rating (1-5)</Label>
        <Input className="h-9 text-sm" type="number" min={1} max={5} step={0.1} value={form.rating ?? 4} onChange={(e) => update("rating", Number(e.target.value))} />
      </div>
      <DialogFooter>
        <DialogClose asChild><Button type="button" variant="outline" size="sm">Cancel</Button></DialogClose>
        <Button type="submit" size="sm">{defaultValues ? "Update" : "Add"} Supplier</Button>
      </DialogFooter>
    </form>
  )
}
