"use client"

import { useState } from "react"
import { DashboardLayout } from "@/components/dashboard-layout"
import { OrderStatusBadge } from "@/components/stock-status-badge"
import { useInventory } from "@/lib/inventory-context"
import { formatCurrency, formatDate } from "@/lib/utils"
import { OrderStatus, type PurchaseOrder, type PurchaseOrderItem } from "@/lib/types"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
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
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  Plus,
  Search,
  ChevronDown,
  Check,
  X,
  Truck,
  Clock,
  Package,
  DollarSign,
} from "lucide-react"
import { StatsCard } from "@/components/stats-card"

export default function OrdersPage() {
  return (
    <DashboardLayout title="Purchase Orders">
      <OrdersContent />
    </DashboardLayout>
  )
}

function OrdersContent() {
  const {
    state,
    getSupplierById,
    hasPermission,
    addOrderPersisted,
    updateOrderStatusPersisted,
  } = useInventory()
  const { purchaseOrders } = state
  const [search, setSearch] = useState("")
  const [statusFilter, setStatusFilter] = useState<string>("all")
  const [isAddOpen, setIsAddOpen] = useState(false)
  const [expandedOrder, setExpandedOrder] = useState<string | null>(null)

  const filtered = purchaseOrders.filter((o) => {
    const supplier = getSupplierById(o.supplierId)
    const matchesSearch =
      o.id.toLowerCase().includes(search.toLowerCase()) ||
      supplier?.name.toLowerCase().includes(search.toLowerCase())
    const matchesStatus = statusFilter === "all" || o.status === statusFilter
    return matchesSearch && matchesStatus
  })

  const totalValue = purchaseOrders.reduce((sum, o) => sum + o.totalAmount, 0)
  const pendingCount = purchaseOrders.filter((o) => o.status === OrderStatus.Pending).length
  const shippedCount = purchaseOrders.filter((o) => o.status === OrderStatus.Shipped).length

  const handleStatusChange = async (orderId: string, newStatus: OrderStatus) => {
    const res = await updateOrderStatusPersisted(orderId, newStatus)
    if (!res.ok) {
      window.alert(res.error ?? "Unable to update order status right now. Please try again.")
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatsCard title="Total Orders" value={purchaseOrders.length} icon={Package} />
        <StatsCard title="Pending" value={pendingCount} icon={Clock} variant="warning" />
        <StatsCard title="In Transit" value={shippedCount} icon={Truck} variant="default" />
        <StatsCard title="Total Value" value={formatCurrency(totalValue)} icon={DollarSign} variant="success" />
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input placeholder="Search orders..." className="pl-8 h-9 text-sm" value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="h-9 w-36 text-sm"><SelectValue placeholder="Status" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Status</SelectItem>
              {Object.values(OrderStatus).map((s) => (
                <SelectItem key={s} value={s}>{s}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {hasPermission("create_order") && (
          <Dialog open={isAddOpen} onOpenChange={setIsAddOpen}>
            <DialogTrigger asChild>
              <Button size="sm" className="h-9 gap-1.5"><Plus className="size-4" />New Order</Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
              <DialogHeader><DialogTitle>Create Purchase Order</DialogTitle></DialogHeader>
              <OrderForm
                suppliers={state.suppliers}
                items={state.items}
                onSubmit={async (order) => {
                  const res = await addOrderPersisted(order)
                  if (res.ok) {
                    setIsAddOpen(false)
                  } else {
                    window.alert(res.error ?? "Unable to create order right now. Please try again.")
                  }
                }}
              />
            </DialogContent>
          </Dialog>
        )}
      </div>

      {/* Orders Table */}
      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-8 text-xs" />
                <TableHead className="text-xs">Order ID</TableHead>
                <TableHead className="text-xs">Supplier</TableHead>
                <TableHead className="text-xs">Items</TableHead>
                <TableHead className="text-xs">Order Date</TableHead>
                <TableHead className="text-xs">Expected</TableHead>
                <TableHead className="text-xs">Status</TableHead>
                <TableHead className="text-xs text-right">Total</TableHead>
                {hasPermission("approve_order") && <TableHead className="text-xs text-right">Actions</TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={9} className="h-24 text-center text-sm text-muted-foreground">
                    No orders found.
                  </TableCell>
                </TableRow>
              ) : (
                filtered.map((order) => {
                  const supplier = getSupplierById(order.supplierId)
                  const isExpanded = expandedOrder === order.id
                  return (
                    <Collapsible key={order.id} asChild open={isExpanded} onOpenChange={() => setExpandedOrder(isExpanded ? null : order.id)}>
                      <>
                        <TableRow className="cursor-pointer hover:bg-muted/50">
                          <TableCell>
                            <CollapsibleTrigger asChild>
                              <Button variant="ghost" size="icon" className="size-6">
                                <ChevronDown className={`size-3.5 transition-transform ${isExpanded ? "rotate-180" : ""}`} />
                              </Button>
                            </CollapsibleTrigger>
                          </TableCell>
                          <TableCell className="font-mono text-xs font-medium text-foreground">{order.id.toUpperCase()}</TableCell>
                          <TableCell className="text-sm text-foreground">{supplier?.name ?? "Unknown"}</TableCell>
                          <TableCell className="text-xs text-muted-foreground">{order.items.length} item{order.items.length > 1 ? "s" : ""}</TableCell>
                          <TableCell className="text-xs text-muted-foreground">{formatDate(order.orderDate)}</TableCell>
                          <TableCell className="text-xs text-muted-foreground">{formatDate(order.expectedDelivery)}</TableCell>
                          <TableCell><OrderStatusBadge status={order.status} /></TableCell>
                          <TableCell className="text-right text-sm font-semibold text-foreground">{formatCurrency(order.totalAmount)}</TableCell>
                          {hasPermission("approve_order") && (
                            <TableCell className="text-right">
                              <div className="flex items-center justify-end gap-1">
                                {order.status === OrderStatus.Pending && (
                                  <>
                                    <Button variant="ghost" size="icon" className="size-7 text-success hover:text-success" onClick={() => handleStatusChange(order.id, OrderStatus.Approved)}>
                                      <Check className="size-3.5" />
                                      <span className="sr-only">Approve</span>
                                    </Button>
                                    <Button variant="ghost" size="icon" className="size-7 text-destructive hover:text-destructive" onClick={() => handleStatusChange(order.id, OrderStatus.Cancelled)}>
                                      <X className="size-3.5" />
                                      <span className="sr-only">Cancel</span>
                                    </Button>
                                  </>
                                )}
                                {order.status === OrderStatus.Approved && (
                                  <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => handleStatusChange(order.id, OrderStatus.Shipped)}>
                                    Mark Shipped
                                  </Button>
                                )}
                                {order.status === OrderStatus.Shipped && (
                                  <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => handleStatusChange(order.id, OrderStatus.Delivered)}>
                                    Mark Delivered
                                  </Button>
                                )}
                              </div>
                            </TableCell>
                          )}
                        </TableRow>
                        <CollapsibleContent asChild>
                          <TableRow className="bg-muted/30">
                            <TableCell colSpan={9} className="p-4">
                              <div className="rounded-md border border-border overflow-hidden">
                                <Table>
                                  <TableHeader>
                                    <TableRow>
                                      <TableHead className="text-[11px]">Item</TableHead>
                                      <TableHead className="text-[11px]">Quantity</TableHead>
                                      <TableHead className="text-[11px]">Unit Price</TableHead>
                                      <TableHead className="text-[11px] text-right">Subtotal</TableHead>
                                    </TableRow>
                                  </TableHeader>
                                  <TableBody>
                                    {order.items.map((oi, idx) => (
                                      <TableRow key={idx}>
                                        <TableCell className="text-xs text-foreground">{oi.itemName}</TableCell>
                                        <TableCell className="text-xs text-muted-foreground">{oi.quantity.toLocaleString()}</TableCell>
                                        <TableCell className="text-xs font-mono text-muted-foreground">{formatCurrency(oi.unitPrice)}</TableCell>
                                        <TableCell className="text-right text-xs font-semibold text-foreground">{formatCurrency(oi.quantity * oi.unitPrice)}</TableCell>
                                      </TableRow>
                                    ))}
                                  </TableBody>
                                </Table>
                              </div>
                            </TableCell>
                          </TableRow>
                        </CollapsibleContent>
                      </>
                    </Collapsible>
                  )
                })
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}

function OrderForm({
  suppliers,
  items: allItems,
  onSubmit,
}: {
  suppliers: { id: string; name: string }[]
  items: { id: string; name: string; unitPrice: number }[]
  onSubmit: (order: PurchaseOrder) => void | Promise<void>
}) {
  const [supplierId, setSupplierId] = useState(suppliers[0]?.id ?? "")
  const [orderItems, setOrderItems] = useState<PurchaseOrderItem[]>([])
  const [selectedItem, setSelectedItem] = useState("")
  const [qty, setQty] = useState(1)

  const addItem = () => {
    const item = allItems.find((i) => i.id === selectedItem)
    if (!item || orderItems.some((oi) => oi.itemId === selectedItem)) return
    setOrderItems([...orderItems, { itemId: item.id, itemName: item.name, quantity: qty, unitPrice: item.unitPrice }])
    setSelectedItem("")
    setQty(1)
  }

  const removeItem = (idx: number) => {
    setOrderItems(orderItems.filter((_, i) => i !== idx))
  }

  const total = orderItems.reduce((sum, oi) => sum + oi.quantity * oi.unitPrice, 0)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (orderItems.length === 0) return
    const orderDate = new Date()
    const expectedDelivery = new Date(orderDate)
    expectedDelivery.setDate(orderDate.getDate() + 14)

    void onSubmit({
      id: `po-${crypto.randomUUID().slice(0, 8)}`,
      supplierId,
      items: orderItems,
      status: OrderStatus.Pending,
      orderDate: orderDate.toISOString().split("T")[0],
      expectedDelivery: expectedDelivery.toISOString().split("T")[0],
      totalAmount: total,
    })
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div className="flex flex-col gap-1.5">
        <Label className="text-xs">Supplier</Label>
        <Select value={supplierId} onValueChange={setSupplierId}>
          <SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger>
          <SelectContent>
            {suppliers.map((s) => (
              <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="flex flex-col gap-2">
        <Label className="text-xs">Add Items</Label>
        <div className="flex items-center gap-2">
          <Select value={selectedItem} onValueChange={setSelectedItem}>
            <SelectTrigger className="h-9 text-sm flex-1"><SelectValue placeholder="Select item" /></SelectTrigger>
            <SelectContent>
              {allItems.map((i) => (
                <SelectItem key={i.id} value={i.id}>{i.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input className="h-9 w-20 text-sm" type="number" min={1} value={qty} onChange={(e) => setQty(Number(e.target.value))} />
          <Button type="button" size="sm" className="h-9" onClick={addItem} disabled={!selectedItem}>Add</Button>
        </div>
      </div>

      {orderItems.length > 0 && (
        <div className="rounded-md border border-border overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-[11px]">Item</TableHead>
                <TableHead className="text-[11px]">Qty</TableHead>
                <TableHead className="text-[11px]">Price</TableHead>
                <TableHead className="text-[11px] text-right">Subtotal</TableHead>
                <TableHead className="w-8" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {orderItems.map((oi, idx) => (
                <TableRow key={idx}>
                  <TableCell className="text-xs text-foreground">{oi.itemName}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">{oi.quantity}</TableCell>
                  <TableCell className="text-xs font-mono text-muted-foreground">{formatCurrency(oi.unitPrice)}</TableCell>
                  <TableCell className="text-right text-xs font-semibold text-foreground">{formatCurrency(oi.quantity * oi.unitPrice)}</TableCell>
                  <TableCell>
                    <Button variant="ghost" size="icon" className="size-6 text-destructive" onClick={() => removeItem(idx)}>
                      <X className="size-3" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              <TableRow>
                <TableCell colSpan={3} className="text-xs font-semibold text-foreground text-right">Total</TableCell>
                <TableCell className="text-right text-sm font-bold text-foreground">{formatCurrency(total)}</TableCell>
                <TableCell />
              </TableRow>
            </TableBody>
          </Table>
        </div>
      )}

      <DialogFooter>
        <DialogClose asChild><Button type="button" variant="outline" size="sm">Cancel</Button></DialogClose>
        <Button type="submit" size="sm" disabled={orderItems.length === 0}>Create Order</Button>
      </DialogFooter>
    </form>
  )
}
