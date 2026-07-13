import { Helmet } from "react-helmet-async"
import { Link } from "react-router"
import { motion } from "motion/react"
import { MailCheck } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { useLocale } from "@/i18n/locale-context"

export default function VerifyEmailPage() {
  const { t } = useLocale()
  return (
    <>
      <Helmet><title>{t("auth.checkEmail")} — Operion ERP</title></Helmet>
      <div className="flex min-h-[80vh] items-center justify-center px-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
          className="w-full max-w-md"
        >
          <div className="mb-8 text-center">
            <Link to="/" className="inline-flex items-center gap-2 font-bold text-xl">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground text-sm font-bold">O</div>
              Operion
            </Link>
          </div>
          <Card className="text-center">
            <CardHeader>
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ delay: 0.2, type: "spring", stiffness: 200 }}
                className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-green-100 dark:bg-green-900/30"
              >
                <MailCheck className="h-8 w-8 text-green-600 dark:text-green-400" />
              </motion.div>
              <CardTitle>{t("auth.checkEmail")}</CardTitle>
              <CardDescription>{t("auth.checkEmailDesc")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                {t("auth.didntReceive")}
              </p>
              <div className="flex flex-col gap-3">
                <Button asChild>
                  <Link to="/login">{t("auth.goToSignIn")}</Link>
                </Button>
                <Button variant="outline" asChild>
                  <Link to="/contact">{t("auth.contactSupport")}</Link>
                </Button>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </>
  )
}
