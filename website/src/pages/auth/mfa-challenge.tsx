import { useState, useEffect, useRef } from "react"
import { Helmet } from "react-helmet-async"
import { Link } from "react-router"
import { useAppNavigate } from "@/hooks/useAppNavigate"
import { Shield, ArrowLeft, AlertCircle, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card"
import { useAuth } from "@/contexts/auth-provider"
import { useLocale } from "@/i18n/locale-context"

export default function MfaChallengePage() {
  const { t } = useLocale()
  const { mfaSessionToken, verifyMfa } = useAuth()
  const navigate = useAppNavigate()

  const [code, setCode] = useState("")
  const [isBackup, setIsBackup] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState("")
  const hadSessionToken = useRef(false)

  // Track that we once had a session token, so the post-verify cleanup
  // (provider clears mfaSessionToken) doesn't race us back to /login.
  if (mfaSessionToken) {
    hadSessionToken.current = true
  }

  // Redirect to login if no MFA session token is present
  useEffect(() => {
    if (!mfaSessionToken && !hadSessionToken.current) {
      navigate("/login", { replace: true })
    }
  }, [mfaSessionToken, navigate])

  async function handleSubmit(e?: React.FormEvent, submittedCode?: string) {
    e?.preventDefault()
    // Use the explicit submitted value when called from the delayed auto-submit
    // (the closure's `code` would be stale for a single-shot 6-digit fill/paste).
    const value = submittedCode ?? code
    if (value.length < 6) return

    setIsLoading(true)
    setError("")

    try {
      await verifyMfa(value)
      navigate("/dashboard", { replace: true })
    } catch {
      setError(isBackup ? t("mfaChallenge.invalidBackupCode") : t("mfaChallenge.invalidVerificationCode"))
      setCode("")
    } finally {
      setIsLoading(false)
    }
  }

  function handleCodeChange(value: string) {
    // Only allow digits
    const digits = value.replace(/\D/g, "").slice(0, 6)
    setCode(digits)
    setError("")

    // Auto-submit when 6 digits are entered — pass the digits explicitly so the
    // delayed call doesn't read a stale `code` closure (fill/paste path).
    if (digits.length === 6) {
      setTimeout(() => handleSubmit(undefined, digits), 50)
    }
  }

  if (!mfaSessionToken) {
    return null
  }

  return (
    <>
      <Helmet><title>{t("mfaChallenge.pageTitle")}</title></Helmet>
      <div className="flex min-h-[80vh] items-center justify-center px-4">
        <div className="w-full max-w-md">
          <div className="mb-8 text-center">
            <Link to="/" className="inline-flex items-center gap-2 font-bold text-xl">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground text-sm font-bold">O</div>
              Operion
            </Link>
          </div>

          <Card>
            <CardHeader className="text-center">
              <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
                <Shield className="h-6 w-6 text-primary" />
              </div>
              <CardTitle>{t("mfaChallenge.title")}</CardTitle>
              <CardDescription>
                {isBackup
                  ? t("mfaChallenge.backupCodeDesc")
                  : t("mfaChallenge.authCodeDesc")}
              </CardDescription>
            </CardHeader>

            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <label htmlFor="mfa-code" className="text-sm font-medium leading-none">
                    {isBackup ? t("mfaChallenge.backupCodeLabel") : t("mfaChallenge.verificationCodeLabel")}
                  </label>
                  <div className="relative">
                    <Input
                      id="mfa-code"
                      type="text"
                      inputMode="numeric"
                      autoComplete="one-time-code"
                      maxLength={6}
                      placeholder={t("mfaChallenge.codePlaceholder")}
                      value={code}
                      onChange={(e) => handleCodeChange(e.target.value)}
                      className="h-12 text-center text-lg tracking-[0.5em] font-mono"
                      disabled={isLoading}
                      error={error || undefined}
                    />
                  </div>
                </div>

                <Button
                  type="submit"
                  className="w-full h-11"
                  disabled={code.length < 6 || isLoading}
                >
                  {isLoading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      {t("mfaChallenge.verifying")}
                    </>
                  ) : (
                    t("mfaChallenge.verify")
                  )}
                </Button>

                {error && (
                  <div className="flex items-start gap-2 rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                    <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                    <span>{error}</span>
                  </div>
                )}
              </form>
            </CardContent>

            <CardFooter className="flex-col gap-3">
              <button
                type="button"
                onClick={() => {
                  setIsBackup(!isBackup)
                  setCode("")
                  setError("")
                }}
                className="text-sm text-primary hover:underline"
              >
                {isBackup ? t("mfaChallenge.useAuthenticatorInstead") : t("mfaChallenge.useBackupCodeInstead")}
              </button>

              <Link
                to="/contact"
                className="text-sm text-muted-foreground hover:text-foreground"
              >
                {t("mfaChallenge.troubleContactSupport")}
              </Link>
            </CardFooter>
          </Card>

          <div className="mt-6 text-center">
            <Link to="/login" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
              <ArrowLeft className="h-3.5 w-3.5" />
              {t("mfaChallenge.backToSignIn")}
            </Link>
          </div>
        </div>
      </div>
    </>
  )
}
