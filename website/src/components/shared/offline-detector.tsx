import { useState, useEffect, useCallback } from "react"
import { Link } from "react-router"
import { motion, AnimatePresence } from "motion/react"
import { WifiOff, X } from "lucide-react"
import { useLocale } from "@/i18n/locale-context"
import { cn } from "@/lib/utils"

/**
 * OfflineDetector — renders a dismissible notification banner at the top
 * of the viewport when the browser goes offline.
 *
 * Does NOT perform a full-page redirect. The dedicated `/offline` page
 * remains available for users who navigate there intentionally.
 */
export default function OfflineDetector() {
  const { t } = useLocale()
  const [isOffline, setIsOffline] = useState(
    typeof navigator !== "undefined" ? !navigator.onLine : false,
  )
  const [dismissed, setDismissed] = useState(false)

  const handleOnline = useCallback(() => {
    setIsOffline(false)
    setDismissed(false)
  }, [])

  const handleOffline = useCallback(() => {
    setIsOffline(true)
    setDismissed(false)
  }, [])

  useEffect(() => {
    window.addEventListener("online", handleOnline)
    window.addEventListener("offline", handleOffline)
    return () => {
      window.removeEventListener("online", handleOnline)
      window.removeEventListener("offline", handleOffline)
    }
  }, [handleOnline, handleOffline])

  const show = isOffline && !dismissed

  return (
    <AnimatePresence>
      {show && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={{ duration: 0.3 }}
          className="sticky top-0 z-50 overflow-hidden"
          role="alert"
          aria-live="assertive"
        >
          <div
            className={cn(
              "flex items-center gap-3 px-4 py-2.5 text-sm",
              "bg-amber-50 text-amber-900",
              "dark:bg-amber-950 dark:text-amber-200",
              "border-b border-amber-200 dark:border-amber-800",
            )}
          >
            <WifiOff className="h-4 w-4 shrink-0" aria-hidden="true" />
            <span className="flex-1">{t("error.offlineBanner")}</span>
            <Link
              to="/offline"
              className="font-medium underline-offset-2 hover:underline"
            >
              {t("error.offlineViewPage")}
            </Link>
            <button
              type="button"
              onClick={() => setDismissed(true)}
              className="ml-2 shrink-0 rounded p-0.5 transition-colors hover:bg-amber-200/60 dark:hover:bg-amber-800/60"
              aria-label={t("error.offlineDismiss")}
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
