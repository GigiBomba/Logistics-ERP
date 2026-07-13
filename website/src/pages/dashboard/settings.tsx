import { useState } from "react"
import { Helmet } from "react-helmet-async"
import { motion } from "motion/react"
import { Link } from "react-router"
import { Bell, Shield, Palette, Fingerprint, KeyRound, Monitor, Trash2, Download, Key, Languages, Clock, MapPin } from "lucide-react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { Callout } from "@/components/ui/callout"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { useTheme } from "@/contexts/theme-provider"
import { useLocale } from "@/i18n/locale-context"
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

export default function SettingsPage() {
  const { theme, setTheme } = useTheme()
  const { t } = useLocale()
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
                    <Button variant="outline" disabled>{t("profile.savePreferences")}</Button>
                    <p className="mt-2 text-xs text-muted-foreground">{t("profile.savePrefsPlaceholder")}</p>
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

              {/* 2FA Placeholder */}
              <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.15 }}>
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2"><Fingerprint className="h-5 w-5" /> {t("settings.twoFactor")}</CardTitle>
                    <CardDescription>{t("profile.twoFactorDesc")}</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <Callout variant="info" title={t("common.comingSoon")}>
                      {t("profile.twoFactorComingSoon")}
                    </Callout>
                    <Button variant="outline" disabled>
                      <Shield className="mr-2 h-4 w-4" />
                      {t("profile.enable2FA")}
                    </Button>
                  </CardContent>
                </Card>
              </motion.div>

              {/* Connected Sessions */}
              <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.2 }}>
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2"><Monitor className="h-5 w-5" /> {t("settings.connectedSessions")}</CardTitle>
                    <CardDescription>{t("settings.connectedSessionsDesc")}</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex items-center justify-between rounded-lg border p-3">
                      <div className="flex items-center gap-3">
                        <Monitor className="h-5 w-5 text-muted-foreground" />
                        <div>
                          <p className="text-sm font-medium">{t("profile.activeSessions")}</p>
                          <p className="text-xs text-muted-foreground">{t("profile.sessionsCount")}</p>
                        </div>
                      </div>
                      <Badge variant="success">{t("profile.normal")}</Badge>
                    </div>
                    <Button variant="outline" asChild>
                      <Link to="/dashboard/profile">{t("dashboard.manageSessions")}</Link>
                    </Button>
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
                    <Button variant="outline" disabled>
                      <Download className="mr-2 h-4 w-4" />
                      {t("settings.requestDataExport")}
                    </Button>
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
                    <Button variant="destructive" disabled>
                      <Trash2 className="mr-2 h-4 w-4" />
                      {t("settings.deleteAccount")}
                    </Button>
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
                    <Callout variant="info" title={t("common.comingSoon")}>
                      {t("settings.apiKeysComingSoon")}
                    </Callout>
                    <Button variant="outline" disabled>
                      <Key className="mr-2 h-4 w-4" />
                      {t("settings.createApiKey")}
                    </Button>
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
