import { useState, useRef, useEffect } from "react"
import { SeoHead } from "@/components/seo/seo-head"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { toast } from "sonner"
import { motion, AnimatePresence, useInView } from "motion/react"
import { useLocale } from "@/i18n/locale-context"
import {
  Sparkles,
  Bell,
  Calendar,
  Percent,
  ArrowRight,
  CheckCircle2,
  Clock,
  Mail,
  Building2,
  Users,
  Key,
  Bot,
  Workflow,
  MessageCircle,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input, Label } from "@/components/ui/input"
import { CopyButton } from "@/components/ui/copy-button"
import { Skeleton } from "@/components/ui/skeleton"
import { waitlistApi } from "@/api/endpoints"
import { useWaitlistCount } from "@/services/queries"
import { extractApiError } from "@/api/client"
import { AxiosError } from "axios"
import TurnstileWidget from "@/components/shared/turnstile-widget"
import { trackEvent } from "@/services/analytics"

const benefits = [
  {
    icon: Sparkles,
    titleKey: "waitlist.benefits.earlyAccess",
    descKey: "waitlist.benefits.earlyAccessDesc",
  },
  {
    icon: Bot,
    titleKey: "waitlist.benefits.aiCopilot",
    descKey: "waitlist.benefits.aiCopilotDesc",
  },
  {
    icon: Workflow,
    titleKey: "waitlist.benefits.workflowAutomation",
    descKey: "waitlist.benefits.workflowAutomationDesc",
  },
  {
    icon: Bell,
    titleKey: "waitlist.benefits.notifications",
    descKey: "waitlist.benefits.notificationsDesc",
  },
  {
    icon: Calendar,
    titleKey: "waitlist.benefits.extendedTrial",
    descKey: "waitlist.benefits.extendedTrialDesc",
  },
  {
    icon: Percent,
    titleKey: "waitlist.benefits.reducedPrice",
    descKey: "waitlist.benefits.reducedPriceDesc",
  },
]

const waitlistSchema = z.object({
  company_name: z
    .string()
    .min(2, "Company name must be at least 2 characters")
    .max(200, "Company name must be at most 200 characters"),
  email: z.string().email("Please enter a valid email"),
  hp_field: z.string().optional(),
  source: z.string().optional(),
})

type WaitlistForm = z.infer<typeof waitlistSchema>

function AnimatedCounter({ target }: { target: number }) {
  const ref = useRef<HTMLSpanElement>(null)
  const isInView = useInView(ref, { once: true })
  const [count, setCount] = useState(0)

  useEffect(() => {
    if (!isInView) return
    let current = 0
    const duration = 1500
    const increment = Math.ceil(target / (duration / 16))
    const timer = setInterval(() => {
      current += increment
      if (current >= target) {
        setCount(target)
        clearInterval(timer)
      } else {
        setCount(current)
      }
    }, 16)
    return () => clearInterval(timer)
  }, [isInView, target])

  return (
    <span ref={ref} className="font-semibold text-white tabular-nums">
      {count}+
    </span>
  )
}

export default function WaitlistPage() {
  const { t } = useLocale()
  const [submitted, setSubmitted] = useState(false)
  const [referralCode, setReferralCode] = useState<string | null>(null)
  const [duplicateMessage, setDuplicateMessage] = useState<string | null>(null)
  const [turnstileToken, setTurnstileToken] = useState<string>("")
  const {
    data: countData,
    isLoading: countLoading,
  } = useWaitlistCount()

  // Fall back to the previous hardcoded figure if the live count is unavailable
  const waitlistCount = countData?.count ?? 500

  const {
    register,
    handleSubmit,
    getValues,
    formState: { errors, isSubmitting },
    reset,
  } = useForm<WaitlistForm>({
    resolver: zodResolver(waitlistSchema),
    defaultValues: {
      source: "landing_page",
      hp_field: "",
    },
  })

  // Analytics: log page view of the waitlist funnel
  useEffect(() => {
    trackEvent("waitlist_view", "engagement", getValues("source") || "landing_page")
  }, [getValues])

  async function onSubmit(data: WaitlistForm) {
    setDuplicateMessage(null)

    if (data.hp_field && data.hp_field.trim().length > 0) {
      return
    }

    // Analytics: log form submit attempt (after honeypot check, before API call)
    trackEvent("waitlist_submit_attempt", "engagement", data.source || "landing_page")

    try {
      const response = await waitlistApi.join({
        company_name: data.company_name,
        email: data.email,
        source: data.source || "landing_page",
        turnstile_token: turnstileToken || undefined,
      })

      setReferralCode(response.data.referral_code)
      setSubmitted(true)
      // Analytics: log successful signup
      trackEvent("waitlist_submit_success", "engagement", data.source || "landing_page")
      reset()
    } catch (error) {
      if (error instanceof AxiosError) {
        if (error.response?.status === 409) {
          setDuplicateMessage(t("waitlist.error.alreadyJoined"))
          return
        }
        if (error.response?.status === 429) {
          toast.error(t("waitlist.error.rateLimited"))
          return
        }
      }
      toast.error(extractApiError(error))
    }
  }

  return (
    <>
      <SeoHead
        title={t("waitlist.title")}
        description={t("waitlist.metaDesc")}
        canonical="https://operionerp.xyz/waitlist"
      />

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-primary/90 via-primary to-primary/80" />
        <div className="absolute inset-0 hidden dark:block bg-black/50" />
        <div className="absolute inset-0 opacity-10">
          <div className="absolute -top-24 -right-24 h-96 w-96 rounded-full bg-white blur-3xl" />
          <div className="absolute -bottom-24 -left-24 h-96 w-96 rounded-full bg-white blur-3xl" />
        </div>

        <div className="relative container-wide py-20 md:py-28 lg:py-36">
          <div className="mx-auto max-w-3xl text-center">
            <motion.div
              initial={{ opacity: 0, y: 24 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
            >
              <h1 className="text-4xl font-bold tracking-tight text-white sm:text-5xl lg:text-6xl">
                {t("waitlist.heroTitle")}
              </h1>
              <p className="mt-5 text-lg text-white/80 sm:text-xl max-w-2xl mx-auto">
                {t("waitlist.heroDesc")}
              </p>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 24 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.15, ease: [0.22, 1, 0.36, 1] }}
              className="mt-10"
            >
              <div className="mx-auto max-w-xl rounded-2xl bg-white/95 dark:bg-background/95 p-6 sm:p-8 shadow-2xl ring-1 ring-white/20 backdrop-blur-sm">
                <AnimatePresence mode="wait">
                  {submitted ? (
                    <motion.div
                      key="success"
                      initial={{ opacity: 0, scale: 0.96 }}
                      animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.96 }}
                      transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
                      className="text-center space-y-5"
                    >
                      <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/30">
                        <CheckCircle2 className="h-7 w-7 text-green-600 dark:text-green-400" />
                      </div>
                      <div>
                        <h3 className="text-xl font-semibold text-foreground">
                          {t("waitlist.joined")}
                        </h3>
                          <p className="mt-1 text-sm text-muted-foreground">
                            {t("waitlist.success.nextSteps")}
                          </p>
                      </div>

                      {referralCode && (
                        <motion.div
                          initial={{ opacity: 0, y: 8 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ delay: 0.3, duration: 0.35 }}
                          className="rounded-xl border bg-muted/50 p-4 space-y-3"
                        >
                          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
                            {t("waitlist.success.referralCode")}
                          </p>
                          <div className="flex items-center justify-center gap-2">
                            <div className="inline-flex items-center gap-2 rounded-lg bg-background border px-4 py-2">
                              <Key className="h-4 w-4 text-primary" />
                              <span className="text-base font-mono font-semibold tracking-wide text-foreground">
                                {referralCode}
                              </span>
                            </div>
                            <CopyButton text={referralCode} aria-label={t("waitlist.success.copyReferralCode")} />
                          </div>
                          <p className="text-xs text-muted-foreground">
                            {t("waitlist.success.shareMessage")}
                          </p>
                          <a
                            href={`https://wa.me/?text=${encodeURIComponent(`M-am înscris pe lista de acces timpuriu Operion! Folosește codul meu de recomandare: ${referralCode} → https://operionerp.xyz/waitlist?ref=${referralCode}`)}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={() => trackEvent("referral_shared", "referral", `whatsapp:${referralCode}`)}
                            className="inline-flex items-center justify-center gap-2 w-full rounded-lg bg-[#25D366] hover:bg-[#20BD5A] text-white text-sm font-medium px-4 py-2.5 transition-colors"
                          >
                            <MessageCircle className="h-4 w-4" />
                            {t("waitlist.whatsappShare")}
                          </a>
                        </motion.div>
                      )}
                    </motion.div>
                  ) : (
                    <motion.div
                      key="form"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                    >
                      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
                        {/* Honeypot */}
                        <div
                          aria-hidden="true"
                          style={{ position: "absolute", left: "-9999px" }}
                        >
                          <label htmlFor="hp_field">Website</label>
                          <input
                            id="hp_field"
                            type="text"
                            tabIndex={-1}
                            autoComplete="off"
                            {...register("hp_field")}
                          />
                        </div>

                        <div className="grid gap-4 sm:grid-cols-2">
                          <div className="space-y-2 text-left">
                            <Label htmlFor="company_name" className="text-foreground">
                              {t("waitlist.form.companyName")}
                            </Label>
                            <div className="relative">
                              <Building2 className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
                              <Input
                                id="company_name"
                                className="pl-10 h-11"
                                placeholder={t("waitlist.form.companyNamePlaceholder")}
                                {...register("company_name")}
                              />
                            </div>
                            {errors.company_name && (
                              <p className="text-xs text-destructive">
                                {errors.company_name.message}
                              </p>
                            )}
                          </div>

                          <div className="space-y-2 text-left">
                            <Label htmlFor="email" className="text-foreground">
                              {t("waitlist.form.email")}
                            </Label>
                            <div className="relative">
                              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
                              <Input
                                id="email"
                                type="email"
                                className="pl-10 h-11"
                                placeholder={t("waitlist.form.emailPlaceholder")}
                                {...register("email")}
                              />
                            </div>
                            {errors.email && (
                              <p className="text-xs text-destructive">
                                {errors.email.message}
                              </p>
                            )}
                          </div>
                        </div>

                        {duplicateMessage && (
                          <div className="rounded-lg border bg-amber-50 dark:bg-amber-900/20 p-3 text-sm text-amber-800 dark:text-amber-200 text-left">
                            {duplicateMessage}
                          </div>
                        )}

                        <input type="hidden" {...register("source")} />

                        <TurnstileWidget
                          onVerify={setTurnstileToken}
                          onExpired={() => setTurnstileToken("")}
                          className="flex justify-center"
                        />

                        <p className="text-center text-xs text-amber-600 dark:text-amber-400 font-medium">
                          {t("waitlist.urgencyNote")}
                        </p>

                        <Button
                          type="submit"
                          size="xl"
                          className="w-full"
                          disabled={isSubmitting}
                        >
                          {isSubmitting ? (
                            <span className="flex items-center gap-2">
                              <Clock className="h-4 w-4 animate-spin" />
                              {t("waitlist.form.joining")}
                            </span>
                          ) : (
                            <span className="flex items-center gap-2">
                              {t("waitlist.joinButton")}
                              <ArrowRight className="h-4 w-4" />
                            </span>
                          )}
                        </Button>
                      </form>

                      <p className="mt-4 text-center text-xs text-muted-foreground">
                        {t("waitlist.noSpam")}
                      </p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.6, delay: 0.3 }}
              className="mt-6 flex items-center justify-center gap-2 text-sm text-white/80"
            >
              <Users className="h-4 w-4" />
              {countLoading ? (
                <Skeleton className="h-5 w-12 rounded bg-white/20" />
              ) : (
                <AnimatedCounter target={waitlistCount} />
              )}
              <span>{t("waitlist.professionalsJoined")}</span>
            </motion.div>
          </div>
        </div>
      </section>

      {/* Benefits */}
      <section className="py-16 md:py-24 bg-muted/30">
        <div className="container-wide">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
            className="text-center mb-12"
          >
              <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
                {t("waitlist.benefitsTitle")}
              </h2>
              <p className="mt-3 text-lg text-muted-foreground max-w-xl mx-auto">
                {t("waitlist.benefits.subtitle")}
              </p>
          </motion.div>

          <div className="mx-auto max-w-5xl grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {benefits.map((benefit, i) => (
              <motion.div
                key={benefit.titleKey}
                initial={{ opacity: 0, y: 24 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{
                  duration: 0.45,
                  delay: i * 0.1,
                  ease: [0.22, 1, 0.36, 1],
                }}
              >
                <div className="group relative h-full rounded-2xl border bg-background p-6 transition-all hover:-translate-y-1 hover:shadow-xl hover:border-primary/20">
                  <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary transition-colors group-hover:bg-primary group-hover:text-primary-foreground">
                    <benefit.icon className="h-6 w-6" />
                  </div>
                  <h3 className="text-lg font-semibold tracking-tight">
                    {t(benefit.titleKey)}
                  </h3>
                  <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
                    {t(benefit.descKey)}
                  </p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>
    </>
  )
}
