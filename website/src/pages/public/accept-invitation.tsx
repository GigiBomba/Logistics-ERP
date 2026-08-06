import { useEffect, useRef, useState } from "react"
import { Helmet } from "react-helmet-async"
import { Link, useSearchParams } from "react-router"
import { motion } from "motion/react"
import { CheckCircle2, Loader2, AlertCircle, Users } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Callout } from "@/components/ui/callout"
import { useAcceptInvitation } from "@/services/queries"
import { useLocale } from "@/i18n/locale-context"
import { AxiosError } from "axios"

type Status = "idle" | "loading" | "success" | "alreadyAccepted" | "error"

export default function AcceptInvitationPage() {
  const { t } = useLocale()
  const [searchParams] = useSearchParams()
  const token = searchParams.get("token")
  const { mutate, isPending } = useAcceptInvitation()
  const [status, setStatus] = useState<Status>("idle")
  const [errorMessage, setErrorMessage] = useState("")
  const firedRef = useRef(false)

  useEffect(() => {
    if (!token) {
      setStatus("error")
      setErrorMessage(t("organization.invite.invalidLinkDesc"))
      return
    }
    if (firedRef.current) return
    firedRef.current = true

    setStatus("loading")
    mutate(token, {
      onSuccess: () => {
        setStatus("success")
      },
      onError: (error) => {
        if (error instanceof AxiosError) {
          const data = error.response?.data as
            | { detail?: string; error_code?: string }
            | undefined
          const code = data?.error_code
          const detail = data?.detail ?? ""

          if (
            code === "invitation/already-accepted" ||
            detail.toLowerCase().includes("already accepted")
          ) {
            setStatus("alreadyAccepted")
            return
          }
          if (
            code === "invitation/expired" ||
            detail.toLowerCase().includes("expired")
          ) {
            setErrorMessage(t("organization.invite.expiredOrInvalidDesc"))
            setStatus("error")
            return
          }
          if (
            code === "invitation/invalid" ||
            detail.toLowerCase().includes("invalid")
          ) {
            setErrorMessage(t("organization.invite.invalidLinkDesc"))
            setStatus("error")
            return
          }
        }
        setErrorMessage(t("organization.invite.genericErrorDesc"))
        setStatus("error")
      },
    })
  }, [token, mutate, t])

  const isLoading = status === "loading" || isPending

  if (!token) {
    return (
      <>
        <Helmet>
          <title>{`${t("organization.invite.invalidLink")} — Operion ERP`}</title>
        </Helmet>
        <div className="flex min-h-[80vh] items-center justify-center px-4">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
            className="w-full max-w-md"
          >
            <div className="mb-8 text-center">
              <Link
                to="/"
                className="inline-flex items-center gap-2 font-bold text-xl"
              >
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground text-sm font-bold">
                  O
                </div>
                Operion
              </Link>
            </div>
            <Card className="text-center">
              <CardHeader>
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ delay: 0.2, type: "spring", stiffness: 200 }}
                  className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-red-100 dark:bg-red-900/30"
                >
                  <AlertCircle className="h-8 w-8 text-red-600 dark:text-red-400" />
                </motion.div>
                <CardTitle>{t("organization.invite.invalidLink")}</CardTitle>
                <CardDescription>
                  {t("organization.invite.invalidLinkDesc")}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <Button asChild className="w-full">
                  <Link to="/contact">{t("auth.contactSupport")}</Link>
                </Button>
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </>
    )
  }

  return (
    <>
      <Helmet>
        <title>{`${t("organization.invite.pageTitle")} — Operion ERP`}</title>
      </Helmet>
      <div className="flex min-h-[80vh] items-center justify-center px-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
          className="w-full max-w-md"
        >
          <div className="mb-8 text-center">
            <Link
              to="/"
              className="inline-flex items-center gap-2 font-bold text-xl"
            >
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground text-sm font-bold">
                O
              </div>
              Operion
            </Link>
          </div>

          <Card className="text-center">
            <CardHeader>
              {isLoading && (
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ delay: 0.2, type: "spring", stiffness: 200 }}
                  className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10"
                >
                  <Loader2 className="h-8 w-8 animate-spin text-primary" />
                </motion.div>
              )}
              {status === "success" && (
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ delay: 0.2, type: "spring", stiffness: 200 }}
                  className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-green-100 dark:bg-green-900/30"
                >
                  <CheckCircle2 className="h-8 w-8 text-green-600 dark:text-green-400" />
                </motion.div>
              )}
              {(status === "error" || status === "alreadyAccepted") && (
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ delay: 0.2, type: "spring", stiffness: 200 }}
                  className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-amber-100 dark:bg-amber-900/30"
                >
                  {status === "alreadyAccepted" ? (
                    <Users className="h-8 w-8 text-amber-600 dark:text-amber-400" />
                  ) : (
                    <AlertCircle className="h-8 w-8 text-red-600 dark:text-red-400" />
                  )}
                </motion.div>
              )}

              <CardTitle>
                {isLoading && t("organization.invite.accepting")}
                {status === "success" && t("organization.invite.accepted")}
                {status === "alreadyAccepted" &&
                  t("organization.invite.alreadyAccepted")}
                {status === "error" && t("organization.invite.failed")}
              </CardTitle>
              <CardDescription>
                {isLoading && t("organization.invite.acceptingDesc")}
                {status === "success" && t("organization.invite.acceptedDesc")}
                {status === "alreadyAccepted" &&
                  t("organization.invite.alreadyAcceptedDesc")}
                {status === "error" && t("organization.invite.errorDesc")}
              </CardDescription>
            </CardHeader>

            <CardContent className="space-y-4">
              {status === "error" && (
                <Callout variant="danger" title={t("common.errorTitle")}>
                  {errorMessage}
                  <div className="mt-2">
                    {t("organization.invite.requestNewInvitation")}{" "}
                    <Link to="/contact" className="underline underline-offset-2">
                      {t("auth.contactSupport")}
                    </Link>
                  </div>
                </Callout>
              )}

              {(status === "success" || status === "alreadyAccepted") && (
                <Button asChild className="w-full">
                  <Link to="/dashboard/organizations">
                    {t("organization.invite.goToOrganizations")}
                  </Link>
                </Button>
              )}

              {status === "error" && (
                <Button asChild variant="outline" className="w-full">
                  <Link to="/contact">{t("auth.contactSupport")}</Link>
                </Button>
              )}
            </CardContent>
          </Card>

          <div className="mt-6 text-center">
            <Link
              to="/"
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              {t("common.back")}
            </Link>
          </div>
        </motion.div>
      </div>
    </>
  )
}
