import { useState } from "react"
import { Helmet } from "react-helmet-async"
import { motion } from "motion/react"
import { toast } from "sonner"
import {
  Gift,
  Copy,
  Check,
  Users,
  TrendingUp,
  Share2,
  Clock,
  CheckCircle2,
  Loader2,
  Send,
} from "lucide-react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/input"
import { Callout } from "@/components/ui/callout"
import { StatCard } from "@/components/shared/stat-card"
import { EmptyState } from "@/components/shared/empty-state"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { extractApiError } from "@/api/client"
import { useLocale } from "@/i18n/locale-context"
import { useReferrals, useCreateReferral, useWriteAuditLog } from "@/services/queries"
import { useProfile } from "@/services/queries"

export default function ReferralsPage() {
  const { t } = useLocale()
  const { data, isLoading, error } = useReferrals()
  const { data: profile } = useProfile()
  const [copied, setCopied] = useState(false)
  const [referEmail, setReferEmail] = useState("")
  const [referError, setReferError] = useState<string | null>(null)
  const createReferral = useCreateReferral()
  const writeAuditLog = useWriteAuditLog()

  const referralCode = "waitlist-ref" // Will be fetched from user's waitlist record
  const referralLink = `${window.location.origin}/register?ref=${referralCode}`

  function validateReferralEmail(email: string): string | null {
    const trimmed = email.trim()
    if (!trimmed) return t("referral.enterEmail")
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!emailRegex.test(trimmed)) return t("referral.enterValidEmail")

    // Self-referral check: referrer and referee email must not be identical (case-insensitive)
    if (profile?.email && trimmed.toLowerCase() === profile.email.toLowerCase()) {
      return t("referral.cannotReferSelf")
    }

    // Local-part check: if domains are the same, local parts must differ
    const currentLocal = profile?.email?.split("@")[0]?.toLowerCase()
    const currentDomain = profile?.email?.split("@")[1]?.toLowerCase()
    const refLocal = trimmed.split("@")[0].toLowerCase()
    const refDomain = trimmed.split("@")[1].toLowerCase()
    if (currentDomain && currentDomain === refDomain && currentLocal === refLocal) {
      return t("referral.cannotReferSelf")
    }

    return null
  }

  async function handleReferSubmit(e: React.FormEvent) {
    e.preventDefault()
    setReferError(null)

    const error = validateReferralEmail(referEmail)
    if (error) {
      setReferError(error)
      return
    }

    try {
      await createReferral.mutateAsync({ referred_email: referEmail.trim() })

      // Log the referral creation to the audit trail
      writeAuditLog.mutate({
        action: "referral_created",
        target_type: "referral",
        metadata: { referred_email: referEmail.trim() },
      })

      toast.success(t("referral.sent"))
      setReferEmail("")
    } catch (err: unknown) {
      // Handle rate-limit (429) errors
      if (err && typeof err === "object" && "response" in err) {
        const axiosErr = err as { response?: { status?: number } }
        if (axiosErr.response?.status === 429) {
          setReferError(t("referral.rateLimited"))
          return
        }
      }
      setReferError(extractApiError(err) || t("referral.failedToSend"))
    }
  }

  async function handleCopyLink() {
    try {
      await navigator.clipboard.writeText(referralLink)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Fallback: select the input
      const input = document.getElementById("referral-link-input") as HTMLInputElement
      if (input) {
        input.select()
        document.execCommand("copy")
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
      }
    }
  }

  const howItWorks = [
    {
      step: 1,
      icon: Gift,
      title: t("referral.step1"),
    },
    {
      step: 2,
      icon: Users,
      title: t("referral.step2"),
    },
    {
      step: 3,
      icon: TrendingUp,
      title: t("referral.step3"),
    },
  ]

  return (
    <>
      <Helmet>
        <title>{t("referral.title")} — Operion ERP</title>
      </Helmet>

      <SectionWrapper>
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
        >
          <div className="flex items-center gap-3 mb-2">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10">
              <Gift className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight">{t("referral.title")}</h1>
              <p className="text-muted-foreground">{t("referral.description")}</p>
            </div>
          </div>
        </motion.div>

        {/* Stats */}
        {isLoading ? (
          <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-28 animate-pulse rounded-xl bg-muted" />
            ))}
          </div>
        ) : error ? (
          <Callout variant="danger" title={t("referral.failedToLoad")} className="mt-8">
            {extractApiError(error)}
          </Callout>
        ) : (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1, duration: 0.4 }}
            className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
          >
            <StatCard
              value={String(data?.total_referrals ?? 0)}
              label={t("referral.referredUsers")}
              icon={Users}
            />
            <StatCard
              value={String(data?.pending_referrals ?? 0)}
              label={t("referral.pendingRewards")}
              icon={Clock}
            />
            <StatCard
              value={String(data?.completed_referrals ?? 0)}
              label={t("referral.rewardsEarned")}
              icon={CheckCircle2}
            />
          </motion.div>
        )}

        {/* Referral Code & Link */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2, duration: 0.4 }}
          className="mt-8"
        >
          <Card className="border-primary/20 bg-gradient-to-br from-primary/5 via-primary/[0.02] to-background">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <Share2 className="h-5 w-5 text-primary" />
                {t("referral.yourLink")}
              </CardTitle>
              <CardDescription>{t("referral.shareMessage")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-2">
                <Input
                  id="referral-link-input"
                  value={referralLink}
                  readOnly
                  className="font-mono text-sm flex-1"
                />
                <Button variant="default" onClick={handleCopyLink} className="shrink-0 gap-2">
                  {copied ? (
                    <>
                      <Check className="h-4 w-4" />
                      {t("referral.copied")}
                    </>
                  ) : (
                    <>
                      <Copy className="h-4 w-4" />
                      {t("referral.copyCode")}
                    </>
                  )}
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                {t("referral.terms")}
              </p>
            </CardContent>
          </Card>
        </motion.div>

        {/* How it Works */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3, duration: 0.4 }}
          className="mt-8"
        >
          <h2 className="text-xl font-bold tracking-tight mb-4">{t("referral.howItWorks")}</h2>
          <div className="grid gap-4 sm:grid-cols-3">
            {howItWorks.map((item) => (
              <Card key={item.step}>
                <CardContent className="p-6">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary mb-4">
                    <item.icon className="h-5 w-5" />
                  </div>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground">
                      {item.step}
                    </span>
                    <span className="text-sm text-muted-foreground">{t("referral.stepLabel").replace("{number}", String(item.step))}</span>
                  </div>
                  <p className="font-medium">{item.title}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </motion.div>

        {/* Refer a Friend by Email */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4, duration: 0.4 }}
          className="mt-8"
        >
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <Send className="h-5 w-5 text-primary" />
                {t("referral.referAFriend")}
              </CardTitle>
              <CardDescription>
                {t("referral.referAFriendDesc")}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleReferSubmit} className="space-y-4">
                <div className="flex gap-2">
                  <div className="flex-1">
                    <Label htmlFor="refer-email" className="sr-only">
                      {t("referral.friendsEmail")}
                    </Label>
                    <Input
                      id="refer-email"
                      type="email"
                      placeholder={t("referral.friendsEmailPlaceholder")}
                      value={referEmail}
                      onChange={(e) => {
                        setReferEmail(e.target.value)
                        if (referError) setReferError(null)
                      }}
                      disabled={createReferral.isPending}
                    />
                  </div>
                  <Button type="submit" disabled={createReferral.isPending || !referEmail.trim()}>
                    {createReferral.isPending ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        {t("referral.sending")}
                      </>
                    ) : (
                      t("referral.sendInvite")
                    )}
                  </Button>
                </div>
                {referError && (
                  <Callout variant="danger" title={t("referral.unableToSend")}>
                    {referError}
                  </Callout>
                )}
                {createReferral.isSuccess && (
                  <Callout variant="success" title={t("referral.sent")}>
                    {t("referral.sentDesc")}
                  </Callout>
                )}
              </form>
            </CardContent>
          </Card>
        </motion.div>

        {/* Referral List */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.45, duration: 0.4 }}
          className="mt-8"
        >
          <h2 className="text-xl font-bold tracking-tight mb-4">{t("referral.referredUsers")}</h2>
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : data?.referrals && data.referrals.length > 0 ? (
            <Card>
              <CardContent className="p-0">
                <div className="divide-y">
                  {data.referrals.map((ref) => (
                    <div
                      key={ref.id}
                      className="flex items-center justify-between px-6 py-4"
                    >
                      <div className="flex items-center gap-3">
                        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-muted">
                          <Users className="h-4 w-4 text-muted-foreground" />
                        </div>
                        <div>
                          <p className="text-sm font-medium">{ref.referred_email}</p>
                          <p className="text-xs text-muted-foreground">
                            {new Date(ref.created_at).toLocaleDateString()}
                          </p>
                        </div>
                      </div>
                      <Badge
                        variant={
                          ref.status === "completed"
                            ? "success"
                            : ref.status === "pending"
                              ? "secondary"
                              : "outline"
                        }
                      >
                        {ref.status === "completed"
                          ? t("referral.completed")
                          : ref.status === "pending"
                            ? t("referral.pending")
                            : ref.status}
                      </Badge>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="p-6">
                <EmptyState
                  title={t("referral.noReferrals")}
                  description={t("referral.shareMessage")}
                />
              </CardContent>
            </Card>
          )}
        </motion.div>

        {/* Terms */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.55, duration: 0.4 }}
          className="mt-8"
        >
          <Card className="bg-muted/30">
            <CardContent className="p-4 text-xs text-muted-foreground leading-relaxed space-y-2">
              <div>
                <p className="font-medium text-foreground mb-1">{t("referral.termsTitle")}</p>
                <ul className="list-disc list-inside space-y-1">
                  <li>{t("referral.terms")}</li>
                  <li>{t("referral.termsDiscount")}</li>
                  <li>{t("referral.termsCode")}</li>
                  <li>{t("referral.termsRewards")}</li>
                  <li>{t("referral.termsCombine")}</li>
                </ul>
              </div>
              <p className="text-xs text-muted-foreground italic">
                {t("referral.abuseNote")}
              </p>
            </CardContent>
          </Card>
        </motion.div>
      </SectionWrapper>
    </>
  )
}
