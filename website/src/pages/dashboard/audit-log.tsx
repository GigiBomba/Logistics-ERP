import { useState } from "react"
import { Helmet } from "react-helmet-async"
import { motion } from "motion/react"
import {
  LogIn,
  LogOut,
  Key,
  Shield,
  ShieldOff,
  UserPlus,
  UserX,
  UserCog,
  Smartphone,
  FileKey,
  CreditCard,
  Settings,
  Download,
  Trash2,
  Search,
  Clock,
} from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Pagination } from "@/components/ui/pagination"
import { LoadingSpinner } from "@/components/ui/loading-spinner"
import { EmptyState } from "@/components/shared/empty-state"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { Callout } from "@/components/ui/callout"
import { RequireRole } from "@/components/auth/require-role"
import { useAuditLog } from "@/services/queries"
import { useLocale } from "@/i18n/locale-context"
import type { AuditLogEntry, AuditAction } from "@/types"

// ─── Action helpers ─────────────────────────────────────────

const ACTION_ICONS: Partial<Record<AuditAction, typeof LogIn>> = {
  login: LogIn,
  logout: LogOut,
  password_change: Key,
  mfa_enabled: Shield,
  mfa_disabled: ShieldOff,
  member_invited: UserPlus,
  member_removed: UserX,
  role_changed: UserCog,
  device_deactivated: Smartphone,
  license_transferred: FileKey,
  subscription_changed: CreditCard,
  settings_updated: Settings,
  data_exported: Download,
  account_deleted: Trash2,
}

const ACTION_VARIANTS: Partial<Record<AuditAction, "default" | "secondary" | "destructive" | "outline" | "success">> = {
  login: "success",
  logout: "secondary",
  password_change: "secondary",
  mfa_enabled: "success",
  mfa_disabled: "secondary",
  member_invited: "default",
  member_removed: "destructive",
  role_changed: "secondary",
  device_deactivated: "destructive",
  license_transferred: "default",
  subscription_changed: "default",
  settings_updated: "secondary",
  data_exported: "default",
  account_deleted: "destructive",
}

function getActionIcon(action: AuditAction) {
  const Icon = ACTION_ICONS[action] ?? LogIn
  return <Icon className="h-4 w-4" />
}

function getActionLabel(action: AuditAction, t: (key: string) => string) {
  const key = `auditLog.action.${action}`
  const label = t(key)
  return label || action.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
}

// ─── Date formatting ───────────────────────────────────────

function formatDate(dateString: string) {
  return new Date(dateString).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

function formatRelativeTime(dateString: string) {
  const now = Date.now()
  const then = new Date(dateString).getTime()
  const diffMs = now - then
  const diffMinutes = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMinutes < 1) return "Just now"
  if (diffMinutes < 60) return `${diffMinutes}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  return formatDate(dateString)
}

// ─── Target description ────────────────────────────────────

function getTargetDescription(entry: AuditLogEntry): string {
  if (entry.target_type && entry.target_id) {
    return `${entry.target_type}: ${entry.target_id}`
  }
  if (entry.target_type) return entry.target_type
  if (entry.metadata?.target_name) return entry.metadata.target_name
  return "\u2014"
}

// ─── Entry row ─────────────────────────────────────────────

function AuditLogRow({ entry }: { entry: AuditLogEntry }) {
  const { t } = useLocale()
  const actionLabel = getActionLabel(entry.action, t)
  const variant = (ACTION_VARIANTS[entry.action] ?? "secondary") as "default" | "secondary" | "destructive" | "outline" | "success"

  return (
    <motion.tr
      initial={{ opacity: 0, y: 8 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      className="border-b border-border/50 transition-colors hover:bg-muted/30"
    >
      <td className="py-3 pl-4 pr-3">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent">
            {getActionIcon(entry.action)}
          </div>
          <div className="min-w-0">
            <Badge variant={variant} className="whitespace-nowrap">
              {actionLabel}
            </Badge>
          </div>
        </div>
      </td>
      <td className="px-3 py-3">
        <span className="text-sm font-medium">{entry.actor_name || entry.actor_user_id}</span>
      </td>
      <td className="px-3 py-3">
        <span className="text-sm text-muted-foreground">{getTargetDescription(entry)}</span>
      </td>
      <td className="px-3 py-3">
        <div className="flex items-center gap-1.5 text-sm text-muted-foreground" title={formatDate(entry.created_at)}>
          <Clock className="h-3.5 w-3.5 shrink-0" />
          <span>{formatRelativeTime(entry.created_at)}</span>
        </div>
      </td>
      <td className="px-3 py-3">
        {entry.ip_address ? (
          <span className="font-mono text-xs text-muted-foreground">{entry.ip_address}</span>
        ) : (
          <span className="text-xs text-muted-foreground">\u2014</span>
        )}
      </td>
    </motion.tr>
  )
}

// ─── Loading skeleton ──────────────────────────────────────

function AuditLogSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 8 }).map((_, i) => (
        <div key={i} className="flex animate-pulse items-center gap-4 rounded-lg border border-border/50 p-4">
          <div className="h-8 w-8 rounded-full bg-muted" />
          <div className="flex-1 space-y-2">
            <div className="h-4 w-24 rounded bg-muted" />
            <div className="h-3 w-32 rounded bg-muted" />
          </div>
          <div className="h-4 w-20 rounded bg-muted" />
          <div className="h-4 w-16 rounded bg-muted" />
        </div>
      ))}
    </div>
  )
}

// ─── Main page ─────────────────────────────────────────────

export default function AuditLogPage() {
  const { t } = useLocale()
  const [page, setPage] = useState(1)
  const [actorSearch, setActorSearch] = useState("")
  const [actionFilter, setActionFilter] = useState<string>("")
  const perPage = 25

  const { data, isLoading, isError, error, refetch } = useAuditLog({
    page,
    per_page: perPage,
    actor: actorSearch || undefined,
    action: actionFilter || undefined,
  })

  const entries = data?.entries ?? []
  const total = data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / perPage))

  const allActions: AuditAction[] = [
    "login", "logout", "password_change", "mfa_enabled", "mfa_disabled",
    "member_invited", "member_removed", "role_changed", "device_deactivated",
    "license_transferred", "subscription_changed", "settings_updated",
    "data_exported", "account_deleted",
  ]

  return (
    <RequireRole roles={["owner", "admin"]}>
      <Helmet>
        <title>{t("auditLog.pageTitle")} — Operion ERP</title>
      </Helmet>

      <SectionWrapper>
        {/* Page Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
        >
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h1 className="text-3xl font-bold tracking-tight">{t("auditLog.pageTitle")}</h1>
              <p className="mt-2 text-muted-foreground">{t("auditLog.description")}</p>
            </div>
          </div>
        </motion.div>

        {/* Filter bar */}
        <motion.div
          className="mt-6 flex flex-wrap items-center gap-3"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.05 }}
        >
          <div className="relative w-full max-w-xs">
            <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder={t("auditLog.filterActorPlaceholder")}
              value={actorSearch}
              onChange={(e) => { setActorSearch(e.target.value); setPage(1) }}
              className="pl-8"
            />
          </div>

          <select
            value={actionFilter}
            onChange={(e) => { setActionFilter(e.target.value); setPage(1) }}
            className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            aria-label={t("auditLog.filterAction")}
          >
            <option value="">{t("auditLog.filterActionPlaceholder")}</option>
            {allActions.map((action) => (
              <option key={action} value={action}>
                {getActionLabel(action, t)}
              </option>
            ))}
          </select>
        </motion.div>

        {/* Content area */}
        <motion.div
          className="mt-6"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.1 }}
        >
          {isLoading ? (
            <Card>
              <CardContent className="p-6">
                <div className="flex items-center justify-center py-8">
                  <LoadingSpinner size="lg" />
                </div>
                <AuditLogSkeleton />
              </CardContent>
            </Card>
          ) : isError ? (
            <Card>
              <CardContent className="p-6">
                <Callout variant="danger" title={t("auditLog.error")}>
                  {error instanceof Error ? error.message : t("auditLog.errorDesc")}
                </Callout>
                <div className="mt-4 flex justify-center">
                  <Button variant="outline" onClick={() => refetch()}>
                    {t("auditLog.retry")}
                  </Button>
                </div>
              </CardContent>
            </Card>
          ) : entries.length === 0 ? (
            <Card>
              <CardContent className="p-6">
                <EmptyState
                  icon={<ClipboardListIcon />}
                  title={t("auditLog.empty")}
                  description={t("auditLog.emptyDesc")}
                />
              </CardContent>
            </Card>
          ) : (
            <>
              {/* Table view on larger screens */}
              <div className="overflow-x-auto rounded-lg border border-border/50">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-border/50 bg-muted/40 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      <th className="px-4 py-3">{t("auditLog.table.action")}</th>
                      <th className="px-3 py-3">{t("auditLog.table.actor")}</th>
                      <th className="px-3 py-3">{t("auditLog.table.target")}</th>
                      <th className="px-3 py-3">{t("auditLog.table.timestamp")}</th>
                      <th className="px-3 py-3">{t("auditLog.table.ipAddress")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {entries.map((entry) => (
                      <AuditLogRow key={entry.id} entry={entry} />
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              <div className="mt-6 flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                  {t("auditLog.pagination")
                    .replace("{page}", String(page))
                    .replace("{totalPages}", String(totalPages))}
                  {" "}· {total} total entries
                </p>
                <Pagination
                  currentPage={page}
                  totalPages={totalPages}
                  onPageChange={setPage}
                />
              </div>
            </>
          )}
        </motion.div>
      </SectionWrapper>
    </RequireRole>
  )
}

// ─── Inline clipboard icon for empty state ─────────────────

function ClipboardListIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="64"
      height="64"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="text-muted-foreground/60"
    >
      <rect width="8" height="4" x="8" y="2" rx="1" ry="1" />
      <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
      <path d="M12 11h4" />
      <path d="M12 16h4" />
      <path d="M8 11h.01" />
      <path d="M8 16h.01" />
    </svg>
  )
}
