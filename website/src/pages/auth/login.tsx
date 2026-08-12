import { useState } from "react"
import { Helmet } from "react-helmet-async"
import { Link, useSearchParams } from "react-router"
import { useAppNavigate } from "@/hooks/useAppNavigate"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { toast } from "sonner"
import { motion } from "motion/react"
import { Eye, EyeOff, Mail, Lock } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input, Label } from "@/components/ui/input"
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card"
import { useAuth } from "@/contexts/auth-provider"
import { useLocale } from "@/i18n/locale-context"
import TurnstileWidget from "@/components/shared/turnstile-widget"

const loginSchema = z.object({
  email: z.string().email("Please enter a valid email"),
  password: z.string().min(1, "Password is required"),
  rememberMe: z.boolean().optional(),
})

type LoginForm = z.infer<typeof loginSchema>

export default function LoginPage() {
  const navigate = useAppNavigate()
  const { login } = useAuth()
  const { t } = useLocale()
  const [searchParams] = useSearchParams()
  const [showPassword, setShowPassword] = useState(false)
  const [turnstileToken, setTurnstileToken] = useState("")

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginForm>({ resolver: zodResolver(loginSchema) })

  async function onSubmit(data: LoginForm) {
    try {
      const result = await login(data.email, data.password, data.rememberMe, turnstileToken)
      // If MFA is required, redirect to the challenge page
      if (result?.mfaRequired) {
        navigate("/auth/mfa-challenge", { replace: true })
        return
      }
      toast.success(t("auth.signedIn"))
      const returnUrl = searchParams.get("returnUrl")
      const isValidReturnUrl = returnUrl && returnUrl.startsWith("/") && !returnUrl.startsWith("//")
      navigate(isValidReturnUrl ? returnUrl : "/dashboard", { replace: true })
    } catch (error: unknown) {
      const apiError = error as { response?: { status?: number; data?: { detail?: string } } }
      if (apiError?.response?.status === 429) {
        const retryAfter = apiError.response.data?.detail || t("auth.tooManyAttempts")
        toast.error(retryAfter)
      } else {
        toast.error(t("auth.invalidCredentials"))
      }
    }
  }

  return (
    <>
      <Helmet><title>{`${t("common.signIn")} — Operion ERP`}</title></Helmet>
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
          <Card>
            <CardHeader className="text-center">
              <CardTitle>{t("auth.welcomeBack")}</CardTitle>
              <CardDescription>{t("auth.signInDesc")}</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="email">{t("auth.email")}</Label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input id="email" type="email" className="pl-10" placeholder={t("auth.emailPlaceholder")} {...register("email")} />
                  </div>
                  {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
                </div>
                <div className="space-y-2">
                  <Label htmlFor="password">{t("auth.password")}</Label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input id="password" type={showPassword ? "text" : "password"} className="pl-10 pr-10" placeholder={t("auth.passwordPlaceholder")} {...register("password")} />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      aria-label={showPassword ? t("mfa.hidePassword") : t("mfa.showPassword")}
                      aria-pressed={showPassword}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    >
                      {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                  {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
                </div>
                <div className="flex items-center justify-between">
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      {...register("rememberMe")}
                      className="h-4 w-4 rounded border-input text-primary focus:ring-primary"
                    />
                    {t("auth.rememberMe")}
                  </label>
                  <Link to="/forgot-password" className="text-sm text-primary hover:underline">{t("auth.forgotPassword")}</Link>
                </div>
                <TurnstileWidget onVerify={setTurnstileToken} onExpired={() => setTurnstileToken("")} className="flex justify-center" />
                <Button type="submit" className="w-full" disabled={isSubmitting}>
                  {isSubmitting ? t("auth.signingIn") : t("common.signIn")}
                </Button>
              </form>
            </CardContent>
            <CardFooter className="justify-center">
              <p className="text-sm text-muted-foreground">
                {t("auth.dontHaveAccount")}{" "}<Link to="/register" className="text-primary hover:underline font-medium">{t("common.signUp")}</Link>
              </p>
            </CardFooter>
          </Card>
          <div className="mt-6 text-center">
            <Link to="/" className="text-sm text-muted-foreground hover:text-foreground">{t("common.back")}</Link>
          </div>
        </motion.div>
      </div>
    </>
  )
}
