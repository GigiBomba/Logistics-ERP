import { useEffect, useMemo, useState, useCallback } from "react"
import { motion } from "motion/react"
import {
  Search,
  Download,
  Trash2,
  Pencil,
  X,
  MoreHorizontal,
  Loader2,
} from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input, Label } from "@/components/ui/input"

import { Pagination } from "@/components/ui/pagination"
import { Skeleton } from "@/components/ui/loading-spinner"
import { Callout } from "@/components/ui/callout"
import {
  waitlistApi,
  type WaitlistEntry,
  type WaitlistPageResponse,
  type WaitlistEntriesParams,
} from "@/api/endpoints"
import { extractApiError } from "@/api/client"
import { useLocale } from "@/i18n/locale-context"

const STATUS_OPTIONS = ["", "joined", "invited", "activated", "converted", "churned", "unsubscribed"]

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    joined: "bg-secondary text-secondary-foreground",
    invited: "bg-primary text-primary-foreground",
    activated: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950 dark:text-amber-300 dark:border-amber-800",
    converted: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100",
    churned: "bg-destructive text-destructive-foreground",
    unsubscribed: "bg-muted text-muted-foreground opacity-70",
  }
  return (
    <span
      className={`inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold ${styles[status] ?? styles.joined}`}
    >
      {status}
    </span>
  )
}

function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: string
  options: { value: string; label: string }[]
  onChange: (val: string) => void
}) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs text-muted-foreground">{label}</Label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  )
}

function ConfirmDialog({
  open,
  title,
  description,
  onConfirm,
  onCancel,
  isLoading,
}: {
  open: boolean
  title: string
  description: string
  onConfirm: () => void
  onCancel: () => void
  isLoading: boolean
}) {
  const { t } = useLocale()
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="w-full max-w-sm rounded-xl border bg-card p-6 shadow-lg"
      >
        <h3 className="text-lg font-semibold">{title}</h3>
        <p className="mt-2 text-sm text-muted-foreground">{description}</p>
        <div className="mt-6 flex justify-end gap-3">
          <Button variant="outline" size="sm" onClick={onCancel} disabled={isLoading}>
            {t("common.cancel")}
          </Button>
          <Button variant="destructive" size="sm" onClick={onConfirm} disabled={isLoading}>
            {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : t("adminWaitlist.actions.confirm")}
          </Button>
        </div>
      </motion.div>
    </div>
  )
}

function NotesModal({
  open,
  entry,
  onSave,
  onClose,
  isLoading,
}: {
  open: boolean
  entry: WaitlistEntry | null
  onSave: (notes: string) => void
  onClose: () => void
  isLoading: boolean
}) {
  const { t } = useLocale()
  const [notes, setNotes] = useState(entry?.notes ?? "")
  useEffect(() => {
    setNotes(entry?.notes ?? "")
  }, [entry])

  if (!open || !entry) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="w-full max-w-lg rounded-xl border bg-card p-6 shadow-lg"
      >
        <h3 className="text-lg font-semibold">{t("adminWaitlist.actions.editNotes")}</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          {entry.company_name} — {entry.email}
        </p>
        <div className="mt-4 space-y-2">
          <Label htmlFor="notes">{t("adminWaitlist.labels.notes")}</Label>
          <textarea
            id="notes"
            rows={4}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            className="flex min-h-[80px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            placeholder={t("adminWaitlist.placeholders.notes")}
          />
        </div>
        <div className="mt-6 flex justify-end gap-3">
          <Button variant="outline" size="sm" onClick={onClose} disabled={isLoading}>
            {t("common.cancel")}
          </Button>
          <Button size="sm" onClick={() => onSave(notes)} disabled={isLoading}>
            {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : t("common.save")}
          </Button>
        </div>
      </motion.div>
    </div>
  )
}

export default function EntriesTab() {
  const { t } = useLocale()
  const STATUS_LABELS = useMemo<Record<string, string>>(() => ({
    "": t("adminWaitlist.status.all"),
    joined: t("adminWaitlist.status.joined"),
    invited: t("adminWaitlist.status.invited"),
    activated: t("adminWaitlist.status.activated"),
    converted: t("adminWaitlist.status.converted"),
    churned: t("adminWaitlist.status.churned"),
    unsubscribed: t("adminWaitlist.status.unsubscribed"),
  }), [t])

  const [entries, setEntries] = useState<WaitlistEntry[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(25)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [search, setSearch] = useState("")
  const [status, setStatus] = useState("")
  const [country, setCountry] = useState("")
  const [companySize, setCompanySize] = useState("")
  const [fleetSize, setFleetSize] = useState("")
  const [source, setSource] = useState("")
  const [dateFrom, setDateFrom] = useState("")
  const [dateTo, setDateTo] = useState("")

  const [countries, setCountries] = useState<string[]>([])
  const [companySizes, setCompanySizes] = useState<string[]>([])
  const [fleetSizes, setFleetSizes] = useState<string[]>([])
  const [sources, setSources] = useState<string[]>([])

  const [actionLoading, setActionLoading] = useState<number | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<WaitlistEntry | null>(null)
  const [notesTarget, setNotesTarget] = useState<WaitlistEntry | null>(null)
  const [dropdownOpen, setDropdownOpen] = useState<number | null>(null)

  const buildParams = useCallback((): WaitlistEntriesParams => {
    const params: WaitlistEntriesParams = { page, page_size: pageSize }
    if (search.trim()) params.search = search.trim()
    if (status) params.status = status
    if (country) params.country = country
    if (companySize) params.company_size = companySize
    if (fleetSize) params.fleet_size = fleetSize
    if (source) params.source = source
    if (dateFrom) params.date_from = dateFrom
    if (dateTo) params.date_to = dateTo
    return params
  }, [search, status, country, companySize, fleetSize, source, dateFrom, dateTo, page, pageSize])

  const fetchEntries = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await waitlistApi.listEntries(buildParams())
      const data = res.data as WaitlistPageResponse
      setEntries(data.entries)
      setTotal(data.total)
      // Update filter options from response if available
      if (data.by_status) {
        // Derive other dimensions from entries as fallback
        const c = new Set<string>()
        const cs = new Set<string>()
        const fs = new Set<string>()
        const s = new Set<string>()
        data.entries.forEach((e) => {
          if (e.country) c.add(e.country)
          if (e.company_size) cs.add(e.company_size)
          if (e.fleet_size) fs.add(e.fleet_size)
          if (e.source) s.add(e.source)
        })
        setCountries(Array.from(c).sort())
        setCompanySizes(Array.from(cs).sort())
        setFleetSizes(Array.from(fs).sort())
        setSources(Array.from(s).sort())
      }
    } catch (err) {
      setError(extractApiError(err))
    } finally {
      setLoading(false)
    }
  }, [buildParams])

  useEffect(() => {
    fetchEntries()
  }, [fetchEntries])

  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / pageSize)), [total, pageSize])

  function handleExportCsv() {
    const params = buildParams()
    waitlistApi
      .exportCsv(params)
      .then((res) => {
        const blob = new Blob([res.data as BlobPart], { type: "text/csv" })
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement("a")
        a.href = url
        a.download = `waitlist-export-${new Date().toISOString().slice(0, 10)}.csv`
        document.body.appendChild(a)
        a.click()
        a.remove()
        window.URL.revokeObjectURL(url)
      })
      .catch((err) => {
        setError(t("adminWaitlist.messages.exportFailed", { error: extractApiError(err) }))
      })
  }

  function handleDelete(entry: WaitlistEntry) {
    setDeleteTarget(entry)
  }

  async function confirmDelete() {
    if (!deleteTarget) return
    setActionLoading(deleteTarget.id)
    try {
      await waitlistApi.deleteEntry(deleteTarget.id)
      setDeleteTarget(null)
      await fetchEntries()
    } catch (err) {
      setError(t("adminWaitlist.messages.deleteFailed", { error: extractApiError(err) }))
    } finally {
      setActionLoading(null)
    }
  }

  function handleUpdateStatus(entry: WaitlistEntry, newStatus: string) {
    setActionLoading(entry.id)
    waitlistApi
      .updateEntry(entry.id, { status: newStatus })
      .then(() => fetchEntries())
      .catch((err) => setError(t("adminWaitlist.messages.updateFailed", { error: extractApiError(err) })))
      .finally(() => {
        setActionLoading(null)
        setDropdownOpen(null)
      })
  }

  function handleSaveNotes(notes: string) {
    if (!notesTarget) return
    setActionLoading(notesTarget.id)
    waitlistApi
      .updateEntry(notesTarget.id, { notes })
      .then(() => {
        setNotesTarget(null)
        fetchEntries()
      })
      .catch((err) => setError(t("adminWaitlist.messages.updateFailed", { error: extractApiError(err) })))
      .finally(() => setActionLoading(null))
  }

  function clearFilters() {
    setSearch("")
    setStatus("")
    setCountry("")
    setCompanySize("")
    setFleetSize("")
    setSource("")
    setDateFrom("")
    setDateTo("")
    setPage(1)
  }

  const hasFilters = search || status || country || companySize || fleetSize || source || dateFrom || dateTo

  return (
    <div className="space-y-6">
      {/* Filters */}
      <Card>
        <CardContent className="p-5 space-y-4">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder={t("adminWaitlist.placeholders.search")}
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value)
                  setPage(1)
                }}
                className="pl-9"
              />
            </div>
            <div className="flex flex-wrap gap-3">
              <FilterSelect
                label={t("adminWaitlist.filters.status")}
                value={status}
                options={STATUS_OPTIONS.map((s) => ({ value: s, label: STATUS_LABELS[s] }))}
                onChange={(v) => {
                  setStatus(v)
                  setPage(1)
                }}
              />
              <FilterSelect
                label={t("adminWaitlist.filters.country")}
                value={country}
                options={[{ value: "", label: t("adminWaitlist.filters.allCountries") }, ...countries.map((c) => ({ value: c, label: c }))]}
                onChange={(v) => {
                  setCountry(v)
                  setPage(1)
                }}
              />
              <FilterSelect
                label={t("adminWaitlist.filters.companySize")}
                value={companySize}
                options={[{ value: "", label: t("adminWaitlist.filters.allSizes") }, ...companySizes.map((c) => ({ value: c, label: c }))]}
                onChange={(v) => {
                  setCompanySize(v)
                  setPage(1)
                }}
              />
              <FilterSelect
                label={t("adminWaitlist.filters.fleetSize")}
                value={fleetSize}
                options={[{ value: "", label: t("adminWaitlist.filters.allFleets") }, ...fleetSizes.map((c) => ({ value: c, label: c }))]}
                onChange={(v) => {
                  setFleetSize(v)
                  setPage(1)
                }}
              />
              <FilterSelect
                label={t("adminWaitlist.filters.source")}
                value={source}
                options={[{ value: "", label: t("adminWaitlist.filters.allSources") }, ...sources.map((c) => ({ value: c, label: c }))]}
                onChange={(v) => {
                  setSource(v)
                  setPage(1)
                }}
              />
            </div>
          </div>

          <div className="flex flex-wrap items-end gap-3">
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">{t("adminWaitlist.filters.from")}</Label>
              <Input
                type="date"
                value={dateFrom}
                onChange={(e) => {
                  setDateFrom(e.target.value)
                  setPage(1)
                }}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">{t("adminWaitlist.filters.to")}</Label>
              <Input
                type="date"
                value={dateTo}
                onChange={(e) => {
                  setDateTo(e.target.value)
                  setPage(1)
                }}
              />
            </div>
            {hasFilters && (
              <Button variant="ghost" size="sm" onClick={clearFilters} className="h-9">
                <X className="h-4 w-4 mr-1" />
                {t("adminWaitlist.actions.clear")}
              </Button>
            )}
            <div className="flex-1" />
            <Button variant="outline" size="sm" onClick={handleExportCsv}>
              <Download className="h-4 w-4 mr-1.5" />
              {t("adminWaitlist.actions.exportCsv")}
            </Button>
          </div>
        </CardContent>
      </Card>

      {error && (
        <Callout variant="danger">
          {error}
          <div className="mt-2">
            <Button size="sm" variant="outline" onClick={fetchEntries}>
              {t("adminWaitlist.actions.retry")}
            </Button>
          </div>
        </Callout>
      )}

      {/* Table */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center justify-between">
            <span>{t("adminWaitlist.title")}</span>
            <span className="text-sm font-normal text-muted-foreground">
              {t("adminWaitlist.pagination.full", { total, page, totalPages })}
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="px-4 py-3 text-left font-medium">{t("adminWaitlist.table.company")}</th>
                  <th className="px-4 py-3 text-left font-medium">{t("adminWaitlist.table.email")}</th>
                  <th className="px-4 py-3 text-left font-medium">{t("adminWaitlist.table.contact")}</th>
                  <th className="px-4 py-3 text-left font-medium">{t("adminWaitlist.table.status")}</th>
                  <th className="px-4 py-3 text-left font-medium">{t("adminWaitlist.table.source")}</th>
                  <th className="px-4 py-3 text-left font-medium">{t("adminWaitlist.table.joined")}</th>
                  <th className="px-4 py-3 text-right font-medium">{t("adminWaitlist.table.actions")}</th>
                </tr>
              </thead>
              <tbody>
                {loading && entries.length === 0 ? (
                  Array.from({ length: 8 }).map((_, i) => (
                    <tr key={i} className="border-b">
                      <td className="px-4 py-3">
                        <Skeleton className="h-4 w-32" />
                      </td>
                      <td className="px-4 py-3">
                        <Skeleton className="h-4 w-40" />
                      </td>
                      <td className="px-4 py-3">
                        <Skeleton className="h-4 w-24" />
                      </td>
                      <td className="px-4 py-3">
                        <Skeleton className="h-5 w-16" />
                      </td>
                      <td className="px-4 py-3">
                        <Skeleton className="h-4 w-20" />
                      </td>
                      <td className="px-4 py-3">
                        <Skeleton className="h-4 w-24" />
                      </td>
                      <td className="px-4 py-3">
                        <Skeleton className="h-8 w-20 ml-auto" />
                      </td>
                    </tr>
                  ))
                ) : entries.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-12 text-center text-muted-foreground">
                      {t("adminWaitlist.messages.noEntries")}
                    </td>
                  </tr>
                ) : (
                  entries.map((entry) => (
                    <tr key={entry.id} className="border-b hover:bg-muted/40 transition-colors">
                      <td className="px-4 py-3 font-medium">{entry.company_name}</td>
                      <td className="px-4 py-3 text-muted-foreground">{entry.email}</td>
                      <td className="px-4 py-3">{entry.contact_name ?? "—"}</td>
                      <td className="px-4 py-3">
                        <StatusBadge status={entry.status} />
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">{entry.source}</td>
                      <td className="px-4 py-3 text-muted-foreground whitespace-nowrap">
                        {new Date(entry.joined_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="relative inline-block">
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-8 w-8 p-0"
                            onClick={() =>
                              setDropdownOpen(dropdownOpen === entry.id ? null : entry.id)
                            }
                            disabled={actionLoading === entry.id}
                          >
                            {actionLoading === entry.id ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <MoreHorizontal className="h-4 w-4" />
                            )}
                          </Button>
                          {dropdownOpen === entry.id && (
                            <div className="absolute right-0 top-full z-20 mt-1 w-48 rounded-md border bg-popover shadow-md">
                              <div className="py-1">
                                <button
                                  className="flex w-full items-center gap-2 px-3 py-2 text-sm hover:bg-muted text-left"
                                  onClick={() => {
                                    setNotesTarget(entry)
                                    setDropdownOpen(null)
                                  }}
                                >
                                  <Pencil className="h-4 w-4" />
                                  {t("adminWaitlist.actions.editNotes")}
                                </button>
                                <div className="px-3 py-1 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                                  {t("adminWaitlist.actions.changeStatus")}
                                </div>
                                {STATUS_OPTIONS.filter((s) => s && s !== entry.status).map((s) => (
                                  <button
                                    key={s}
                                    className="flex w-full items-center gap-2 px-3 py-2 text-sm hover:bg-muted text-left"
                                    onClick={() => handleUpdateStatus(entry, s)}
                                  >
                                    <span className="h-2 w-2 rounded-full bg-current" />
                                    {STATUS_LABELS[s]}
                                  </button>
                                ))}
                                <div className="my-1 border-t" />
                                <button
                                  className="flex w-full items-center gap-2 px-3 py-2 text-sm text-destructive hover:bg-destructive/10 text-left"
                                  onClick={() => {
                                    setDropdownOpen(null)
                                    handleDelete(entry)
                                  }}
                                >
                                  <Trash2 className="h-4 w-4" />
                                  {t("common.delete")}
                                </button>
                              </div>
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between px-4 py-4 border-t">
            <p className="text-sm text-muted-foreground">
              {t("adminWaitlist.pagination.showing", { count: entries.length, total })}
            </p>
            <Pagination
              currentPage={page}
              totalPages={totalPages}
              onPageChange={setPage}
            />
          </div>
        </CardContent>
      </Card>

      {/* Modals */}
      <ConfirmDialog
        open={!!deleteTarget}
        title={t("adminWaitlist.confirm.deleteTitle")}
        description={t("adminWaitlist.confirm.deleteDescription", { name: deleteTarget?.company_name })}
        onConfirm={confirmDelete}
        onCancel={() => setDeleteTarget(null)}
        isLoading={actionLoading === deleteTarget?.id}
      />

      <NotesModal
        open={!!notesTarget}
        entry={notesTarget}
        onSave={handleSaveNotes}
        onClose={() => setNotesTarget(null)}
        isLoading={actionLoading === notesTarget?.id}
      />
    </div>
  )
}
