"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  LayoutDashboard,
  Package,
  Truck,
  Building2,
  ClipboardList,
  Bell,
  FileBarChart,
  Activity,
  ChevronUp,
} from "lucide-react"
import { useInventory } from "@/lib/inventory-context"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuItem,
  SidebarMenuButton,
} from "@/components/ui/sidebar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"

const navItems = [
  { title: "Dashboard", url: "/", icon: LayoutDashboard },
  { title: "Inventory", url: "/inventory", icon: Package },
  { title: "Suppliers", url: "/suppliers", icon: Truck },
  { title: "Departments", url: "/departments", icon: Building2 },
  { title: "Purchase Orders", url: "/orders", icon: ClipboardList },
  { title: "Alerts", url: "/alerts", icon: Bell },
  { title: "Reports", url: "/reports", icon: FileBarChart },
]

export function AppSidebar() {
  const pathname = usePathname()
  const { state, getUnacknowledgedAlerts } = useInventory()
  const { currentUser } = state
  const unacknowledgedCount = getUnacknowledgedAlerts().length

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild>
              <Link href="/">
                <div className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                  <Activity className="size-4" />
                </div>
                <div className="flex flex-col gap-0.5 leading-none">
                  <span className="font-semibold">AHIMP</span>
                  <span className="text-xs text-sidebar-foreground/60">Hospital Inventory</span>
                </div>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Navigation</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => {
                const isActive =
                  item.url === "/"
                    ? pathname === "/"
                    : pathname.startsWith(item.url)
                return (
                  <SidebarMenuItem key={item.title}>
                    <SidebarMenuButton
                      asChild
                      isActive={isActive}
                      tooltip={item.title}
                    >
                      <Link href={item.url}>
                        <item.icon />
                        <span>{item.title}</span>
                      </Link>
                    </SidebarMenuButton>
                    {item.title === "Alerts" && unacknowledgedCount > 0 && (
                      <SidebarMenuBadge>
                        <Badge variant="destructive" className="h-5 min-w-5 rounded-full px-1 text-[10px]">
                          {unacknowledgedCount}
                        </Badge>
                      </SidebarMenuBadge>
                    )}
                  </SidebarMenuItem>
                )
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <SidebarMenuButton
                  size="lg"
                  className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
                >
                  <Avatar className="size-8 rounded-lg">
                    <AvatarFallback className="rounded-lg bg-primary/20 text-xs font-medium text-sidebar-foreground">
                      {currentUser.avatar}
                    </AvatarFallback>
                  </Avatar>
                  <div className="grid flex-1 text-left text-sm leading-tight">
                    <span className="truncate font-semibold">{currentUser.name}</span>
                    <span className="truncate text-xs text-sidebar-foreground/60">{currentUser.role}</span>
                  </div>
                  <ChevronUp className="ml-auto size-4" />
                </SidebarMenuButton>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                className="w-[--radix-dropdown-menu-trigger-width] min-w-56 rounded-lg"
                side="top"
                align="end"
                sideOffset={4}
              >
                {state.users.map((user) => (
                  <DropdownMenuItem
                    key={user.id}
                    className="gap-3 p-2"
                    onSelect={() => {}}
                  >
                    <RoleSwitchItem user={user} />
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  )
}

function RoleSwitchItem({ user }: { user: { id: string; name: string; role: string; avatar: string } }) {
  const { dispatch, state } = useInventory()
  const fullUser = state.users.find((u) => u.id === user.id)
  const isActive = state.currentUser.id === user.id

  return (
    <button
      className="flex w-full items-center gap-3"
      onClick={() => {
        if (fullUser) {
          dispatch({ type: "SET_CURRENT_USER", payload: fullUser })
        }
      }}
    >
      <Avatar className="size-8 rounded-lg">
        <AvatarFallback className={cn("rounded-lg text-xs font-medium", isActive ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground")}>
          {user.avatar}
        </AvatarFallback>
      </Avatar>
      <div className="grid flex-1 text-left text-sm leading-tight">
        <span className="truncate font-medium">{user.name}</span>
        <span className="truncate text-xs text-muted-foreground">{user.role}</span>
      </div>
      {isActive && (
        <div className="size-2 rounded-full bg-primary" />
      )}
    </button>
  )
}

import { cn } from "@/lib/utils"
