import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import { useLocale } from "@/i18n/locale-context"
import {
  loadConsent,
  saveConsent,
  getDefaultConsent,
  applyConsent,
  type ConsentState,
} from "@/lib/consent"

/**
 * Cookie‑consent banner with Google Consent Mode v2 integration.
 *
 * Shows a fixed bottom overlay when no valid consent is stored.
 * Three‑button UX: Accept All | Reject All | Manage Preferences.
 * "Manage Preferences" reveals a detail panel with per‑category toggles.
 *
 * Stored consent is automatically applied to GCM on every page load.
 */
export default function CookieConsentBanner() {
  const { t } = useLocale()
  const [consent, setConsent] = useState<ConsentState | null | undefined>(
    undefined,
  )
  const [showPreferences, setShowPreferences] = useState(false)
  const [pendingAnalytics, setPendingAnalytics] = useState(false)
  const [pendingMarketing, setPendingMarketing] = useState(false)

  // ── Bootstrap: load stored consent & apply it ──────────────────────
  useEffect(() => {
    const stored = loadConsent()
    setConsent(stored)
    if (stored) {
      applyConsent(stored)
    }
  }, [])

  // ── Loading – don't flash the banner ───────────────────────────────
  if (consent === undefined) return null

  // ── Consent already given – hide banner ────────────────────────────
  if (consent !== null) return null

  // ── Handlers ───────────────────────────────────────────────────────
  function handleAcceptAll() {
    const state: ConsentState = {
      ...getDefaultConsent(),
      timestamp: Date.now(),
      analytics: true,
      marketing: true,
    }
    saveConsent(state)
    applyConsent(state)
    setConsent(state)
  }

  function handleRejectAll() {
    const state: ConsentState = {
      ...getDefaultConsent(),
      timestamp: Date.now(),
    }
    saveConsent(state)
    applyConsent(state)
    setConsent(state)
  }

  function handleOpenPreferences() {
    setPendingAnalytics(false)
    setPendingMarketing(false)
    setShowPreferences(true)
  }

  function handleSavePreferences() {
    const state: ConsentState = {
      ...getDefaultConsent(),
      timestamp: Date.now(),
      analytics: pendingAnalytics,
      marketing: pendingMarketing,
    }
    saveConsent(state)
    applyConsent(state)
    setConsent(state)
  }

  // ── Render ─────────────────────────────────────────────────────────
  return (
    <Card
      role="dialog"
      aria-modal="true"
      aria-labelledby="cookie-consent-title"
      className={cn(
        // Base: full‑width bar pinned to bottom
        "fixed bottom-0 left-0 right-0 z-50 rounded-none border-x-0 border-b-0",
        // Desktop: centered card with rounded corners
        "sm:bottom-4 sm:left-1/2 sm:-translate-x-1/2 sm:w-[calc(100%-2rem)] sm:max-w-lg sm:rounded-xl sm:border-x sm:border-b",
        // Glass effect
        "bg-background/80 backdrop-blur-xl shadow-lg",
        // Spacing
        "p-4 sm:p-6",
      )}
    >
      <div className="flex flex-col gap-4">
        {/* ── Title + description ──────────────────────────────── */}
        <div>
          <h2
            id="cookie-consent-title"
            className="text-base font-semibold"
          >
            {t("cookieConsent.title")}
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {t("cookieConsent.description")}
          </p>
        </div>

        {/* ── Preference toggles (hidden until expanded) ───────── */}
        {showPreferences && (
          <div className="space-y-3 rounded-lg border p-4">
            {/* Strictly Necessary — always on */}
            <div className="flex items-center justify-between gap-4">
              <div className="min-w-0">
                <p className="text-sm font-medium">
                  {t("cookieConsent.strictlyNecessary")}
                </p>
                <p className="text-xs text-muted-foreground">
                  {t("cookieConsent.strictlyNecessaryDesc")}
                </p>
              </div>
              <Badge
                variant="secondary"
                className="shrink-0 text-xs"
              >
                {t("cookieConsent.alwaysActive")}
              </Badge>
            </div>

            {/* Analytics */}
            <div className="flex items-center justify-between gap-4">
              <div className="min-w-0">
                <p className="text-sm font-medium">{t("cookieConsent.analytics")}</p>
                <p className="text-xs text-muted-foreground">
                  {t("cookieConsent.analyticsDesc")}
                </p>
              </div>
              <ToggleSwitch
                checked={pendingAnalytics}
                onChange={setPendingAnalytics}
                aria-label={t("cookieConsent.toggleAnalytics")}
              />
            </div>

            {/* Marketing */}
            <div className="flex items-center justify-between gap-4">
              <div className="min-w-0">
                <p className="text-sm font-medium">{t("cookieConsent.marketing")}</p>
                <p className="text-xs text-muted-foreground">
                  {t("cookieConsent.marketingDesc")}
                </p>
              </div>
              <ToggleSwitch
                checked={pendingMarketing}
                onChange={setPendingMarketing}
                aria-label={t("cookieConsent.toggleMarketing")}
              />
            </div>
          </div>
        )}

        {/* ── Buttons ──────────────────────────────────────────── */}
        <div
          className={cn(
            "flex flex-wrap gap-2",
            showPreferences
              ? "justify-end"
              : "sm:flex-row sm:justify-end",
          )}
        >
          {!showPreferences ? (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={handleRejectAll}
              >
                {t("cookieConsent.rejectAll")}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleOpenPreferences}
              >
                {t("cookieConsent.managePreferences")}
              </Button>
              <Button
                variant="default"
                size="sm"
                onClick={handleAcceptAll}
              >
                {t("cookieConsent.acceptAll")}
              </Button>
            </>
          ) : (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={handleRejectAll}
              >
                {t("cookieConsent.rejectAll")}
              </Button>
              <Button
                variant="default"
                size="sm"
                onClick={handleSavePreferences}
              >
                {t("cookieConsent.savePreferences")}
              </Button>
            </>
          )}
        </div>
      </div>
    </Card>
  )
}

// ── Inline toggle switch (no external dependency) ─────────────────────
function ToggleSwitch({
  checked,
  onChange,
  ...props
}: {
  checked: boolean
  onChange: (v: boolean) => void
} & Omit<React.ComponentPropsWithoutRef<"button">, "checked" | "onChange">) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={cn(
        "relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        checked ? "bg-primary" : "bg-input",
      )}
      {...props}
    >
      <span
        className={cn(
          "pointer-events-none block h-4 w-4 rounded-full bg-background shadow-lg ring-0 transition-transform",
          checked ? "translate-x-4" : "translate-x-0",
        )}
      />
    </button>
  )
}
