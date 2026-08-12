import { useState, useEffect, useRef } from "react"
import { Helmet } from "react-helmet-async"
import { motion } from "motion/react"
import { Link } from "react-router"
import { Bell, Shield, Palette, KeyRound, Monitor, Trash2, Download, Key, Languages, Clock, MapPin, Lock, QrCode, Mail, Loader2, Eye, EyeOff, Copy, CheckCircle } from "lucide-react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input, Label } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { Callout } from "@/components/ui/callout"
import { Tooltip } from "@/components/ui/tooltip"
import { Skeleton } from "@/components/ui/skeleton"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { useTheme } from "@/contexts/theme-provider"
import { useLocale } from "@/i18n/locale-context"
import { useAuth } from "@/contexts/auth-provider"
import { useSessions, useCreateTicket, useUpdateNotificationPreferences, useMfaStatus, useMfaEnroll, useMfaConfirm, useMfaDisable } from "@/services/queries"
import { toast } from "sonner"
import type { NotificationPreference } from "@/types"

const timezones = [
  "UTC",
  "Europe/Bucharest (EET)",
  "Europe/London (GMT)",
  "Europe/Berlin (CET)",
  "America/New_York (EST)",
  "America/Los_Angeles (PST)",
  "Asia/Dubai (GST)",
  "Asia/Singapore (SGT)",
]

const availableLanguages = [
  { code: "en", labelKey: "language.en" },
  { code: "ro", labelKey: "language.ro" },
  { code: "de", labelKey: "language.de" },
  { code: "fr", labelKey: "language.fr" },
  { code: "es", labelKey: "language.es" },
  { code: "pl", labelKey: "language.pl" },
]

const unavailableLanguages = [] as { code: string; labelKey: string }[]

const regions = [
  { code: "RO", labelKey: "settings.romania" },
  { code: "GB", labelKey: "settings.unitedKingdom" },
  { code: "DE", labelKey: "settings.germany" },
  { code: "US", labelKey: "settings.unitedStates" },
  { code: "CA", labelKey: "settings.canada" },
]

const defaultNotifications: NotificationPreference = {
  email_notifications: true,
  product_updates: true,
  security_alerts: true,
  marketing_emails: false,
  blog_digest: false,
}

/* ─── MFA Card (inline in this file to avoid new-file overhead) ─── */
function MfaCard() {
  const { t } = useLocale()
  const { data: mfaStatus, isLoading: mfaStatusLoading } = useMfaStatus()
  const enrollMutation = useMfaEnroll()
  const confirmMutation = useMfaConfirm()
  const disableMutation = useMfaDisable()

  const [phase, setPhase] = useState<"idle" | "enrolling" | "confirming" | "done" | "disabling">("idle")
  const [confirmCode, setConfirmCode] = useState("")
  const [savedChecked, setSavedChecked] = useState(false)
  const [disablePassword, setDisablePassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [copied, setCopied] = useState(false)
  const codeInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (phase === "confirming") {
      codeInputRef.current?.focus()
    }
  }, [phase])

  const handleEnroll = () => {
    enrollMutation.mutate(undefined, {
      onSuccess: () => {
        setPhase("confirming")
        toast.success(t("mfa.toast.enrollStarted"))
      },
      onError: (err: any) => {
        toast.error(err?.response?.data?.detail || err?.message || t("mfa.toast.enrollFailed"))
      },
    })
  }

  const handleConfirm = () => {
    if (confirmCode.length !== 6) {
      toast.error(t("mfa.toast.enterFullCode"))
      return
    }
    confirmMutation.mutate(confirmCode, {
      onSuccess: () => {
        setPhase("done")
        toast.success(t("mfa.toast.enabled"))
      },
      onError: (err: any) => {
        toast.error(err?.response?.data?.detail || err?.message || t("mfa.toast.invalidCode"))
      },
    })
  }

  const handleDisable = () => {
    if (!disablePassword) {
      toast.error(t("mfa.toast.enterPassword"))
      return
    }
    disableMutation.mutate(disablePassword, {
      onSuccess: () => {
        toast.success(t("mfa.toast.disabled"))
        setPhase("idle")
        setDisablePassword("")
      },
      onError: (err: any) => {
        toast.error(err?.response?.data?.detail || err?.message || t("mfa.toast.disableFailed"))
      },
    })
  }

  const downloadBackupCodes = () => {
    const codes = (enrollMutation.data as any)?.backup_codes || (confirmMutation.data as any)?.backup_codes || []
    if (!codes.length) return
    const blob = new Blob([codes.join("\n")], { type: "text/plain" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = "operion-backup-codes.txt"
    a.click()
    URL.revokeObjectURL(url)
  }

  const enrollData = enrollMutation.data as any
  const secret = enrollData?.secret || ""
  const otpauthUri = enrollData?.otpauth_uri || ""

  const backupCodes = enrollData?.backup_codes || (confirmMutation.data as any)?.backup_codes || []

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      toast.error(t("mfa.toast.copyFailed"))
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><Lock className="h-5 w-5" /> {t("settings.twoFactor")}</CardTitle>
        <CardDescription>{t("profile.twoFactorDesc")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {mfaStatusLoading ? (
          <div className="space-y-3">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-9 w-full" />
          </div>
        ) : mfaStatus?.mfa_enabled ? (
          <>
            <Callout variant="success" title={t("mfa.statusEnabled")}>
              <p className="text-sm">{t("mfa.statusEnabledDesc")}</p>
            </Callout>
            {phase === "disabling" ? (
              <div className="space-y-3">
                <div className="space-y-2">
                  <Label htmlFor="mfa-disable-password">{t("mfa.disable.passwordLabel")}</Label>
                  <div className="relative">
                    <Input
                      id="mfa-disable-password"
                      type={showPassword ? "text" : "password"}
                      value={disablePassword}
                      onChange={(e) => setDisablePassword(e.target.value)}
                      placeholder={t("mfa.currentPasswordPlaceholder")}
                      className="pr-10"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                      aria-label={showPassword ? t("mfa.hidePassword") : t("mfa.showPassword")}
                    >
                      {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                </div>
                <div className="flex gap-3">
                  <Button variant="outline" size="sm" onClick={() => setPhase("idle")}>{t("common.cancel")}</Button>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={handleDisable}
                    disabled={disableMutation.isPending}
                  >
                    {disableMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                    {t("mfa.disableNow")}
                  </Button>
                </div>
                {disableMutation.isError && (
                  <Callout variant="danger" title={t("common.errorTitle")}>
                    <p className="text-sm">{(disableMutation.error as any)?.response?.data?.detail || (disableMutation.error as any)?.message || t("mfa.toast.disableFailed")}</p>
                  </Callout>
                )}
              </div>
            ) : (
              <Button variant="outline" onClick={() => setPhase("disabling")}>
                <Shield className="mr-2 h-4 w-4" />
                {t("mfa.disable.disableButton")}
              </Button>
            )}
          </>
        ) : (
          <>
            {phase === "idle" && (
              <>
                <p className="text-sm text-muted-foreground">
                  {t("settings.twoFactorDescription")}
                </p>
                <Button
                  variant="outline"
                  onClick={handleEnroll}
                  disabled={enrollMutation.isPending}
                >
                  {enrollMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Shield className="mr-2 h-4 w-4" />}
                  {t("profile.enable2FA")}
                </Button>
                {enrollMutation.isError && (
                  <Callout variant="danger" title={t("mfa.enrollmentFailed")}>
                    <p className="text-sm">{(enrollMutation.error as any)?.response?.data?.detail || (enrollMutation.error as any)?.message || t("mfa.toast.enrollFailed")}</p>
                  </Callout>
                )}
              </>
            )}

            {phase === "confirming" && enrollData && (
              <div className="space-y-4">
                <Callout variant="info" title={t("mfa.setupAuthenticator")}>
                  <p className="text-sm">{t("mfa.enroll.scanPrompt")}</p>
                </Callout>

                {/* QR placeholder + manual key */}
                <div className="rounded-lg border bg-muted/30 p-4 space-y-3">
                  <div className="mx-auto flex h-40 w-40 items-center justify-center rounded-lg bg-white p-2">
                    <QrCode className="h-24 w-24 text-foreground" />
                  </div>
                  <div className="space-y-1">
                    <p className="text-xs font-medium text-muted-foreground">{t("mfa.enroll.manualKeyLabel")}</p>
                    <div className="flex items-center gap-2">
                      <code className="flex-1 rounded-md bg-muted px-3 py-2 text-sm font-mono select-all">{secret}</code>
                      <button
                        onClick={() => copyToClipboard(secret)}
                        className="rounded-md border p-2 hover:bg-muted"
                        aria-label={t("mfa.copySetupKey")}
                      >
                        {copied ? <CheckCircle className="h-4 w-4 text-green-600" /> : <Copy className="h-4 w-4" />}
                      </button>
                    </div>
                  </div>
                  <div className="space-y-1">
                    <p className="text-xs font-medium text-muted-foreground">{t("mfa.otpauthUri")}</p>
                    <p className="text-xs text-muted-foreground break-all select-all">{otpauthUri}</p>
                  </div>
                </div>

                {/* Confirm code */}
                <div className="space-y-2">
                  <Label htmlFor="mfa-confirm-code">{t("mfa.verificationCode")}</Label>
                  <input
                    ref={codeInputRef}
                    id="mfa-confirm-code"
                    type="text"
                    inputMode="numeric"
                    maxLength={6}
                    value={confirmCode}
                    onChange={(e) => {
                      const val = e.target.value.replace(/\D/g, "").slice(0, 6)
                      setConfirmCode(val)
                      if (val.length === 6) {
                        setTimeout(() => handleConfirm(), 100)
                      }
                    }}
                    placeholder="000000"
                    className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-center text-lg tracking-widest shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                    aria-live="polite"
                  />
                  <p className="text-xs text-muted-foreground">{t("mfa.autoAdvance")}</p>
                </div>

                <div className="flex gap-3">
                  <Button variant="outline" size="sm" onClick={() => { setPhase("idle"); setConfirmCode("") }}>{t("common.cancel")}</Button>
                  <Button size="sm" onClick={handleConfirm} disabled={confirmCode.length !== 6 || confirmMutation.isPending}>
                    {confirmMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                    {t("mfa.enroll.verifyEnable")}
                  </Button>
                </div>
                {confirmMutation.isError && (
                  <Callout variant="danger" title={t("mfa.invalidCodeTitle")}>
                    <p className="text-sm">{(confirmMutation.error as any)?.response?.data?.detail || (confirmMutation.error as any)?.message || t("mfa.toast.verificationFailed")}</p>
                  </Callout>
                )}
              </div>
            )}

            {phase === "done" && (
              <div className="space-y-4">
                <Callout variant="success" title={t("mfa.enroll.successTitle")}>
                  <p className="text-sm">{t("mfa.enroll.successBody")}</p>
                </Callout>

                <div className="rounded-lg border bg-muted/30 p-4">
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                    {backupCodes.map((code: string, i: number) => (
                      <code key={i} className="rounded-md bg-background px-2 py-1.5 text-center text-sm font-mono select-all">{code}</code>
                    ))}
                  </div>
                </div>

                <div className="flex items-start gap-2">
                  <input
                    id="saved-backup-codes"
                    type="checkbox"
                    checked={savedChecked}
                    onChange={(e) => setSavedChecked(e.target.checked)}
                    className="mt-0.5 h-4 w-4 rounded border-primary text-primary"
                  />
                  <Label htmlFor="saved-backup-codes" className="text-sm font-normal cursor-pointer">
                    {t("mfa.enroll.backupCodesGate")}
                  </Label>
                </div>

                <div className="flex gap-3">
                  <Button variant="outline" size="sm" onClick={downloadBackupCodes}>
                    <Download className="mr-2 h-4 w-4" />
                    {t("mfa.enroll.downloadTxt")}
                  </Button>
                  <Button size="sm" disabled={!savedChecked} onClick={() => setPhase("idle")}>
                    {t("mfa.enroll.done")}
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}

export default function SettingsPage() {
  const { theme, setTheme } = useTheme()
  const { t } = useLocale()
  const { user } = useAuth()
  const { data: sessions, isLoading: sessionsLoading, isError: sessionsError } = useSessions()
  const createTicket = useCreateTicket()
  const updatePrefs = useUpdateNotificationPreferences()
  const [notifications, setNotifications] = useState<NotificationPreference>(defaultNotifications)
  const [timezone, setTimezone] = useState("Europe/Bucharest (EET)")
  const [language, setLanguage] = useState("en")
  const [region, setRegion] = useState("RO")

  return (
    <>
      <Helmet><title>{t("settings.title")} — Operion ERP</title></Helmet>
      <SectionWrapper>
        <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}>
          <h1 className="text-3xl font-bold tracking-tight">{t("settings.title")}</h1>
          <p className="mt-2 text-muted-foreground">{t("settings.description")}</p>
        </motion.div>

        <Tabs defaultValue="appearance" className="mt-8">
          <TabsList className="mb-6">
            <TabsTrigger value="appearance">{t("settings.appearance")}</TabsTrigger>
            <TabsTrigger value="notifications">{t("settings.notifications")}</TabsTrigger>
            <TabsTrigger value="language">{t("settings.languageRegion")}</TabsTrigger>
            <TabsTrigger value="security">{t("settings.security")}</TabsTrigger>
            <TabsTrigger value="privacy">{t("settings.dataPrivacy")}</TabsTrigger>
          </TabsList>

          <TabsContent value="appearance" className="space-y-8">
            <div className="grid gap-6 lg:grid-cols-2">
              {/* Theme */}
              <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.1 }}>
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2"><Palette className="h-5 w-5" /> {t("settings.appearance")}</CardTitle>
                    <CardDescription>{t("settings.appearanceDesc")}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="flex gap-2">
                      {(["light", "dark", "system"] as const).map((t) => (
                        <Button
                          key={t}
                          variant={theme === t ? "default" : "outline"}
                          size="sm"
                          onClick={() => setTheme(t)}
                          className="capitalize"
                        >
                          {t}
                        </Button>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            </div>
          </TabsContent>

          <TabsContent value="notifications" className="space-y-8">
            <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.1 }}>
              <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2"><Bell className="h-5 w-5" /> {t("settings.notifications")}</CardTitle>
                    <CardDescription>{t("settings.notificationsDesc")}</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {([
                      { key: "email_notifications" as keyof NotificationPreference, labelKey: "profile.emailNotifications", descriptionKey: "profile.emailNotificationsDesc" },
                      { key: "product_updates" as keyof NotificationPreference, labelKey: "profile.productUpdates", descriptionKey: "profile.productUpdatesDesc" },
                      { key: "security_alerts" as keyof NotificationPreference, labelKey: "profile.securityAlerts", descriptionKey: "profile.securityAlertsDesc" },
                      { key: "marketing_emails" as keyof NotificationPreference, labelKey: "profile.marketingEmails", descriptionKey: "profile.marketingEmailsDesc" },
                    ]).map((item) => (
                      <label
                        key={item.key}
                        className="flex items-start gap-3 rounded-lg border p-4 cursor-pointer transition-colors hover:bg-muted/50"
                      >
                        <input
                          type="checkbox"
                          className="mt-0.5 h-4 w-4 rounded border-primary text-primary focus:ring-primary"
                          checked={notifications[item.key]}
                          onChange={(e) =>
                            setNotifications((prev) => ({ ...prev, [item.key]: e.target.checked }))
                          }
                        />
                        <div>
                          <p className="text-sm font-medium">{t(item.labelKey)}</p>
                          <p className="text-xs text-muted-foreground">{t(item.descriptionKey)}</p>
                        </div>
                      </label>
                    ))}
                  </div>
                  <div className="mt-6">
                    <Button
                      variant="outline"
                      onClick={() =>
                        updatePrefs.mutate(notifications, {
                          onSuccess: () => toast.success(t("profile.preferencesSaved")),
                          onError: () => toast.error(t("profile.preferencesSaveError")),
                        })
                      }
                      disabled={updatePrefs.isPending}
                    >
                      {updatePrefs.isPending ? (
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      ) : null}
                      {t("profile.savePreferences")}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          </TabsContent>

          <TabsContent value="language" className="space-y-8">
            <div className="grid gap-6 lg:grid-cols-2">
              {/* Language */}
              <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.1 }}>
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2"><Languages className="h-5 w-5" /> {t("settings.language")}</CardTitle>
                    <CardDescription>{t("settings.languageDesc")}</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="settings-language">{t("settings.language")}</Label>
                      <select
                        id="settings-language"
                        value={language}
                        onChange={(e) => setLanguage(e.target.value)}
                        className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                      >
                          {availableLanguages.map((lang) => (
                            <option key={lang.code} value={lang.code}>{t(lang.labelKey)}</option>
                          ))}
                          {unavailableLanguages.map((lang) => (
                            <option key={lang.code} value={lang.code} disabled className="text-muted-foreground/60">{t(lang.labelKey)}</option>
                          ))}
                      </select>
                    </div>
                    <p className="text-xs text-muted-foreground">{t("settings.moreLanguages")}</p>
                  </CardContent>
                </Card>
              </motion.div>

              {/* Region */}
              <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.15 }}>
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2"><MapPin className="h-5 w-5" /> {t("settings.region")}</CardTitle>
                    <CardDescription>{t("settings.regionDesc")}</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="settings-region">{t("settings.countryRegion")}</Label>
                      <select
                        id="settings-region"
                        value={region}
                        onChange={(e) => setRegion(e.target.value)}
                        className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                      >
                        {regions.map((r) => (
                          <option key={r.code} value={r.code}>{t(r.labelKey)}</option>
                        ))}
                      </select>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>

              {/* Timezone */}
              <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.2 }}>
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2"><Clock className="h-5 w-5" /> {t("settings.timezone")}</CardTitle>
                    <CardDescription>{t("settings.timezoneDesc")}</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="settings-timezone">{t("settings.timezone")}</Label>
                      <select
                        id="settings-timezone"
                        value={timezone}
                        onChange={(e) => setTimezone(e.target.value)}
                        className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                      >
                        {timezones.map((tz) => (
                          <option key={tz} value={tz}>{tz}</option>
                        ))}
                      </select>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            </div>
          </TabsContent>

          <TabsContent value="security" className="space-y-8">
            <div className="grid gap-6 lg:grid-cols-2">
              {/* Security */}
              <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.1 }}>
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2"><Shield className="h-5 w-5" /> {t("settings.security")}</CardTitle>
                    <CardDescription>{t("settings.securityDesc")}</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {/* Account email */}
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <Mail className="h-4 w-4" />
                      <span>{t("settings.account")}: {user?.email}</span>
                    </div>
                    {/* Password row */}
                    <div className="flex items-center justify-between rounded-lg border p-3">
                      <div className="flex items-center gap-3">
                        <KeyRound className="h-5 w-5 text-muted-foreground" />
                        <div>
                          <p className="text-sm font-medium">{t("profile.password")}</p>
                          <p className="text-xs text-muted-foreground">{t("profile.lastChanged")}</p>
                        </div>
                      </div>
                      <Badge variant="success">{t("profile.secure")}</Badge>
                    </div>
                    <Button variant="outline" asChild>
                      <Link to="/dashboard/profile">{t("settings.changePassword")}</Link>
                    </Button>
                  </CardContent>
                </Card>
              </motion.div>

              {/* Two-Factor Authentication */}
              <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.15 }}>
                <MfaCard />
              </motion.div>

              {/* Connected Sessions */}
              <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.2 }}>
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2"><Monitor className="h-5 w-5" /> {t("settings.connectedSessions")}</CardTitle>
                    <CardDescription>{t("settings.connectedSessionsDesc")}</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {sessionsLoading ? (
                      <div className="space-y-3">
                        {[1, 2].map((i) => (
                          <div key={i} className="flex items-center gap-3 rounded-lg border p-3">
                            <Skeleton className="h-8 w-8 rounded-lg" />
                            <div className="flex-1 space-y-1.5">
                              <Skeleton className="h-4 w-48" />
                              <Skeleton className="h-3 w-32" />
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : sessionsError ? (
                      <Callout variant="danger" title={t("settings.sessionsLoadError")}>
                        {t("settings.sessionsLoadErrorDesc")}
                      </Callout>
                    ) : (
                      <>
                        {/* Session summary */}
                        <div className="flex items-center justify-between rounded-lg border p-3">
                          <div className="flex items-center gap-3">
                            <Monitor className="h-5 w-5 text-muted-foreground" />
                            <div>
                              <p className="text-sm font-medium">{t("profile.activeSessions")}</p>
                              <p className="text-xs text-muted-foreground">
                                {sessions ? `${sessions.length} ${t("settings.activeSessions")}` : "—"}
                              </p>
                            </div>
                          </div>
                          <Badge variant="success">{t("profile.normal")}</Badge>
                        </div>

                        {/* Current session preview (first session) */}
                        {sessions && sessions.length > 0 && (
                          <div className="rounded-lg border p-3">
                            <p className="mb-2 text-xs font-medium text-muted-foreground">{t("settings.currentSession")}</p>
                            <div className="flex items-center gap-3">
                              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent">
                                <Monitor className="h-4 w-4 text-primary" />
                              </div>
                              <div className="min-w-0 flex-1">
                                <p className="truncate text-sm font-medium">
                                  {sessions[0].device_name || sessions[0].device_platform || t("settings.unknownDevice")}
                                </p>
                                {sessions[0].ip_address && (
                                  <p className="truncate text-xs text-muted-foreground">
                                    {sessions[0].ip_address}
                                  </p>
                                )}
                              </div>
                            </div>
                          </div>
                        )}

                        <Button variant="outline" asChild>
                          <Link to="/dashboard/profile">{t("dashboard.manageSessions")}</Link>
                        </Button>
                      </>
                    )}
                  </CardContent>
                </Card>
              </motion.div>
            </div>
          </TabsContent>

          <TabsContent value="privacy" className="space-y-8">
            <div className="grid gap-6 lg:grid-cols-2">
              {/* Data & Privacy */}
              <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.1 }}>
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2"><Download className="h-5 w-5" /> {t("settings.dataExport")}</CardTitle>
                    <CardDescription>{t("settings.dataExportDesc")}</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <Callout variant="info" title={t("common.comingSoon")}>
                      {t("settings.dataExportComingSoon")}
                    </Callout>
                    <div className="flex flex-col gap-2">
                      <Button variant="outline" disabled>
                        <Download className="mr-2 h-4 w-4" />
                        {t("settings.requestDataExport")}
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() =>
                          createTicket.mutate(
                            {
                              subject: "Data Export Request",
                              description: "I would like to request a full export of my account data.",
                              priority: "low",
                            },
                            {
                              onSuccess: () => toast.success(t("settings.ticketSubmitted")),
                              onError: () => toast.error(t("settings.ticketFailed")),
                            }
                          )
                        }
                        disabled={createTicket.isPending}
                      >
                        {createTicket.isPending ? (
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        ) : (
                          <Mail className="mr-2 h-4 w-4" />
                        )}
                        {t("settings.requestViaSupport")}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>

              {/* Delete Account */}
              <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.15 }}>
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2"><Trash2 className="h-5 w-5" /> {t("settings.deleteAccount")}</CardTitle>
                    <CardDescription>{t("settings.deleteAccountDesc")}</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <Callout variant="danger" title={t("settings.warning")}>
                      {t("settings.deleteAccountWarning")}
                    </Callout>
                    <div className="flex flex-col gap-2">
                      <Button variant="destructive" disabled>
                        <Trash2 className="mr-2 h-4 w-4" />
                        {t("settings.deleteAccount")}
                      </Button>
                      <Button variant="outline" asChild>
                        <Link to="/contact?subject=Account%20Deletion%20Request">
                          <Mail className="mr-2 h-4 w-4" />
                          {t("settings.contactSupport")}
                        </Link>
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>

              {/* API Keys */}
              <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.2 }}>
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2"><Key className="h-5 w-5" /> {t("settings.apiKeys")}</CardTitle>
                    <CardDescription>{t("settings.apiKeysDesc")}</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <p className="text-sm text-muted-foreground">
                      {t("settings.apiKeysRoadmapDesc")}
                    </p>

                    {/* API Keys preview */}
                    <div className="rounded-lg border-2 border-dashed border-muted-foreground/30 p-6 text-center">
                      <Key className="mx-auto mb-2 h-10 w-10 text-muted-foreground/40" />
                      <p className="text-sm font-medium">{t("settings.apiKeysComingSoon")}</p>
                    </div>

                    {/* Disabled Create Button with Tooltip */}
                    <Tooltip content={t("settings.apiKeysComingInUpdate")}>
                      <div>
                        <Button variant="outline" disabled className="w-full">
                          <Key className="mr-2 h-4 w-4" />
                          {t("settings.createApiKey")}
                        </Button>
                      </div>
                    </Tooltip>
                  </CardContent>
                </Card>
              </motion.div>
            </div>
          </TabsContent>
        </Tabs>
      </SectionWrapper>
    </>
  )
}
