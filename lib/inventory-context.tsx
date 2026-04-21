"use client"

import React, { createContext, useContext, useReducer, type ReactNode } from "react"
import {
  type InventoryItem,
  type Supplier,
  type Department,
  type PurchaseOrder,
  type User,
  type Alert,
  type ActivityLog,
  StockStatus,
  Role,
} from "./types"
import {
  users as mockUsers,
} from "./mock-data"
import { getInventorySnapshot } from "./ml-api"
import {
  createInventoryOrder,
  createInventoryItem,
  createInventorySupplier,
  deleteInventoryItem,
  deleteInventorySupplier,
  updateInventoryOrderStatus,
  updateInventoryItem,
  updateInventorySupplier,
} from "./ml-api"

interface InventoryState {
  items: InventoryItem[]
  suppliers: Supplier[]
  departments: Department[]
  purchaseOrders: PurchaseOrder[]
  users: User[]
  alerts: Alert[]
  activityLogs: ActivityLog[]
  currentUser: User
  searchQuery: string
}

type Action =
  | { type: "HYDRATE_STATE"; payload: Partial<InventoryState> }
  | { type: "ADD_ITEM"; payload: InventoryItem }
  | { type: "UPDATE_ITEM"; payload: InventoryItem }
  | { type: "DELETE_ITEM"; payload: string }
  | { type: "ADD_SUPPLIER"; payload: Supplier }
  | { type: "UPDATE_SUPPLIER"; payload: Supplier }
  | { type: "DELETE_SUPPLIER"; payload: string }
  | { type: "ADD_ORDER"; payload: PurchaseOrder }
  | { type: "UPDATE_ORDER"; payload: PurchaseOrder }
  | { type: "ACKNOWLEDGE_ALERT"; payload: string }
  | { type: "ADD_ALERT"; payload: Alert }
  | { type: "ADD_LOG"; payload: ActivityLog }
  | { type: "SET_CURRENT_USER"; payload: User }
  | { type: "SET_SEARCH_QUERY"; payload: string }
  | { type: "UPDATE_DEPARTMENT"; payload: Department }

function inventoryReducer(state: InventoryState, action: Action): InventoryState {
  switch (action.type) {
    case "HYDRATE_STATE":
      return { ...state, ...action.payload }
    case "ADD_ITEM":
      return { ...state, items: [...state.items, action.payload] }
    case "UPDATE_ITEM":
      return {
        ...state,
        items: state.items.map((item) =>
          item.id === action.payload.id ? action.payload : item
        ),
      }
    case "DELETE_ITEM":
      return {
        ...state,
        items: state.items.filter((item) => item.id !== action.payload),
      }
    case "ADD_SUPPLIER":
      return { ...state, suppliers: [...state.suppliers, action.payload] }
    case "UPDATE_SUPPLIER":
      return {
        ...state,
        suppliers: state.suppliers.map((s) =>
          s.id === action.payload.id ? action.payload : s
        ),
      }
    case "DELETE_SUPPLIER":
      return {
        ...state,
        suppliers: state.suppliers.filter((s) => s.id !== action.payload),
      }
    case "ADD_ORDER":
      return { ...state, purchaseOrders: [...state.purchaseOrders, action.payload] }
    case "UPDATE_ORDER":
      return {
        ...state,
        purchaseOrders: state.purchaseOrders.map((o) =>
          o.id === action.payload.id ? action.payload : o
        ),
      }
    case "ACKNOWLEDGE_ALERT":
      return {
        ...state,
        alerts: state.alerts.map((a) =>
          a.id === action.payload ? { ...a, acknowledged: true } : a
        ),
      }
    case "ADD_ALERT":
      return { ...state, alerts: [action.payload, ...state.alerts] }
    case "ADD_LOG":
      return { ...state, activityLogs: [action.payload, ...state.activityLogs] }
    case "SET_CURRENT_USER":
      return { ...state, currentUser: action.payload }
    case "SET_SEARCH_QUERY":
      return { ...state, searchQuery: action.payload }
    case "UPDATE_DEPARTMENT":
      return {
        ...state,
        departments: state.departments.map((d) =>
          d.id === action.payload.id ? action.payload : d
        ),
      }
    default:
      return state
  }
}

interface InventoryContextType {
  state: InventoryState
  dispatch: React.Dispatch<Action>
  refreshSnapshot: () => Promise<void>
  addItemPersisted: (item: InventoryItem) => Promise<{ ok: boolean; error?: string }>
  updateItemPersisted: (item: InventoryItem) => Promise<{ ok: boolean; error?: string }>
  deleteItemPersisted: (id: string) => Promise<{ ok: boolean; error?: string }>
  addSupplierPersisted: (supplier: Supplier) => Promise<{ ok: boolean; error?: string }>
  updateSupplierPersisted: (supplier: Supplier) => Promise<{ ok: boolean; error?: string }>
  deleteSupplierPersisted: (id: string) => Promise<{ ok: boolean; error?: string }>
  addOrderPersisted: (order: PurchaseOrder) => Promise<{ ok: boolean; error?: string }>
  updateOrderStatusPersisted: (orderId: string, status: string) => Promise<{ ok: boolean; error?: string }>
  // Helpers
  getItemById: (id: string) => InventoryItem | undefined
  getSupplierById: (id: string) => Supplier | undefined
  getDepartmentById: (id: string) => Department | undefined
  getOrderById: (id: string) => PurchaseOrder | undefined
  getUserById: (id: string) => User | undefined
  getItemsByCategory: (category: string) => InventoryItem[]
  getItemsByDepartment: (departmentId: string) => InventoryItem[]
  getItemsBySupplier: (supplierId: string) => InventoryItem[]
  getLowStockItems: () => InventoryItem[]
  getExpiringItems: (days: number) => InventoryItem[]
  getExpiredItems: () => InventoryItem[]
  getUnacknowledgedAlerts: () => Alert[]
  hasPermission: (action: string) => boolean
}

const InventoryContext = createContext<InventoryContextType | null>(null)

const initialState: InventoryState = {
  items: [],
  suppliers: [],
  departments: [],
  purchaseOrders: [],
  users: mockUsers,
  alerts: [],
  activityLogs: [],
  currentUser: mockUsers[0],
  searchQuery: "",
}

export function InventoryProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(inventoryReducer, initialState)

  const refreshSnapshot = React.useCallback(async () => {
    const snapshot = await getInventorySnapshot()
    if (!snapshot) return
    dispatch({
      type: "HYDRATE_STATE",
      payload: {
        items: snapshot.items as InventoryItem[],
        suppliers: snapshot.suppliers as Supplier[],
        departments: snapshot.departments as Department[],
        purchaseOrders: snapshot.purchaseOrders as PurchaseOrder[],
        alerts: snapshot.alerts as Alert[],
        activityLogs: snapshot.activityLogs as ActivityLog[],
      },
    })
  }, [])

  React.useEffect(() => {
    void refreshSnapshot()
  }, [refreshSnapshot])

  const addItemPersisted = React.useCallback(async (item: InventoryItem) => {
    const res = await createInventoryItem(item)
    if (!res.ok || !res.data?.ok) {
      return { ok: false, error: res.error ?? res.data?.error ?? "Failed to create item" }
    }
    await refreshSnapshot()
    return { ok: true }
  }, [refreshSnapshot])

  const updateItemPersisted = React.useCallback(async (item: InventoryItem) => {
    const res = await updateInventoryItem(item.id, item)
    if (!res.ok || !res.data?.ok) {
      return { ok: false, error: res.error ?? res.data?.error ?? "Failed to update item" }
    }
    await refreshSnapshot()
    return { ok: true }
  }, [refreshSnapshot])

  const deleteItemPersisted = React.useCallback(async (id: string) => {
    const res = await deleteInventoryItem(id)
    if (!res.ok || !res.data?.ok) {
      return { ok: false, error: res.error ?? res.data?.error ?? "Failed to delete item" }
    }
    await refreshSnapshot()
    return { ok: true }
  }, [refreshSnapshot])

  const addSupplierPersisted = React.useCallback(async (supplier: Supplier) => {
    const res = await createInventorySupplier(supplier)
    if (!res.ok || !res.data?.ok) {
      return { ok: false, error: res.error ?? res.data?.error ?? "Failed to create supplier" }
    }
    await refreshSnapshot()
    return { ok: true }
  }, [refreshSnapshot])

  const updateSupplierPersisted = React.useCallback(async (supplier: Supplier) => {
    const res = await updateInventorySupplier(supplier.id, supplier)
    if (!res.ok || !res.data?.ok) {
      return { ok: false, error: res.error ?? res.data?.error ?? "Failed to update supplier" }
    }
    await refreshSnapshot()
    return { ok: true }
  }, [refreshSnapshot])

  const deleteSupplierPersisted = React.useCallback(async (id: string) => {
    const res = await deleteInventorySupplier(id)
    if (!res.ok || !res.data?.ok) {
      return { ok: false, error: res.error ?? res.data?.error ?? "Failed to delete supplier" }
    }
    await refreshSnapshot()
    return { ok: true }
  }, [refreshSnapshot])

  const addOrderPersisted = React.useCallback(async (order: PurchaseOrder) => {
    const res = await createInventoryOrder(order)
    if (!res.ok || !res.data?.ok) {
      return { ok: false, error: res.error ?? res.data?.error ?? "Failed to create order" }
    }
    await refreshSnapshot()
    return { ok: true }
  }, [refreshSnapshot])

  const updateOrderStatusPersisted = React.useCallback(async (orderId: string, status: string) => {
    const res = await updateInventoryOrderStatus(orderId, status)
    if (!res.ok || !res.data?.ok) {
      return { ok: false, error: res.error ?? res.data?.error ?? "Failed to update order status" }
    }
    await refreshSnapshot()
    return { ok: true }
  }, [refreshSnapshot])

  const getItemById = (id: string) => state.items.find((i) => i.id === id)
  const getSupplierById = (id: string) => state.suppliers.find((s) => s.id === id)
  const getDepartmentById = (id: string) => state.departments.find((d) => d.id === id)
  const getOrderById = (id: string) => state.purchaseOrders.find((o) => o.id === id)
  const getUserById = (id: string) => state.users.find((u) => u.id === id)

  const getItemsByCategory = (category: string) =>
    state.items.filter((i) => i.category === category)

  const getItemsByDepartment = (departmentId: string) =>
    state.items.filter((i) => i.departmentId === departmentId)

  const getItemsBySupplier = (supplierId: string) =>
    state.items.filter((i) => i.supplierId === supplierId)

  const getLowStockItems = () =>
    state.items.filter(
      (i) => i.status === StockStatus.LowStock || i.status === StockStatus.OutOfStock
    )

  const getExpiringItems = (days: number) => {
    const now = new Date()
    const cutoff = new Date(now.getTime() + days * 24 * 60 * 60 * 1000)
    return state.items.filter((i) => {
      if (i.expiryDate === "N/A") return false
      const expiry = new Date(i.expiryDate)
      return expiry > now && expiry <= cutoff
    })
  }

  const getExpiredItems = () =>
    state.items.filter((i) => i.status === StockStatus.Expired)

  const getUnacknowledgedAlerts = () =>
    state.alerts.filter((a) => !a.acknowledged)

  const hasPermission = (action: string): boolean => {
    const role = state.currentUser.role
    const permissions: Record<string, Role[]> = {
      "add_item": [Role.Admin, Role.Pharmacist],
      "edit_item": [Role.Admin, Role.Pharmacist],
      "delete_item": [Role.Admin],
      "manage_suppliers": [Role.Admin],
      "view_suppliers": [Role.Admin, Role.Pharmacist, Role.DepartmentHead],
      "create_order": [Role.Admin, Role.Pharmacist],
      "approve_order": [Role.Admin],
      "manage_departments": [Role.Admin],
      "transfer_items": [Role.Admin, Role.Pharmacist, Role.DepartmentHead],
      "view_all_reports": [Role.Admin],
      "view_department_reports": [Role.Admin, Role.DepartmentHead],
      "acknowledge_alerts": [Role.Admin, Role.Pharmacist, Role.Nurse, Role.DepartmentHead],
    }
    return permissions[action]?.includes(role) ?? false
  }

  return (
    <InventoryContext.Provider
      value={{
        state,
        dispatch,
        refreshSnapshot,
        addItemPersisted,
        updateItemPersisted,
        deleteItemPersisted,
        addSupplierPersisted,
        updateSupplierPersisted,
        deleteSupplierPersisted,
        addOrderPersisted,
        updateOrderStatusPersisted,
        getItemById,
        getSupplierById,
        getDepartmentById,
        getOrderById,
        getUserById,
        getItemsByCategory,
        getItemsByDepartment,
        getItemsBySupplier,
        getLowStockItems,
        getExpiringItems,
        getExpiredItems,
        getUnacknowledgedAlerts,
        hasPermission,
      }}
    >
      {children}
    </InventoryContext.Provider>
  )
}

export function useInventory() {
  const context = useContext(InventoryContext)
  if (!context) {
    throw new Error("useInventory must be used within an InventoryProvider")
  }
  return context
}
