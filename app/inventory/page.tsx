"use client"

import { useState, useMemo } from "react"
import { DashboardLayout } from "@/components/dashboard-layout"
import { StockStatusBadge } from "@/components/stock-status-badge"
import { useInventory } from "@/lib/inventory-context"
import { formatCurrency, formatDate, getDaysUntilExpiry, cn } from "@/lib/utils"
import { Category, StockStatus, type InventoryItem } from "@/lib/types"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import {
  Search,
  Plus,
  Eye,
  Pencil,
  Trash2,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
} from "lucide-react"
import Link from "next/link"

const ITEMS_PER_PAGE = 12

export default function InventoryPage() {
  return (
    <DashboardLayout title="Inventory Management">
      <InventoryContent />
    </DashboardLayout>
  )
}

function InventoryContent() {
  const { state, dispatch, getDepartmentById, hasPermission } = useInventory()
  const { items } = state

  const [search, setSearch] = useState("")
  const [categoryFilter, setCategoryFilter] = useState<string>("all")
  const [statusFilter, setStatusFilter] = useState<string>("all")
  const [sortField, setSortField] = useState<keyof InventoryItem>("name")
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc")
  const [page, setPage] = useState(1)
  const [editItem, setEditItem] = useState<InventoryItem | null>(null)
  const [isAddOpen, setIsAddOpen] = useState(false)

  const filtered = useMemo(() => {
    let result = [...items]

    if (search) {
      const q = search.toLowerCase()
      result = result.filter(
        (i) =>
          i.name.toLowerCase().includes(q) ||
          i.sku.toLowerCase().includes(q) ||
          i.batchNumber.toLowerCase().includes(q)
      )
    }

    if (categoryFilter !== "all") {
      result = result.filter((i) => i.category === categoryFilter)
    }

    if (statusFilter !== "all") {
      result = result.filter((i) => i.status === statusFilter)
    }

    result.sort((a, b) => {
      const aVal = a[sortField]
      const bVal = b[sortField]
      if (typeof aVal === "string" && typeof bVal === "string") {
        return sortDir === "asc" ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal)
      }
      if (typeof aVal === "number" && typeof bVal === "number") {
        return sortDir === "asc" ? aVal - bVal : bVal - aVal
      }
      return 0
    })

    return result
  }, [items, search, categoryFilter, statusFilter, sortField, sortDir])

  const totalPages = Math.ceil(filtered.length / ITEMS_PER_PAGE)
  const paged = filtered.slice((page - 1) * ITEMS_PER_PAGE, page * ITEMS_PER_PAGE)

  const toggleSort = (field: keyof InventoryItem) => {
    if (sortField === field) {
      setSortDir(sortDir === "asc" ? "desc" : "asc")
    } else {
      setSortField(field)
      setSortDir("asc")
    }
  }

  const handleDelete = (id: string) => {
    dispatch({ type: "DELETE_ITEM", payload: id })
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Filters */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-1 items-center gap-2">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search items, SKU, batch..."
              className="pl-8 h-9 text-sm"
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1) }}
            />
          </div>
          <Select value={categoryFilter} onValueChange={(v) => { setCategoryFilter(v); setPage(1) }}>
            <SelectTrigger className="h-9 w-40 text-sm">
              <SelectValue placeholder="Category" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Categories</SelectItem>
              {Object.values(Category).map((cat) => (
                <SelectItem key={cat} value={cat}>{cat}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setPage(1) }}>
            <SelectTrigger className="h-9 w-36 text-sm">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Status</SelectItem>
              {Object.values(StockStatus).map((s) => (
                <SelectItem key={s} value={s}>{s}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {hasPermission("add_item") && (
          <Dialog open={isAddOpen} onOpenChange={setIsAddOpen}>
            <DialogTrigger asChild>
              <Button size="sm" className="h-9 gap-1.5">
                <Plus className="size-4" />
                Add Item
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>Add New Inventory Item</DialogTitle>
              </DialogHeader>
              <InventoryForm
                onSubmit={(item) => {
                  dispatch({ type: "ADD_ITEM", payload: item })
                  setIsAddOpen(false)
                }}
                suppliers={state.suppliers}
                departments={state.departments}
              />
            </DialogContent>
          </Dialog>
        )}
      </div>

      {/* Category Quick Filters */}
      <div className="flex flex-wrap gap-1.5">
        <Badge
          variant={categoryFilter === "all" ? "default" : "outline"}
          className="cursor-pointer text-xs"
          onClick={() => { setCategoryFilter("all"); setPage(1) }}
        >
          All ({items.length})
        </Badge>
        {Object.values(Category).map((cat) => {
          const count = items.filter((i) => i.category === cat).length
          return (
            <Badge
              key={cat}
              variant={categoryFilter === cat ? "default" : "outline"}
              className="cursor-pointer text-xs"
              onClick={() => { setCategoryFilter(cat); setPage(1) }}
            >
              {cat} ({count})
            </Badge>
          )
        })}
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[250px]">
                    <button className="flex items-center gap-1 text-xs font-medium" onClick={() => toggleSort("name")}>
                      Item Name <ArrowUpDown className="size-3" />
                    </button>
                  </TableHead>
                  <TableHead className="text-xs">SKU</TableHead>
                  <TableHead className="text-xs">Category</TableHead>
                  <TableHead className="text-xs">
                    <button className="flex items-center gap-1" onClick={() => toggleSort("quantity")}>
                      Qty <ArrowUpDown className="size-3" />
                    </button>
                  </TableHead>
                  <TableHead className="text-xs">Status</TableHead>
                  <TableHead className="text-xs">Department</TableHead>
                  <TableHead className="text-xs">Expiry</TableHead>
                  <TableHead className="text-xs text-right">Unit Price</TableHead>
                  <TableHead className="text-xs text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {paged.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={9} className="h-24 text-center text-sm text-muted-foreground">
                      No items found matching your criteria.
                    </TableCell>
                  </TableRow>
                ) : (
                  paged.map((item) => {
                    const dept = getDepartmentById(item.departmentId)
                    const daysUntil = getDaysUntilExpiry(item.expiryDate)
                    return (
                      <TableRow key={item.id}>
                        <TableCell>
                          <div className="flex flex-col">
                            <span className="text-sm font-medium text-foreground">{item.name}</span>
                            <span className="text-[11px] text-muted-foreground">{item.batchNumber}</span>
                          </div>
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground font-mono">{item.sku}</TableCell>
                        <TableCell>
                          <Badge variant="outline" className="text-[10px]">{item.category}</Badge>
                        </TableCell>
                        <TableCell>
                          <span className={cn("text-sm font-semibold", item.quantity <= item.reorderLevel ? "text-destructive" : "text-foreground")}>
                            {item.quantity.toLocaleString()}
                          </span>
                          <span className="text-[10px] text-muted-foreground ml-1">{item.unit}</span>
                        </TableCell>
                        <TableCell>
                          <StockStatusBadge status={item.status} />
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">{dept?.name ?? "-"}</TableCell>
                        <TableCell>
                          {item.expiryDate === "N/A" ? (
                            <span className="text-xs text-muted-foreground">N/A</span>
                          ) : (
                            <div className="flex flex-col">
                              <span className="text-xs text-foreground">{formatDate(item.expiryDate)}</span>
                              {daysUntil !== null && daysUntil <= 30 && (
                                <span className={cn("text-[10px] font-medium", daysUntil <= 0 ? "text-destructive" : "text-warning-foreground")}>
                                  {daysUntil <= 0 ? "EXPIRED" : `${daysUntil}d remaining`}
                                </span>
                              )}
                            </div>
                          )}
                        </TableCell>
                        <TableCell className="text-right text-xs font-mono text-foreground">{formatCurrency(item.unitPrice)}</TableCell>
                        <TableCell>
                          <div className="flex items-center justify-end gap-1">
                            <Button variant="ghost" size="icon" className="size-7" asChild>
                              <Link href={`/inventory/${item.id}`}>
                                <Eye className="size-3.5" />
                                <span className="sr-only">View {item.name}</span>
                              </Link>
                            </Button>
                            {hasPermission("edit_item") && (
                              <Dialog open={editItem?.id === item.id} onOpenChange={(open) => !open && setEditItem(null)}>
                                <DialogTrigger asChild>
                                  <Button variant="ghost" size="icon" className="size-7" onClick={() => setEditItem(item)}>
                                    <Pencil className="size-3.5" />
                                    <span className="sr-only">Edit {item.name}</span>
                                  </Button>
                                </DialogTrigger>
                                <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
                                  <DialogHeader>
                                    <DialogTitle>Edit {item.name}</DialogTitle>
                                  </DialogHeader>
                                  <InventoryForm
                                    defaultValues={item}
                                    onSubmit={(updated) => {
                                      dispatch({ type: "UPDATE_ITEM", payload: updated })
                                      setEditItem(null)
                                    }}
                                    suppliers={state.suppliers}
                                    departments={state.departments}
                                  />
                                </DialogContent>
                              </Dialog>
                            )}
                            {hasPermission("delete_item") && (
                              <AlertDialog>
                                <AlertDialogTrigger asChild>
                                  <Button variant="ghost" size="icon" className="size-7 text-destructive hover:text-destructive">
                                    <Trash2 className="size-3.5" />
                                    <span className="sr-only">Delete {item.name}</span>
                                  </Button>
                                </AlertDialogTrigger>
                                <AlertDialogContent>
                                  <AlertDialogHeader>
                                    <AlertDialogTitle>Delete {item.name}?</AlertDialogTitle>
                                    <AlertDialogDescription>
                                      This will permanently remove this item from inventory. This action cannot be undone.
                                    </AlertDialogDescription>
                                  </AlertDialogHeader>
                                  <AlertDialogFooter>
                                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                                    <AlertDialogAction
                                      onClick={() => handleDelete(item.id)}
                                      className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                                    >
                                      Delete
                                    </AlertDialogAction>
                                  </AlertDialogFooter>
                                </AlertDialogContent>
                              </AlertDialog>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    )
                  })
                )}
              </TableBody>
            </Table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between border-t border-border px-4 py-3">
              <span className="text-xs text-muted-foreground">
                Showing {(page - 1) * ITEMS_PER_PAGE + 1}-{Math.min(page * ITEMS_PER_PAGE, filtered.length)} of {filtered.length} items
              </span>
              <div className="flex items-center gap-1">
                <Button variant="outline" size="icon" className="size-7" disabled={page === 1} onClick={() => setPage(page - 1)}>
                  <ChevronLeft className="size-3.5" />
                </Button>
                {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
                  <Button
                    key={p}
                    variant={p === page ? "default" : "outline"}
                    size="icon"
                    className="size-7 text-xs"
                    onClick={() => setPage(p)}
                  >
                    {p}
                  </Button>
                ))}
                <Button variant="outline" size="icon" className="size-7" disabled={page === totalPages} onClick={() => setPage(page + 1)}>
                  <ChevronRight className="size-3.5" />
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

// Inventory Form Component
interface InventoryFormProps {
  defaultValues?: InventoryItem
  onSubmit: (item: InventoryItem) => void
  suppliers: { id: string; name: string }[]
  departments: { id: string; name: string }[]
}

function InventoryForm({ defaultValues, onSubmit, suppliers, departments }: InventoryFormProps) {
  const [form, setForm] = useState<Partial<InventoryItem>>(
    defaultValues ?? {
      id: "",
      name: "",
      category: Category.Medicines,
      sku: "",
      quantity: 0,
      unit: "",
      reorderLevel: 0,
      unitPrice: 0,
      supplierId: suppliers[0]?.id ?? "",
      departmentId: departments[0]?.id ?? "",
      batchNumber: "",
      expiryDate: "",
      location: "",
      status: StockStatus.InStock,
      lastRestocked: new Date().toISOString().split("T")[0],
      notes: "",
    }
  )

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const item = {
      ...(form as InventoryItem),
      id: form.id || `i-${crypto.randomUUID().slice(0, 8)}`,
    }

    const status =
      item.quantity === 0
        ? StockStatus.OutOfStock
        : item.quantity <= item.reorderLevel
          ? StockStatus.LowStock
          : StockStatus.InStock

    onSubmit({ ...item, status })
  }

  const update = (field: string, value: string | number) => {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  return (
    <form onSubmit={handleSubmit} className="grid grid-cols-2 gap-4">
      <div className="col-span-2 flex flex-col gap-1.5">
        <Label className="text-xs">Item Name</Label>
        <Input className="h-9 text-sm" value={form.name ?? ""} onChange={(e) => update("name", e.target.value)} required />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label className="text-xs">Category</Label>
        <Select value={form.category} onValueChange={(v) => update("category", v)}>
          <SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger>
          <SelectContent>
            {Object.values(Category).map((c) => (
              <SelectItem key={c} value={c}>{c}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="flex flex-col gap-1.5">
        <Label className="text-xs">SKU</Label>
        <Input className="h-9 text-sm font-mono" value={form.sku ?? ""} onChange={(e) => update("sku", e.target.value)} required />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label className="text-xs">Quantity</Label>
        <Input className="h-9 text-sm" type="number" min={0} value={form.quantity ?? 0} onChange={(e) => update("quantity", Number(e.target.value))} required />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label className="text-xs">Unit</Label>
        <Input className="h-9 text-sm" value={form.unit ?? ""} onChange={(e) => update("unit", e.target.value)} required placeholder="e.g., Tablets, Vials, Units" />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label className="text-xs">Reorder Level</Label>
        <Input className="h-9 text-sm" type="number" min={0} value={form.reorderLevel ?? 0} onChange={(e) => update("reorderLevel", Number(e.target.value))} required />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label className="text-xs">Unit Price ($)</Label>
        <Input className="h-9 text-sm" type="number" step="0.01" min={0} value={form.unitPrice ?? 0} onChange={(e) => update("unitPrice", Number(e.target.value))} required />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label className="text-xs">Supplier</Label>
        <Select value={form.supplierId} onValueChange={(v) => update("supplierId", v)}>
          <SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger>
          <SelectContent>
            {suppliers.map((s) => (
              <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="flex flex-col gap-1.5">
        <Label className="text-xs">Department</Label>
        <Select value={form.departmentId} onValueChange={(v) => update("departmentId", v)}>
          <SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger>
          <SelectContent>
            {departments.map((d) => (
              <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="flex flex-col gap-1.5">
        <Label className="text-xs">Batch Number</Label>
        <Input className="h-9 text-sm font-mono" value={form.batchNumber ?? ""} onChange={(e) => update("batchNumber", e.target.value)} />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label className="text-xs">Expiry Date</Label>
        <Input className="h-9 text-sm" type="date" value={form.expiryDate === "N/A" ? "" : form.expiryDate ?? ""} onChange={(e) => update("expiryDate", e.target.value || "N/A")} />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label className="text-xs">Location</Label>
        <Input className="h-9 text-sm" value={form.location ?? ""} onChange={(e) => update("location", e.target.value)} />
      </div>
      <div className="col-span-2 flex flex-col gap-1.5">
        <Label className="text-xs">Notes</Label>
        <Textarea className="text-sm min-h-16" value={form.notes ?? ""} onChange={(e) => update("notes", e.target.value)} />
      </div>
      <DialogFooter className="col-span-2">
        <DialogClose asChild>
          <Button type="button" variant="outline" size="sm">Cancel</Button>
        </DialogClose>
        <Button type="submit" size="sm">{defaultValues ? "Update Item" : "Add Item"}</Button>
      </DialogFooter>
    </form>
  )
}
