import { useState, useEffect } from "react"
import { motion } from "motion/react"
import { WifiOff, Wifi, RefreshCw } from "lucide-react"
import { SeoHead } from "@/components/seo/seo-head"
import { Button } from "@/components/ui/button"
import { useLocale } from "@/i18n/locale-context"

export default function ErrorOfflinePage() {
  const { t } = useLocale()
  const [isOnline, setIsOnline] = useState(navigator.onLine)

  useEffect(() => {
    function handleOnline() {
      setIsOnline(true)
    }
    function handleOffline() {
      setIsOnline(false)
    }

    window.addEventListener("online", handleOnline)
    window.addEventListener("offline", handleOffline)
    return () => {
      window.removeEventListener("online", handleOnline)
      window.removeEventListener("offline", handleOffline)
    }
  }, [])

  return (
    <>
      <SeoHead title={t("error.offline")} description="You are offline. Please check your internet connection and try again." noindex />
      <div className="flex min-h-[70vh] items-center justify-center">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="text-center"
        >
          {isOnline ? (
            <>
              <motion.div
                initial={{ scale: 0.8, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ delay: 0.1, duration: 0.4 }}
              >
                <Wifi className="mx-auto h-20 w-20 text-green-500/60" />
              </motion.div>
              <motion.h1
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.3 }}
                className="mt-8 text-2xl font-bold"
              >
                {t("error.backOnline")}
              </motion.h1>
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.4 }}
                className="mt-2 text-muted-foreground"
              >
                {t("error.backOnlineDesc")}
              </motion.p>
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.5 }}
                className="mt-8"
              >
                <Button onClick={() => window.location.reload()}>
                  <RefreshCw className="h-4 w-4" />
                  {t("error.reload")}
                </Button>
              </motion.div>
            </>
          ) : (
            <>
              <motion.div
                initial={{ scale: 0.8, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ delay: 0.1, duration: 0.4 }}
              >
                <WifiOff className="mx-auto h-20 w-20 text-muted-foreground/40" />
              </motion.div>
              <motion.h1
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.3 }}
                className="mt-8 text-2xl font-bold"
              >
                {t("error.offline")}
              </motion.h1>
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.4 }}
                className="mt-2 text-muted-foreground"
              >
                {t("error.offlineDesc")}
              </motion.p>
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.5 }}
                className="mt-8"
              >
                <Button onClick={() => window.location.reload()}>
                  <RefreshCw className="h-4 w-4" />
                  {t("error.retry")}
                </Button>
              </motion.div>
            </>
          )}
        </motion.div>
      </div>
    </>
  )
}
