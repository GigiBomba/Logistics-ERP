import { useState, useEffect, useCallback } from "react"
import { X, Clock, AlertTriangle } from "lucide-react"
import { getTrialState, daysLeftInTrial } from "@/lib/trial"
import { useSubscription } from "@/services/queries"
import { useLocale } from "@/i18n/locale-context"
import { cn } from "@/lib/utils"

function getDismissKey() {
  const today = new Date().toISOString().slice(0, 10)
  return `operion-trial-banner-dismissed-${today}`
}

export function TrialBanner() {
  const { t } = useLocale()
  const { data: subscription } = useSubscription()
  const [dismissed, setDismissed] = useState(false)

  useEffect(() => {
    if (typeof window === "undefined") return
    setDismissed(localStorage.getItem(getDismissKey()) === "1")
  }, [])

  const handleDismiss = useCallback(() => {
    if (typeof window === "undefined") return
    localStorage.setItem(getDismissKey(), "1")
    setDismissed(true)
  }, [])

  if (!subscription) return null

  const state = getTrialState(subscription)
  const daysLeft = daysLeftInTrial(subscription)

  // Only show when the backend says we are actually trialing
  if (subscription.status !== "trialing") return null
  if (state === "expired") return null
  if (state !== "active" && state !== "expiring_soon") return null

  const isUrgent = state === "expiring_soon" && daysLeft != null && daysLeft <= 4

  if (dismissed) return null

  return (
    <div
      role="banner"
      aria-live="polite"
      className={cn(
        "relative flex items-start gap-3 rounded-lg border px-4 py-3 shadow-sm",
        isUrgent
          ? "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-300"
          : "border-blue-200 bg-blue-50 text-blue-800 dark:border-blue-800 dark:bg-blue-950 dark:text-blue-300"
      )}
    >
      {isUrgent ? (
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
      ) : (
        <Clock className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
      )}
      <div className="flex-1">
        <p className="text-sm font-medium">
          {isUrgent
            ? t("trialBanner.expiringSoon.title").replace("{days}", String(daysLeft))
            : t("trialBanner.active.title")}
        </p>
        <p className="text-xs opacity-90">
          {isUrgent
            ? t("trialBanner.expiringSoon.body")
            : t("trialBanner.active.body")}
        </p>
      </div>
      <button
        onClick={handleDismiss}
        className="rounded-md p-1 hover:bg-black/5 dark:hover:bg-white/10"
        aria-label={t("common.dismissTrialBanner")}
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  )
}

export default TrialBanner
