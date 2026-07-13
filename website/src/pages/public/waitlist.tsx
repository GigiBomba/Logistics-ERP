import { useState } from "react"
import { Helmet } from "react-helmet-async"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { toast } from "sonner"
import { motion, AnimatePresence } from "motion/react"
import { useLocale } from "@/i18n/locale-context"
import {
  Rocket,
  Sparkles,
  Bell,
  Users,
  ArrowRight,
  Calendar,
  CheckCircle2,
  Clock,
  MapPin,
  Zap,
  ChevronDown,
  ChevronUp,
  Mail,
  Building2,
  User,
  Globe,
  FileText,
  Download,
  Key,
} from "lucide-react"
import { HeroSection } from "@/components/shared/hero-section"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { SectionHeader } from "@/components/shared/page-header"
import { FeatureCard } from "@/components/shared/feature-card"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input, Label } from "@/components/ui/input"
import { waitlistApi } from "@/api/endpoints"
import { extractApiError } from "@/api/client"
import { AxiosError } from "axios"

const benefits = [
  {
    icon: Sparkles,
    title: "waitlist.benefits.earlyAccess",
    description: "waitlist.benefits.earlyAccessDesc",
  },
  {
    icon: Bell,
    title: "waitlist.benefits.notifications",
    description: "waitlist.benefits.notificationsDesc",
  },
  {
    icon: Users,
    title: "waitlist.benefits.community",
    description: "waitlist.benefits.communityDesc",
  },
  {
    icon: Zap,
    title: "waitlist.benefits.priority",
    description: "waitlist.benefits.priorityDesc",
  },
]

const roadmap = [
  {
    phase: "Q3 2026",
    title: "AI Dispatch Assistant",
    description: "Intelligent route and load recommendations powered by machine learning.",
    status: "beta" as const,
  },
  {
    phase: "Q4 2026",
    title: "Mobile Driver App",
    description: "Native iOS and Android apps for drivers with offline mode and digital proof of delivery.",
    status: "in-progress" as const,
  },
  {
    phase: "Q1 2027",
    title: "Advanced Analytics Suite",
    description: "Custom dashboards, predictive maintenance alerts, and cost optimization insights.",
    status: "planned" as const,
  },
  {
    phase: "Q2 2027",
    title: "Multi-Entity Support",
    description: "Manage multiple subsidiaries, brands, and geographies from a single Operion instance.",
    status: "planned" as const,
  },
]

const waitlistSchema = z.object({
  company_name: z
    .string()
    .min(2, "Company name must be at least 2 characters")
    .max(200, "Company name must be at most 200 characters"),
  email: z.string().email("Please enter a valid email"),
  hp_field: z.string().optional(),
  contact_name: z.string().optional(),
  company_size: z.string().optional(),
  country: z
    .string()
    .length(2, "Country code must be 2 characters")
    .optional()
    .or(z.literal("")),
  fleet_size: z.string().optional(),
  source: z.string().optional(),
})

type WaitlistForm = z.infer<typeof waitlistSchema>

const companySizeOptions = [
  { value: "", label: "Select company size" },
  { value: "solo", label: "Solo" },
  { value: "2-10", label: "2-10" },
  { value: "11-50", label: "11-50" },
  { value: "51-200", label: "51-200" },
  { value: "200+", label: "200+" },
]

const fleetSizeOptions = [
  { value: "", label: "Select fleet size" },
  { value: "1-5", label: "1-5" },
  { value: "6-20", label: "6-20" },
  { value: "21-50", label: "21-50" },
  { value: "51-200", label: "51-200" },
  { value: "200+", label: "200+" },
]

const nextSteps = [
  {
    step: 1,
    title: "waitlist.success.step1Title",
    description: "waitlist.success.step1Desc",
    icon: Mail,
  },
  {
    step: 2,
    title: "waitlist.success.step2Title",
    description: "waitlist.success.step2Desc",
    icon: Zap,
  },
  {
    step: 3,
    title: "waitlist.success.step3Title",
    description: "waitlist.success.step3Desc",
    icon: FileText,
  },
  {
    step: 4,
    title: "waitlist.success.step4Title",
    description: "waitlist.success.step4Desc",
    icon: Download,
  },
]

export default function WaitlistPage() {
  const { t } = useLocale()
  const [submitted, setSubmitted] = useState(false)
  const [referralCode, setReferralCode] = useState<string | null>(null)
  const [duplicateMessage, setDuplicateMessage] = useState<string | null>(null)
  const [showOptional, setShowOptional] = useState(false)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    reset,
  } = useForm<WaitlistForm>({
    resolver: zodResolver(waitlistSchema),
    defaultValues: {
      source: "landing_page",
      hp_field: "",
    },
  })

  async function onSubmit(data: WaitlistForm) {
    setDuplicateMessage(null)

    // Honeypot: silently drop bot submissions
    if (data.hp_field && data.hp_field.trim().length > 0) {
      return
    }

    try {
      const response = await waitlistApi.join({
        company_name: data.company_name,
        email: data.email,
        contact_name: data.contact_name || undefined,
        company_size: data.company_size || undefined,
        country: data.country || undefined,
        fleet_size: data.fleet_size || undefined,
        source: data.source || "landing_page",
      })

      setReferralCode(response.data.referral_code)
      setSubmitted(true)
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
      <Helmet>
        <title>{t("waitlist.title")}</title>
        <meta name="description" content={t("waitlist.metaDesc")} />
      </Helmet>

      <HeroSection
        title={t("waitlist.title")}
        description={t("waitlist.heroDesc")}
        align="center"
        size="large"
      />

      {/* Countdown & Social Proof */}
      <SectionWrapper className="pt-0">
        <div className="mx-auto max-w-3xl text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground mb-8">
              <Users className="h-4 w-4" />
              <span className="font-medium text-foreground">500+</span>
              <span>{t("waitlist.professionalsJoined")}</span>
            </div>

            <Card className="border-primary/20 bg-gradient-to-br from-primary/10 via-primary/5 to-background">
              <CardContent className="p-8">
                <div className="flex items-center justify-center gap-2 mb-4">
                  <Calendar className="h-5 w-5 text-primary" />
                  <span className="text-sm font-medium text-primary">{t("waitlist.nextLaunch")}</span>
                </div>
                <h3 className="text-3xl font-bold tracking-tight sm:text-4xl">Q3 2026</h3>
                <p className="mt-2 text-muted-foreground">
                  {t("waitlist.nextLaunchDesc")}
                </p>
                <div className="mt-6 flex items-center justify-center gap-4 text-sm text-muted-foreground">
                  <div className="flex items-center gap-1.5">
                    <Clock className="h-4 w-4" />
                    <span>{t("waitlist.daysRemaining")}</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <MapPin className="h-4 w-4" />
                    <span>{t("waitlist.globalRollout")}</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </SectionWrapper>

      {/* Benefits */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title={t("waitlist.benefitsTitle")}
          description={t("waitlist.benefitsDesc")}
          className="mb-12"
        />
        <div className="mx-auto max-w-5xl grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {benefits.map((benefit, i) => (
            <FeatureCard key={benefit.title} icon={benefit.icon} title={t(benefit.title)} description={t(benefit.description)} index={i} />
          ))}
        </div>
      </SectionWrapper>

      {/* Signup Form */}
      <SectionWrapper>
        <div className="mx-auto max-w-lg">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <div className="text-center mb-8">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 mb-6">
                <Rocket className="h-6 w-6 text-primary" />
              </div>
              <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">{t("waitlist.getOnList")}</h2>
              <p className="mt-3 text-muted-foreground">
                {t("waitlist.enterEmailDesc")}
              </p>
            </div>

            <AnimatePresence mode="wait">
              {submitted ? (
                <motion.div
                  key="success"
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
                  className="space-y-6"
                >
                  <div className="rounded-xl border bg-green-50 dark:bg-green-900/20 p-6 text-center">
                    <CheckCircle2 className="mx-auto h-8 w-8 text-green-600 dark:text-green-400" />
                    <h3 className="mt-3 font-semibold text-green-800 dark:text-green-200">{t("waitlist.joined")}</h3>
                    <p className="mt-1 text-sm text-green-700 dark:text-green-300">
                      {t("waitlist.joinedDesc")}
                    </p>
                  </div>

                  <div className="space-y-4">
                    <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider text-center">
                      {t("waitlist.success.title")}
                    </h3>
                    <div className="grid gap-3 sm:grid-cols-2">
                      {nextSteps.map((item, i) => (
                        <motion.div
                          key={item.step}
                          initial={{ opacity: 0, y: 12 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ delay: i * 0.12, duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
                          className="rounded-lg border bg-card p-4"
                        >
                          <div className="flex items-start gap-3">
                            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
                              <item.icon className="h-4 w-4" />
                            </div>
                            <div>
                              <p className="text-sm font-semibold">{t(item.title)}</p>
                              <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">
                                {t(item.description)}
                              </p>
                            </div>
                          </div>
                        </motion.div>
                      ))}
                    </div>
                  </div>

                  {referralCode && (
                    <motion.div
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.6, duration: 0.35 }}
                      className="rounded-lg border bg-muted/50 p-4 text-center"
                    >
                      <p className="text-xs text-muted-foreground mb-1">{t("waitlist.success.referralCode")}</p>
                      <div className="inline-flex items-center gap-2 rounded-md bg-background border px-3 py-1.5">
                        <Key className="h-3.5 w-3.5 text-muted-foreground" />
                        <span className="text-sm font-mono font-medium">{referralCode}</span>
                      </div>
                      <p className="text-xs text-muted-foreground mt-2">
                        {t("waitlist.success.shareMessage")}
                      </p>
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

                    <div className="space-y-2">
                      <Label htmlFor="company_name">{t("waitlist.form.companyName")}</Label>
                      <div className="relative">
                        <Building2 className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
                        <Input
                          id="company_name"
                          className="pl-10"
                          placeholder={t("waitlist.form.companyNamePlaceholder")}
                          {...register("company_name")}
                        />
                      </div>
                      {errors.company_name && (
                        <p className="text-xs text-destructive">{errors.company_name.message}</p>
                      )}
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="email">{t("waitlist.form.email")}</Label>
                      <div className="relative">
                        <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
                        <Input
                          id="email"
                          type="email"
                          className="pl-10"
                          placeholder={t("waitlist.form.emailPlaceholder")}
                          {...register("email")}
                        />
                      </div>
                      {errors.email && (
                        <p className="text-xs text-destructive">{errors.email.message}</p>
                      )}
                    </div>

                    {/* Progressive disclosure */}
                    <button
                      type="button"
                      onClick={() => setShowOptional((s) => !s)}
                      className="flex items-center gap-1.5 text-sm text-primary hover:underline pt-1"
                    >
                      {t("waitlist.form.moreDetails")}
                      {showOptional ? (
                        <ChevronUp className="h-4 w-4" />
                      ) : (
                        <ChevronDown className="h-4 w-4" />
                      )}
                    </button>

                    <AnimatePresence>
                      {showOptional && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: "auto", opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
                          className="overflow-hidden"
                        >
                          <div className="space-y-4 pb-1">
                            <div className="space-y-2">
                              <Label htmlFor="contact_name">{t("waitlist.form.contactName")}</Label>
                              <div className="relative">
                                <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
                                <Input
                                  id="contact_name"
                                  className="pl-10"
                                  placeholder={t("waitlist.form.contactNamePlaceholder")}
                                  {...register("contact_name")}
                                />
                              </div>
                            </div>

                            <div className="space-y-2">
                              <Label htmlFor="company_size">{t("waitlist.form.companySize")}</Label>
                              <div className="relative">
                                <select
                                  id="company_size"
                                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 appearance-none"
                                  {...register("company_size")}
                                >
                                  {companySizeOptions.map((opt) => (
                                    <option key={opt.value} value={opt.value}>
                                      {opt.label}
                                    </option>
                                  ))}
                                </select>
                                <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
                              </div>
                            </div>

                            <div className="space-y-2">
                              <Label htmlFor="country">{t("waitlist.form.country")}</Label>
                              <div className="relative">
                                <Globe className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
                                <Input
                                  id="country"
                                  className="pl-10 uppercase"
                                  placeholder={t("waitlist.form.countryPlaceholder")}
                                  maxLength={2}
                                  {...register("country")}
                                />
                              </div>
                              {errors.country && (
                                <p className="text-xs text-destructive">{errors.country.message}</p>
                              )}
                            </div>

                            <div className="space-y-2">
                              <Label htmlFor="fleet_size">{t("waitlist.form.fleetSize")}</Label>
                              <div className="relative">
                                <select
                                  id="fleet_size"
                                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 appearance-none"
                                  {...register("fleet_size")}
                                >
                                  {fleetSizeOptions.map((opt) => (
                                    <option key={opt.value} value={opt.value}>
                                      {opt.label}
                                    </option>
                                  ))}
                                </select>
                                <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
                              </div>
                            </div>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>

                    <input type="hidden" {...register("source")} />

                    {duplicateMessage && (
                      <div className="rounded-lg border bg-amber-50 dark:bg-amber-900/20 p-3 text-sm text-amber-800 dark:text-amber-200">
                        {duplicateMessage}
                      </div>
                    )}

                    <Button
                      type="submit"
                      size="lg"
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
          </motion.div>
        </div>
      </SectionWrapper>

      {/* Launch Roadmap */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title={t("waitlist.launchRoadmap")}
          description={t("waitlist.launchRoadmapDesc")}
          className="mb-12"
        />
        <div className="mx-auto max-w-3xl">
          <div className="relative">
            <div className="absolute left-4 top-0 bottom-0 w-px bg-border" />
            <div className="space-y-8">
              {roadmap.map((item, i) => (
                <motion.div
                  key={item.title}
                  initial={{ opacity: 0, x: -10 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.1 }}
                  className="relative pl-10"
                >
                  <div className="absolute left-2 top-1.5 h-5 w-5 rounded-full border-2 bg-background flex items-center justify-center">
                    <div className={cn(
                      "h-2.5 w-2.5 rounded-full",
                      item.status === "beta" && "bg-green-500",
                      item.status === "in-progress" && "bg-yellow-500",
                      item.status === "planned" && "bg-muted-foreground"
                    )} />
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold">{item.title}</span>
                    <Badge variant={
                      item.status === "beta" ? "success" :
                      item.status === "in-progress" ? "secondary" : "outline"
                    }>
                      {item.status === "beta" ? t("waitlist.statusBeta") :
                       item.status === "in-progress" ? t("roadmap.inProgress") : t("roadmap.planned")}
                    </Badge>
                    <span className="text-sm text-muted-foreground">{item.phase}</span>
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground">{item.description}</p>
                </motion.div>
              ))}
            </div>
          </div>
        </div>
      </SectionWrapper>
    </>
  )
}

function cn(...inputs: (string | undefined | false | null)[]) {
  return inputs.filter(Boolean).join(" ")
}
