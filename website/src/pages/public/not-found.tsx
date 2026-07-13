import { Helmet } from "react-helmet-async"
import { Link } from "react-router"
import { motion } from "motion/react"
import { FileQuestion } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useLocale } from "@/i18n/locale-context"

export default function NotFoundPage() {
  const { t } = useLocale()
  return (
    <>
      <Helmet>
        <title>{t("error.notFound")} — Operion ERP</title>
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
            <FileQuestion className="mx-auto h-20 w-20 text-muted-foreground/40" />
          </motion.div>
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
            className="mt-6 text-7xl font-bold tracking-tighter text-muted-foreground/20"
          >
            404
          </motion.p>
          <motion.h1
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3 }}
            className="mt-4 text-2xl font-bold"
          >
            {t("error.notFound")}
          </motion.h1>
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.4 }}
            className="mt-2 text-muted-foreground"
          >
            {t("error.notFoundDesc")}
          </motion.p>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.5 }}
            className="mt-8 flex flex-col items-center gap-3 sm:flex-row sm:justify-center"
          >
            <Button asChild>
              <Link to="/">{t("error.goHome")}</Link>
            </Button>
            <Button variant="outline" asChild>
              <Link to="/contact">{t("error.contactSupport")}</Link>
            </Button>
          </motion.div>
        </motion.div>
      </div>
    </>
  )
}
