import { Helmet } from "react-helmet-async"
import { Link } from "react-router"
import { motion } from "motion/react"
import { Wrench } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useLocale } from "@/i18n/locale-context"

export default function ErrorMaintenancePage() {
  const { t } = useLocale()
  return (
    <>
      <Helmet>
        <title>{t("error.maintenance")} — Operion ERP</title>
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
            <Wrench className="mx-auto h-20 w-20 text-muted-foreground/40" />
          </motion.div>
          <motion.h1
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3 }}
            className="mt-8 text-2xl font-bold"
          >
            {t("error.maintenance")}
          </motion.h1>
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.4 }}
            className="mt-2 text-muted-foreground"
          >
            {t("error.maintenanceDesc")}
          </motion.p>
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.45 }}
            className="mt-4 text-sm font-medium text-muted-foreground/80"
          >
            {t("error.maintenanceExpected")}
          </motion.p>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.5 }}
            className="mt-8 flex flex-col items-center gap-3 sm:flex-row sm:justify-center"
          >
            <Button asChild>
              <Link to="/status">{t("error.statusPage")}</Link>
            </Button>
            <Button variant="outline" asChild>
              <Link to="/">{t("error.goHome")}</Link>
            </Button>
          </motion.div>
        </motion.div>
      </div>
    </>
  )
}
