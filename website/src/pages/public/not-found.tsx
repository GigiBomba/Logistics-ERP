import { Link } from "react-router"
import { motion } from "motion/react"
import { FileQuestion, Home, Sparkles, CreditCard, LifeBuoy, ArrowRight } from "lucide-react"
import { SeoHead } from "@/components/seo/seo-head"
import { Button } from "@/components/ui/button"
import { useLocale } from "@/i18n/locale-context"

const helpfulLinks = [
  { to: "/", labelKey: "nav.home", icon: Home },
  { to: "/features", labelKey: "nav.features", icon: Sparkles },
  { to: "/pricing", labelKey: "nav.pricing", icon: CreditCard },
  { to: "/contact", labelKey: "nav.contact", icon: LifeBuoy },
] as const

export default function NotFoundPage() {
  const { t } = useLocale()
  return (
    <>
      <SeoHead title={t("error.notFound")} description="Page not found — the page you are looking for does not exist or has been moved." noindex />
      <div className="flex min-h-[70vh] items-center justify-center px-4">
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

          {/* Helpful links grid */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5, duration: 0.4 }}
            className="mt-8 grid grid-cols-2 gap-3 sm:flex sm:justify-center"
          >
            {helpfulLinks.map(({ to, labelKey, icon: Icon }) => (
              <Link
                key={to}
                to={to}
                className="group flex items-center gap-2 rounded-lg border bg-card px-4 py-3 text-sm font-medium text-card-foreground shadow-xs transition-colors hover:bg-accent hover:text-accent-foreground sm:px-5"
              >
                <Icon className="h-4 w-4 shrink-0 text-muted-foreground group-hover:text-foreground" />
                <span>{t(labelKey)}</span>
                <ArrowRight className="ml-auto h-3.5 w-3.5 shrink-0 opacity-0 transition-opacity group-hover:opacity-60 sm:ml-1" />
              </Link>
            ))}
          </motion.div>

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.6 }}
            className="mt-8"
          >
            <Button asChild variant="outline" size="sm">
              <Link to="/">{t("error.goHome")}</Link>
            </Button>
          </motion.div>
        </motion.div>
      </div>
    </>
  )
}
