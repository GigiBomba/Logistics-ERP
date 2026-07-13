import { useState } from "react"
import { Helmet } from "react-helmet-async"
import { Link, useNavigate, useSearchParams } from "react-router"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { toast } from "sonner"
import { motion } from "motion/react"
import { authApi } from "@/api/endpoints"
import { Eye, EyeOff, Lock } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input, Label } from "@/components/ui/input"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { useLocale } from "@/i18n/locale-context"

const schema = z.object({
  password: z.string().min(8, "Password must be at least 8 characters"),
  confirm_password: z.string(),
}).refine((data) => data.password === data.confirm_password, {
  message: "Passwords don't match",
  path: ["confirm_password"],
})

type FormData = z.infer<typeof schema>

export default function ResetPasswordPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { t } = useLocale()
  const token = searchParams.get("token")
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)

  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<FormData>({
    resolver: zodResolver(schema),
  })

  function onSubmit(data: FormData) {
    authApi.resetPassword(token!, data.password).then(() => {
      toast.success(t("auth.passwordReset"))
      navigate("/login")
    }).catch(() => {
      toast.error(t("auth.resetFailed"))
    })
  }

  if (!token) {
    return (
      <>
        <Helmet><title>{t("auth.resetPassword")} — Operion ERP</title></Helmet>
        <div className="flex min-h-[80vh] items-center justify-center px-4">
          <Card className="w-full max-w-md text-center">
            <CardHeader>
              <CardTitle>{t("auth.invalidLink")}</CardTitle>
              <CardDescription>{t("auth.invalidLinkDesc")}</CardDescription>
            </CardHeader>
            <CardContent>
              <Button asChild className="w-full">
                <Link to="/forgot-password">{t("auth.requestNewLink")}</Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      </>
    )
  }

  return (
    <>
      <Helmet><title>{t("auth.setNewPassword")} — Operion ERP</title></Helmet>
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
              <CardTitle>{t("auth.setNewPassword")}</CardTitle>
              <CardDescription>{t("auth.setNewDesc")}</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="password">{t("auth.newPassword")}</Label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input id="password" type={showPassword ? "text" : "password"} className="pl-10 pr-10" placeholder={t("auth.minChars")} {...register("password")} />
                    <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                      {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                  {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
                </div>
                <div className="space-y-2">
                  <Label htmlFor="confirm_password">{t("auth.confirmNewPassword")}</Label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input id="confirm_password" type={showConfirm ? "text" : "password"} className="pl-10 pr-10" placeholder={t("auth.confirmNewPassword")} {...register("confirm_password")} />
                    <button type="button" onClick={() => setShowConfirm(!showConfirm)} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                      {showConfirm ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                  {errors.confirm_password && <p className="text-xs text-destructive">{errors.confirm_password.message}</p>}
                </div>
                <Button type="submit" className="w-full" disabled={isSubmitting}>
                  {isSubmitting ? t("common.resetting") : t("auth.resetPassword")}
                </Button>
              </form>
            </CardContent>
          </Card>
          <div className="mt-6 text-center">
            <Link to="/" className="text-sm text-muted-foreground hover:text-foreground">{t("common.back")}</Link>
          </div>
        </motion.div>
      </div>
    </>
  )
}
