"use client"

import { Bell, Search, Moon, Sun } from "lucide-react"
import { useTheme } from "next-themes"
import { useInventory } from "@/lib/inventory-context"
import { SidebarTrigger } from "@/components/ui/sidebar"
import { Separator } from "@/components/ui/separator"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { ScrollArea } from "@/components/ui/scroll-area"
import { AlertSeverity } from "@/lib/types"
import { formatDateTime } from "@/lib/utils"
import Link from "next/link"

export function AppHeader({ title }: { title: string }) {
  const { theme, setTheme } = useTheme()
  const { state, dispatch, getUnacknowledgedAlerts } = useInventory()
  const unacknowledged = getUnacknowledgedAlerts()

  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border bg-card px-4">
      <SidebarTrigger className="-ml-1" />
      <Separator orientation="vertical" className="mr-1 h-5" />

      <h1 className="text-sm font-semibold text-foreground">{title}</h1>

      <div className="ml-auto flex items-center gap-2">
        <div className="relative hidden md:block">
          <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search inventory..."
            className="h-8 w-64 pl-8 text-sm"
            value={state.searchQuery}
            onChange={(e) =>
              dispatch({ type: "SET_SEARCH_QUERY", payload: e.target.value })
            }
          />
        </div>

        <Popover>
          <PopoverTrigger asChild>
            <Button variant="ghost" size="icon" className="relative size-8">
              <Bell className="size-4" />
              {unacknowledged.length > 0 && (
                <span className="absolute -right-0.5 -top-0.5 flex size-4 items-center justify-center rounded-full bg-destructive text-[10px] font-bold text-primary-foreground">
                  {unacknowledged.length > 9 ? "9+" : unacknowledged.length}
                </span>
              )}
              <span className="sr-only">Notifications</span>
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-80 p-0" align="end">
            <div className="flex items-center justify-between border-b border-border px-4 py-3">
              <h3 className="text-sm font-semibold text-foreground">Alerts</h3>
              <Link href="/alerts" className="text-xs text-primary hover:underline">
                View all
              </Link>
            </div>
            <ScrollArea className="h-72">
              {unacknowledged.length === 0 ? (
                <p className="p-4 text-center text-sm text-muted-foreground">
                  No new alerts
                </p>
              ) : (
                <div className="flex flex-col">
                  {unacknowledged.slice(0, 8).map((alert) => (
                    <div
                      key={alert.id}
                      className="flex flex-col gap-1 border-b border-border px-4 py-3 last:border-0"
                    >
                      <div className="flex items-center gap-2">
                        <Badge
                          variant="outline"
                          className={
                            alert.severity === AlertSeverity.Critical
                              ? "border-destructive/30 bg-destructive/10 text-destructive text-[10px]"
                              : alert.severity === AlertSeverity.Warning
                                ? "border-warning/30 bg-warning/10 text-warning-foreground text-[10px]"
                                : "border-primary/30 bg-primary/10 text-primary text-[10px]"
                          }
                        >
                          {alert.severity}
                        </Badge>
                        <span className="text-[10px] text-muted-foreground">
                          {formatDateTime(alert.timestamp)}
                        </span>
                      </div>
                      <p className="text-xs text-foreground leading-relaxed">
                        {alert.message}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </ScrollArea>
          </PopoverContent>
        </Popover>

        <Button
          variant="ghost"
          size="icon"
          className="size-8"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
        >
          <Sun className="size-4 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
          <Moon className="absolute size-4 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
          <span className="sr-only">Toggle theme</span>
        </Button>

        <Separator orientation="vertical" className="h-5" />

        <div className="flex items-center gap-2">
          <div className="flex size-7 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground">
            {state.currentUser.avatar}
          </div>
          <div className="hidden flex-col md:flex">
            <span className="text-xs font-medium text-foreground leading-none">
              {state.currentUser.name}
            </span>
            <span className="text-[10px] text-muted-foreground">
              {state.currentUser.role}
            </span>
          </div>
        </div>
      </div>
    </header>
  )
}
