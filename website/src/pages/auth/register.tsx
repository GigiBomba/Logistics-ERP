import { useState } from "react"
import { Helmet } from "react-helmet-async"
import { Link, useSearchParams } from "react-router"
import { useAppNavigate } from "@/hooks/useAppNavigate"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { toast } from "sonner"
import { motion } from "motion/react"
import { Eye, EyeOff, Mail, Lock, User, Building2, Gift } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input, Label } from "@/components/ui/input"
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card"
import { Callout } from "@/components/ui/callout"
import { PasswordStrength } from "@/components/shared/password-strength"
import { useAuth } from "@/contexts/auth-provider"
import { useLocale } from "@/i18n/locale-context"
import TurnstileWidget from "@/components/shared/turnstile-widget"

const registerSchema = z.object({
  name: z.string().min(2, "Name must be at least 2 characters"),
  email: z.string().email("Please enter a valid email"),
  company_name: z.string().optional(),
  password: z.string().min(8, "Password must be at least 8 characters"),
  confirm_password: z.string(),
  referral_code: z.string().optional(),
  termsAccepted: z.literal(true, { error: "You must accept the Terms and Privacy Policy" }),
}).refine((data) => data.password === data.confirm_password, {
  message: "Passwords don't match",
  path: ["confirm_password"],
})

type RegisterForm = z.infer<typeof registerSchema>

export default function RegisterPage() {
  const navigate = useAppNavigate()
  const [searchParams] = useSearchParams()
  const { register: registerUser } = useAuth()
  const { t } = useLocale()
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [turnstileToken, setTurnstileToken] = useState("")
  const [referralError, setReferralError] = useState<string | null>(null)

  const refCodeFromUrl = searchParams.get("ref") ?? ""

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<RegisterForm>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      referral_code: refCodeFromUrl,
    },
  })

  const password = watch("password")

  async function onSubmit(data: RegisterForm) {
    setReferralError(null)
    try {
      await registerUser({
        ...data,
        turnstile_token: turnstileToken || undefined,
      })
      toast.success(t("auth.accountCreated"))
      navigate("/verify-email")
    } catch (err: unknown) {
      // Check for referral-specific errors from the backend
      if (err && typeof err === "object" && "response" in err) {
        const axiosErr = err as { response?: { status?: number; data?: { detail?: string } } }
        if (axiosErr.response?.status === 429) {
          setReferralError(t("referral.rateLimited"))
          return
        }
        const detail = axiosErr.response?.data?.detail?.toLowerCase() ?? ""
        if (detail.includes("self-referral") || detail.includes("cannot refer yourself")) {
          setReferralError(t("referral.cannotReferSelf"))
          return
        }
      }
      toast.error(t("auth.registrationFailed"))
    }
  }

  return (
    <>
      <Helmet><title>{`${t("auth.createAccount")} — Operion ERP`}</title></Helmet>
      <div className="flex min-h-[80vh] items-center justify-center px-4 py-12">
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
              <CardTitle>{t("auth.createAccount")}</CardTitle>
              <CardDescription>{t("auth.registerDesc")}</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="name">{t("auth.fullName")}</Label>
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input id="name" className="pl-10" placeholder={t("auth.namePlaceholder")} {...register("name")} />
                  </div>
                  {errors.name && <p className="text-xs text-destructive">{errors.name.message}</p>}
                </div>
                <div className="space-y-2">
                  <Label htmlFor="email">{t("auth.email")}</Label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input id="email" type="email" className="pl-10" placeholder={t("auth.emailPlaceholder")} {...register("email")} />
                  </div>
                  {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
                </div>
                <div className="space-y-2">
                  <Label htmlFor="company_name">{t("auth.companyName")}</Label>
                  <div className="relative">
                    <Building2 className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input id="company_name" className="pl-10" placeholder={t("auth.companyPlaceholder")} {...register("company_name")} />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="referral_code">{t("register.referralLabel")}</Label>
                  <div className="relative">
                    <Gift className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input id="referral_code" className="pl-10" placeholder={t("register.referralPlaceholder")} {...register("referral_code")} />
                  </div>
                  {referralError && (
                    <Callout variant="danger" title="Referral error">
                      {referralError}
                    </Callout>
                  )}
                </div>
                <div className="space-y-2">
                  <Label htmlFor="password">{t("auth.password")}</Label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input id="password" type={showPassword ? "text" : "password"} className="pl-10 pr-10" placeholder={t("auth.minChars")} {...register("password")} />
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
                  <PasswordStrength password={password} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="confirm_password">{t("auth.confirmPassword")}</Label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input id="confirm_password" type={showConfirm ? "text" : "password"} className="pl-10 pr-10" placeholder={t("auth.confirmPassword")} {...register("confirm_password")} />
                    <button
                      type="button"
                      onClick={() => setShowConfirm(!showConfirm)}
                      aria-label={showConfirm ? t("mfa.hidePassword") : t("mfa.showPassword")}
                      aria-pressed={showConfirm}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    >
                      {showConfirm ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                  {errors.confirm_password && <p className="text-xs text-destructive">{errors.confirm_password.message}</p>}
                </div>
                <div className="space-y-2">
                  <div className="flex items-start gap-2">
                    <input
                      type="checkbox"
                      id="termsAccepted"
                      className="mt-1 h-4 w-4 rounded border-input text-primary focus:ring-primary"
                      required
                      aria-required="true"
                      {...register("termsAccepted")}
                    />
                    <Label htmlFor="termsAccepted" className="text-sm font-normal leading-relaxed text-muted-foreground cursor-pointer">
                      {t("register.acceptTerms")}{" "}
                      <Link to="/terms" className="text-primary hover:underline font-medium">{t("register.termsOfService")}</Link>
                      {" and "}
                      <Link to="/privacy" className="text-primary hover:underline font-medium">{t("register.privacyPolicy")}</Link>
                    </Label>
                  </div>
                  {errors.termsAccepted && (
                    <p className="text-xs text-destructive">{errors.termsAccepted.message}</p>
                  )}
                </div>
                <TurnstileWidget
                  onVerify={setTurnstileToken}
                  onExpired={() => setTurnstileToken("")}
                  theme="auto"
                  className="flex justify-center"
                />
                <Button type="submit" className="w-full" disabled={isSubmitting}>
                  {isSubmitting ? t("auth.creatingAccount") : t("common.create")}
                </Button>
              </form>
            </CardContent>
            <CardFooter className="justify-center">
              <p className="text-sm text-muted-foreground">
                {t("auth.alreadyHaveAccount")}{" "}<Link to="/login" className="text-primary hover:underline font-medium">{t("common.signIn")}</Link>
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
