"use client"

import { useState, useRef, useEffect } from "react"
import { motion, AnimatePresence } from "motion/react"
import {
  Bell,
  Rocket,
  CreditCard,
  ShieldAlert,
  LifeBuoy,
  FileText,
  Info,
  CheckCheck,
  Check,
  Inbox,
} from "lucide-react"
import { cn } from "@/lib/utils"
import type { PortalNotification } from "@/types"

// ─── Type Config ────────────────────────────────────────────

const TYPE_CONFIG: Record<
  PortalNotification["type"],
  { icon: React.ElementType; color: string; bg: string }
> = {
  release: { icon: Rocket, color: "text-blue-500", bg: "bg-blue-500/10" },
  billing: { icon: CreditCard, color: "text-emerald-500", bg: "bg-emerald-500/10" },
  security: { icon: ShieldAlert, color: "text-amber-500", bg: "bg-amber-500/10" },
  support: { icon: LifeBuoy, color: "text-purple-500", bg: "bg-purple-500/10" },
  doc_update: { icon: FileText, color: "text-cyan-500", bg: "bg-cyan-500/10" },
  system: { icon: Info, color: "text-muted-foreground", bg: "bg-muted" },
}

// ─── Helpers ────────────────────────────────────────────────

function timeAgo(dateString: string): string {
  const now = Date.now()
  const then = new Date(dateString).getTime()
  const seconds = Math.floor((now - then) / 1000)

  if (seconds < 60) return "just now"
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}d ago`
  return new Date(dateString).toLocaleDateString("en-US", { month: "short", day: "numeric" })
}

// ─── Props ──────────────────────────────────────────────────

interface NotificationCenterProps {
  notifications: PortalNotification[]
  unreadCount: number
  onMarkRead: (id: string) => void
  onMarkAllRead: () => void
  loading?: boolean
  className?: string
}

// ─── Component ──────────────────────────────────────────────

export function NotificationCenter({
  notifications,
  unreadCount,
  onMarkRead,
  onMarkAllRead,
  loading = false,
  className,
}: NotificationCenterProps) {
  const [open, setOpen] = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)

  // Close on click outside
  useEffect(() => {
    if (!open) return

    function handleClickOutside(e: MouseEvent) {
      if (
        panelRef.current &&
        !panelRef.current.contains(e.target as Node) &&
        buttonRef.current &&
        !buttonRef.current.contains(e.target as Node)
      ) {
        setOpen(false)
      }
    }

    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [open])

  // Close on Escape
  useEffect(() => {
    if (!open) return

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false)
    }

    document.addEventListener("keydown", handleKeyDown)
    return () => document.removeEventListener("keydown", handleKeyDown)
  }, [open])

  const hasUnread = unreadCount > 0
  const sortedNotifications = [...notifications].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  )

  return (
    <div className={cn("relative", className)}>
      {/* Bell button */}
      <button
        ref={buttonRef}
        onClick={() => setOpen((prev) => !prev)}
        className="relative flex h-9 w-9 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
        aria-label={`Notifications${hasUnread ? ` (${unreadCount} unread)` : ""}`}
        aria-expanded={open}
        aria-haspopup="true"
      >
        <Bell className="h-5 w-5" />
        {hasUnread && (
          <span className="absolute -right-0.5 -top-0.5 flex items-center justify-center">
            <span className="absolute h-2.5 w-2.5 animate-ping rounded-full bg-red-500 opacity-75" />
            <span className="relative flex h-2.5 w-2.5 items-center justify-center rounded-full bg-red-500 text-[8px] font-bold text-white">
              {unreadCount > 9 ? "9+" : unreadCount}
            </span>
          </span>
        )}
      </button>

      {/* Dropdown panel */}
      <AnimatePresence>
        {open && (
          <motion.div
            ref={panelRef}
            initial={{ opacity: 0, scale: 0.95, y: -4 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -4 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
            className="absolute right-0 top-full z-50 mt-2 w-80 sm:w-96 origin-top-right"
          >
            <div className="overflow-hidden rounded-xl border border-border/50 bg-background shadow-xl shadow-black/10 dark:border-border/30 dark:bg-zinc-900/95 dark:backdrop-blur-2xl">
              {/* Header */}
              <div className="flex items-center justify-between border-b border-border/50 px-4 py-3 dark:border-border/30">
                <h3 className="text-sm font-semibold">Notifications</h3>
                {hasUnread && !loading && (
                  <button
                    onClick={onMarkAllRead}
                    className="flex items-center gap-1 text-xs font-medium text-primary hover:text-primary/80 transition-colors"
                  >
                    <CheckCheck className="h-3.5 w-3.5" />
                    Mark all read
                  </button>
                )}
              </div>

              {/* Content */}
              <div className="max-h-[min(60vh, 420px)] overflow-y-auto">
                {/* Loading state */}
                {loading && (
                  <div className="flex flex-col gap-3 p-4">
                    {Array.from({ length: 4 }).map((_, i) => (
                      <div key={i} className="flex gap-3 animate-pulse">
                        <div className="h-8 w-8 shrink-0 rounded-lg bg-muted" />
                        <div className="flex-1 space-y-2">
                          <div className="h-3 w-3/4 rounded bg-muted" />
                          <div className="h-2.5 w-full rounded bg-muted" />
                          <div className="h-2 w-1/4 rounded bg-muted" />
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Empty state */}
                {!loading && sortedNotifications.length === 0 && (
                  <div className="flex flex-col items-center justify-center py-12 text-center">
                    <Inbox className="mb-3 h-10 w-10 text-muted-foreground/40" />
                    <p className="text-sm font-medium">No new notifications</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      We'll let you know when something arrives.
                    </p>
                  </div>
                )}

                {/* Notification list */}
                {!loading &&
                  sortedNotifications.map((notification) => {
                    const typeConfig = TYPE_CONFIG[notification.type] || TYPE_CONFIG.system
                    const Icon = typeConfig.icon

                    return (
                      <motion.div
                        key={notification.id}
                        initial={{ opacity: 0, y: 4 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.15 }}
                        className={cn(
                          "group flex gap-3 border-b border-border/30 px-4 py-3 transition-colors last:border-b-0 hover:bg-muted/30",
                          !notification.read && "bg-primary/[0.02]"
                        )}
                      >
                        {/* Type icon */}
                        <div
                          className={cn(
                            "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg",
                            typeConfig.bg
                          )}
                        >
                          <Icon className={cn("h-4 w-4", typeConfig.color)} />
                        </div>

                        {/* Content */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-start justify-between gap-2">
                            <p className="text-sm font-medium truncate">{notification.title}</p>
                            {!notification.read && (
                              <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-primary" />
                            )}
                          </div>
                          <p className="mt-0.5 text-xs text-muted-foreground line-clamp-2">
                            {notification.message}
                          </p>
                          <div className="mt-1.5 flex items-center gap-3">
                            <span className="text-[11px] text-muted-foreground/60">
                              {timeAgo(notification.created_at)}
                            </span>
                            {!notification.read && (
                              <button
                                onClick={() => onMarkRead(notification.id)}
                                className="flex items-center gap-1 text-[11px] font-medium text-primary opacity-0 group-hover:opacity-100 transition-opacity hover:text-primary/80"
                              >
                                <Check className="h-3 w-3" />
                                Mark read
                              </button>
                            )}
                          </div>
                        </div>
                      </motion.div>
                    )
                  })}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ─── Mock Data ──────────────────────────────────────────────

export const MOCK_NOTIFICATIONS: PortalNotification[] = [
  {
    id: "n1",
    type: "release",
    title: "Operion v3.2 is live",
    message:
      "Route optimization engine v2, new analytics dashboard, and enhanced API endpoints are now available.",
    read: false,
    created_at: new Date(Date.now() - 1000 * 60 * 15).toISOString(), // 15 min ago
  },
  {
    id: "n2",
    type: "billing",
    title: "Invoice #INV-2026-0421 available",
    message: "Your monthly invoice for June 2026 has been generated. View and download in Billing.",
    read: false,
    link: "/dashboard/billing",
    created_at: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(), // 2h ago
  },
  {
    id: "n3",
    type: "security",
    title: "New login from Bucharest",
    message:
      "A new sign-in to your account was detected from Bucharest, Romania. If this was you, no action needed.",
    read: true,
    created_at: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(), // 1d ago
  },
  {
    id: "n4",
    type: "support",
    title: "Ticket #2847 resolved",
    message:
      "Your support request regarding 'API rate limiting' has been resolved. Check the resolution notes.",
    read: false,
    link: "/dashboard/support",
    created_at: new Date(Date.now() - 1000 * 60 * 60 * 30).toISOString(), // 30h ago
  },
  {
    id: "n5",
    type: "doc_update",
    title: "New docs: Fleet API v2",
    message:
      "The Fleet Management API v2 documentation is now live with new endpoints for real-time vehicle tracking.",
    read: true,
    link: "/docs/api-reference",
    created_at: new Date(Date.now() - 1000 * 60 * 60 * 48).toISOString(), // 2d ago
  },
  {
    id: "n6",
    type: "system",
    title: "Scheduled maintenance",
    message:
      "Operion will undergo scheduled maintenance on July 15, 02:00-04:00 UTC. Expect brief downtime.",
    read: true,
    created_at: new Date(Date.now() - 1000 * 60 * 60 * 72).toISOString(), // 3d ago
  },
]
