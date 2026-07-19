import { useState, useRef, useEffect, useCallback } from "react"
import { Link } from "react-router"
import { motion, AnimatePresence } from "motion/react"
import { ChevronDown, Check, Building2, Plus, Settings } from "lucide-react"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { useLocale } from "@/i18n/locale-context"
import type { Organization } from "@/types"

interface OrgSwitcherProps {
  organizations: Organization[]
  activeOrgId: string
  onSwitch: (orgId: string) => void
}

function getInitials(name: string) {
  return name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase()
}

export function OrgSwitcher({ organizations, activeOrgId, onSwitch }: OrgSwitcherProps) {
  const { t } = useLocale()
  const [open, setOpen] = useState(false)
  const [highlightedIndex, setHighlightedIndex] = useState(-1)
  const containerRef = useRef<HTMLDivElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  const activeOrg = organizations.find((o) => o.id === activeOrgId)
  const itemCount = organizations.length + 2 // orgs + manage link + create link

  const close = useCallback(() => {
    setOpen(false)
    setHighlightedIndex(-1)
  }, [])

  // Close on click outside
  useEffect(() => {
    if (!open) return
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        close()
      }
    }
    document.addEventListener("mousedown", handleClick)
    return () => document.removeEventListener("mousedown", handleClick)
  }, [open, close])

  // Keyboard handling
  useEffect(() => {
    if (!open) return
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault()
        close()
        return
      }
      if (e.key === "ArrowDown") {
        e.preventDefault()
        setHighlightedIndex((prev) => (prev + 1) % itemCount)
      }
      if (e.key === "ArrowUp") {
        e.preventDefault()
        setHighlightedIndex((prev) => (prev - 1 + itemCount) % itemCount)
      }
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault()
        if (highlightedIndex >= 0 && highlightedIndex < organizations.length) {
          onSwitch(String(organizations[highlightedIndex].id))
          close()
        } else if (highlightedIndex === organizations.length) {
          // Manage organizations — handled by link
          close()
        } else if (highlightedIndex === organizations.length + 1) {
          // Create organization — no action (disabled)
        }
      }
      if (e.key === "Tab") {
        // Allow natural tab flow, but close dropdown when tabbing out
        setTimeout(() => {
          if (containerRef.current && !containerRef.current.contains(document.activeElement)) {
            close()
          }
        }, 0)
      }
    }
    document.addEventListener("keydown", handleKey)
    return () => document.removeEventListener("keydown", handleKey)
  }, [open, highlightedIndex, itemCount, organizations, onSwitch, close])

  // Scroll highlighted item into view
  useEffect(() => {
    if (highlightedIndex >= 0 && listRef.current) {
      const items = listRef.current.querySelectorAll("[data-org-item]")
      const item = items[highlightedIndex] as HTMLElement | undefined
      item?.scrollIntoView({ block: "nearest" })
    }
  }, [highlightedIndex])

  return (
    <div ref={containerRef} className="relative">
      {/* Trigger */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="listbox"
        aria-expanded={open}
        className={cn(
          "flex w-full items-center gap-3 rounded-lg border px-3 py-2.5 text-left transition-colors",
          "hover:bg-accent focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
          open && "bg-accent"
        )}
      >
        {activeOrg ? (
          <Avatar size="sm">
            <AvatarFallback className="bg-primary/10 text-primary text-xs">
              {getInitials(activeOrg.name)}
            </AvatarFallback>
          </Avatar>
        ) : (
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-muted">
            <Building2 className="h-4 w-4 text-muted-foreground" />
          </div>
        )}
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate">
            {activeOrg?.name ?? "Select Organization"}
          </p>
        </div>
        <ChevronDown
          className={cn(
            "h-4 w-4 shrink-0 text-muted-foreground transition-transform",
            open && "rotate-180"
          )}
        />
      </button>

      {/* Dropdown */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.98 }}
            transition={{ duration: 0.15 }}
            className="absolute left-0 right-0 top-full z-50 mt-1.5 overflow-hidden rounded-xl border bg-popover shadow-lg"
            role="listbox"
            aria-label={t("common.aria.organizations")}
            ref={listRef}
          >
            {/* Org List */}
            <div className="max-h-72 overflow-y-auto p-1.5">
              {organizations.map((org, index) => {
                const isActive = org.id === activeOrgId
                const isHighlighted = index === highlightedIndex
                return (
                  <button
                    key={org.id}
                    type="button"
                    data-org-item
                    role="option"
                    aria-selected={isActive}
                    onClick={() => {
                      onSwitch(String(org.id))
                      close()
                    }}
                    onMouseEnter={() => setHighlightedIndex(index)}
                    className={cn(
                      "flex w-full items-center gap-3 rounded-md px-2.5 py-2 text-left text-sm transition-colors",
                      isHighlighted || isActive
                        ? "bg-accent text-accent-foreground"
                        : "hover:bg-accent/50"
                    )}
                  >
                    <Avatar size="sm">
                      <AvatarFallback className="bg-primary/10 text-primary text-xs">
                        {getInitials(org.name)}
                      </AvatarFallback>
                    </Avatar>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium truncate">{org.name}</p>
                      <p className="text-xs text-muted-foreground truncate">
                        {org.industry ?? "Organization"}
                      </p>
                    </div>
                    {isActive && (
                      <Badge variant="success" className="shrink-0 text-[10px] px-1.5 py-0">
                        <Check className="mr-1 h-3 w-3" />
                        Current
                      </Badge>
                    )}
                  </button>
                )
              })}
            </div>

            {/* Footer Actions */}
            <div className="border-t p-1.5">
              <Link
                to="/dashboard/organizations"
                data-org-item
                onClick={close}
                onMouseEnter={() => setHighlightedIndex(organizations.length)}
                className={cn(
                  "flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-sm transition-colors",
                  highlightedIndex === organizations.length
                    ? "bg-accent text-accent-foreground"
                    : "hover:bg-accent/50 text-muted-foreground hover:text-foreground"
                )}
              >
                <Settings className="h-4 w-4" />
                Manage organizations
              </Link>
              <button
                type="button"
                data-org-item
                disabled
                onMouseEnter={() => setHighlightedIndex(organizations.length + 1)}
                className={cn(
                  "flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-sm transition-colors",
                  highlightedIndex === organizations.length + 1
                    ? "bg-accent text-accent-foreground"
                    : "hover:bg-accent/50 text-muted-foreground hover:text-foreground",
                  "disabled:opacity-40 disabled:pointer-events-none"
                )}
              >
                <Plus className="h-4 w-4" />
                Create organization
                <span className="ml-auto text-[10px] text-muted-foreground">Soon</span>
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
