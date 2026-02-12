export enum Category {
  Medicines = "Medicines",
  Equipment = "Equipment",
  Surgical = "Surgical Supplies",
  PPE = "PPE",
  LabReagents = "Lab Reagents",
  BloodBank = "Blood Bank",
}

export enum StockStatus {
  InStock = "In Stock",
  LowStock = "Low Stock",
  OutOfStock = "Out of Stock",
  Expired = "Expired",
}

export enum Role {
  Admin = "Admin",
  Pharmacist = "Pharmacist",
  Nurse = "Nurse",
  DepartmentHead = "Department Head",
}

export enum OrderStatus {
  Pending = "Pending",
  Approved = "Approved",
  Shipped = "Shipped",
  Delivered = "Delivered",
  Cancelled = "Cancelled",
}

export enum AlertType {
  LowStock = "Low Stock",
  ExpiringSoon = "Expiring Soon",
  Expired = "Expired",
  OrderUpdate = "Order Update",
}

export enum AlertSeverity {
  Critical = "Critical",
  Warning = "Warning",
  Info = "Info",
}

export interface InventoryItem {
  id: string
  name: string
  category: Category
  sku: string
  quantity: number
  unit: string
  reorderLevel: number
  unitPrice: number
  supplierId: string
  departmentId: string
  batchNumber: string
  expiryDate: string
  location: string
  status: StockStatus
  lastRestocked: string
  notes: string
}

export interface Supplier {
  id: string
  name: string
  contact: string
  email: string
  phone: string
  address: string
  rating: number
  itemsSupplied: number
}

export interface Department {
  id: string
  name: string
  head: string
  budget: number
  spent: number
}

export interface PurchaseOrderItem {
  itemId: string
  itemName: string
  quantity: number
  unitPrice: number
}

export interface PurchaseOrder {
  id: string
  supplierId: string
  items: PurchaseOrderItem[]
  status: OrderStatus
  orderDate: string
  expectedDelivery: string
  totalAmount: number
}

export interface User {
  id: string
  name: string
  email: string
  role: Role
  departmentId: string
  avatar: string
}

export interface Alert {
  id: string
  type: AlertType
  severity: AlertSeverity
  message: string
  itemId?: string
  timestamp: string
  acknowledged: boolean
}

export interface ActivityLog {
  id: string
  action: string
  userId: string
  itemId?: string
  timestamp: string
  details: string
}
