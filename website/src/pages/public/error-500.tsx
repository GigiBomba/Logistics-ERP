import { Helmet } from "react-helmet-async"
import { Link } from "react-router"
import { motion } from "motion/react"
import { AlertTriangle, RefreshCw, Home, LifeBuoy } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useLocale } from "@/i18n/locale-context"

export default function Error500Page() {
  const { t } = useLocale()
  return (
    <>
      <Helmet>
        <title>{t("error.serverError")} — Operion ERP</title>
      </Helmet>
      <div className="flex min-h-[70vh] items-center justify-center">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="text-center"
        >
          <motion.div
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ delay: 0.1, duration: 0.4 }}
          >
            <AlertTriangle className="mx-auto h-20 w-20 text-muted-foreground/40" />
          </motion.div>
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
            className="mt-6 text-7xl font-bold tracking-tighter text-muted-foreground/20"
          >
            500
          </motion.p>
          <motion.h1
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3 }}
            className="mt-4 text-2xl font-bold"
          >
            {t("error.somethingWentWrong")}
          </motion.h1>
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.4 }}
            className="mt-2 text-muted-foreground"
          >
            {t("error.serverErrorDesc")}
          </motion.p>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.5 }}
            className="mt-8 flex flex-col items-center gap-3 sm:flex-row sm:justify-center"
          >
            <Button onClick={() => window.location.reload()}>
              <RefreshCw className="h-4 w-4" />
              {t("common.tryAgain")}
            </Button>
            <Button variant="outline" asChild>
              <Link to="/">
                <Home className="h-4 w-4" />
                {t("error.goHome")}
              </Link>
            </Button>
            <Button variant="outline" asChild>
              <Link to="/contact">
                <LifeBuoy className="h-4 w-4" />
                {t("error.contactSupport")}
              </Link>
            </Button>
          </motion.div>
        </motion.div>
      </div>
    </>
  )
}
