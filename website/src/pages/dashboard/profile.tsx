import { useEffect, useState } from "react"
import { Helmet } from "react-helmet-async"
import { motion } from "motion/react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { User, Lock, Bell, Globe, Monitor, Smartphone, Shield, Clock, Languages, Palette, LogOut, Fingerprint, KeyRound } from "lucide-react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input, Label } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { Callout } from "@/components/ui/callout"
import { LoadingSpinner } from "@/components/ui/loading-spinner"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { useAuth } from "@/contexts/auth-provider"
import { useTheme } from "@/contexts/theme-provider"
// TODO: Implement when backend endpoint is ready
// import { useProfile, useUpdateProfile, useChangePassword } from "@/services/queries"
import { toast } from "sonner"
import { useLocale } from "@/i18n/locale-context"
import type { UserSession, NotificationPreference } from "@/types"

const profileSchema = z.object({
  name: z.string().min(2, "Name must be at least 2 characters"),
  email: z.string().email("Please enter a valid email"),
})

const passwordSchema = z.object({
  current_password: z.string().min(1, "Current password is required"),
  new_password: z.string().min(8, "Password must be at least 8 characters"),
  confirm_password: z.string(),
}).refine((d) => d.new_password === d.confirm_password, {
  message: "Passwords don't match",
  path: ["confirm_password"],
})

type ProfileForm = z.infer<typeof profileSchema>
type PasswordForm = z.infer<typeof passwordSchema>

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

const mockSessions: UserSession[] = [
  { id: "sess-1", device: "Windows 11", browser: "Chrome 126", ip: "192.168.1.105", location: "Bucharest, Romania", last_active: "Just now", is_current: true },
  { id: "sess-2", device: "macOS Sonoma", browser: "Safari 17", ip: "203.0.113.42", location: "Remote", last_active: "2 hours ago", is_current: false },
  { id: "sess-3", device: "iPhone 15", browser: "Chrome Mobile", ip: "198.51.100.8", location: "Bucharest, Romania", last_active: "1 day ago", is_current: false },
]

const defaultNotifications: NotificationPreference = {
  email_notifications: true,
  product_updates: true,
  security_alerts: true,
  marketing_emails: false,
  blog_digest: false,
}

export default function ProfilePage() {
  const { user } = useAuth()
  const { theme, setTheme } = useTheme()
  const { t } = useLocale()
  // TODO: Implement when backend endpoint is ready
  // const { data: profile, isLoading } = useProfile()
  // const updateProfile = useUpdateProfile()
  // const changePassword = useChangePassword()

  const profile = undefined as { display_name?: string; name?: string; email: string } | undefined
  const isLoading = false
  const updateProfile = { mutate: (_data: unknown) => { toast.success(t("common.comingSoon")) }, isPending: false } as const
  const changePassword = { mutate: (_data: unknown) => { toast.success(t("common.comingSoon")) }, isPending: false } as const

  const [timezone, setTimezone] = useState("Europe/Bucharest (EET)")
  const [language, setLanguage] = useState("en")
  const [notifications, setNotifications] = useState<NotificationPreference>(defaultNotifications)

  const profileForm = useForm<ProfileForm>({
    resolver: zodResolver(profileSchema),
    defaultValues: { name: "", email: "" },
  })

  const passwordForm = useForm<PasswordForm>({
    resolver: zodResolver(passwordSchema),
  })

  useEffect(() => {
    const source = profile || user
    if (source) {
      profileForm.reset({ name: source.display_name || source.name || source.email || "", email: source.email })
    }
  }, [profile, user, profileForm])

  function onProfileSubmit(data: ProfileForm) {
    updateProfile.mutate(data)
  }

  function onPasswordSubmit(data: PasswordForm) {
    changePassword.mutate({
      current_password: data.current_password,
      new_password: data.new_password,
    })
    passwordForm.reset()
  }

  const userName = profile?.display_name || profile?.name || user?.display_name || user?.name || user?.email || "User"
  const userInitials = userName
    .split(" ")
    .map((n: string) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2)

  return (
    <>
      <Helmet><title>{t("profile.title")} — Operion ERP</title></Helmet>
      <SectionWrapper>
        <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}>
          <h1 className="text-3xl font-bold tracking-tight">{t("profile.title")}</h1>
          <p className="mt-2 text-muted-foreground">{t("profile.description")}</p>
        </motion.div>

        {isLoading ? (
          <div className="flex justify-center py-16">
            <LoadingSpinner size="lg" />
          </div>
        ) : (
          <Tabs defaultValue="general" className="mt-8">
            <TabsList className="mb-6">
              <TabsTrigger value="general">{t("profile.general")}</TabsTrigger>
              <TabsTrigger value="security">{t("profile.security")}</TabsTrigger>
              <TabsTrigger value="notifications">{t("profile.notifications")}</TabsTrigger>
              <TabsTrigger value="sessions">{t("profile.sessions")}</TabsTrigger>
            </TabsList>

            <TabsContent value="general" className="space-y-8">
              <div className="grid gap-8 lg:grid-cols-2">
                {/* Profile Information */}
                <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.1 }}>
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2"><User className="h-5 w-5" /> {t("profile.information")}</CardTitle>
                      <CardDescription>{t("profile.informationDesc")}</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <form onSubmit={profileForm.handleSubmit(onProfileSubmit)} className="space-y-4">
                        <div className="space-y-2">
                          <Label htmlFor="name">{t("auth.fullName")}</Label>
                          <Input id="name" {...profileForm.register("name")} />
                          {profileForm.formState.errors.name && <p className="text-xs text-destructive">{profileForm.formState.errors.name.message}</p>}
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="email">{t("auth.email")}</Label>
                          <Input id="email" type="email" {...profileForm.register("email")} />
                          {profileForm.formState.errors.email && <p className="text-xs text-destructive">{profileForm.formState.errors.email.message}</p>}
                        </div>
                        <Button type="submit" disabled={updateProfile.isPending}>
                          {updateProfile.isPending ? t("profile.saving") : t("profile.saveChanges")}
                        </Button>
                      </form>
                    </CardContent>
                  </Card>
                </motion.div>

                {/* Avatar Upload */}
                <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.15 }}>
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2"><User className="h-5 w-5" /> {t("profile.avatar")}</CardTitle>
                      <CardDescription>{t("profile.avatarDesc")}</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="flex items-center gap-4">
                        <Avatar size="lg">
                          <AvatarFallback>{userInitials}</AvatarFallback>
                        </Avatar>
                        <div className="flex-1">
                          <p className="text-sm font-medium">{t("profile.avatarComingSoon")}</p>
                          <p className="text-xs text-muted-foreground">{t("profile.avatarComingSoonDesc")}</p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </motion.div>

                {/* Timezone */}
                <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.2 }}>
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2"><Clock className="h-5 w-5" /> {t("profile.timezone")}</CardTitle>
                      <CardDescription>{t("profile.timezoneDesc")}</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-2">
                        <Label htmlFor="timezone">{t("profile.timezone")}</Label>
                        <select
                          id="timezone"
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

                {/* Language */}
                <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.25 }}>
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2"><Languages className="h-5 w-5" /> {t("profile.language")}</CardTitle>
                      <CardDescription>{t("profile.languageDesc")}</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-2">
                        <Label htmlFor="language">{t("profile.language")}</Label>
                        <select
                          id="language"
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
                        <p className="text-xs text-muted-foreground">{t("profile.moreLanguages")}</p>
                      </div>
                    </CardContent>
                  </Card>
                </motion.div>

                {/* Theme Preference */}
                <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.3 }}>
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2"><Palette className="h-5 w-5" /> {t("profile.theme")}</CardTitle>
                      <CardDescription>{t("profile.themeDesc")}</CardDescription>
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

                {/* Preferences placeholder */}
                <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.35 }}>
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2"><Globe className="h-5 w-5" /> {t("profile.preferences")}</CardTitle>
                      <CardDescription>{t("profile.preferencesDesc")}</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <p className="text-sm text-muted-foreground">{t("profile.preferencesPlaceholder")}</p>
                    </CardContent>
                  </Card>
                </motion.div>
              </div>
            </TabsContent>

            <TabsContent value="security" className="space-y-8">
              <div className="grid gap-8 lg:grid-cols-2">
                {/* Change Password */}
                <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.1 }}>
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2"><Lock className="h-5 w-5" /> {t("profile.changePassword")}</CardTitle>
                      <CardDescription>{t("profile.changePasswordDesc")}</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <form onSubmit={passwordForm.handleSubmit(onPasswordSubmit)} className="space-y-4">
                        <div className="space-y-2">
                          <Label htmlFor="current_password">{t("profile.currentPassword")}</Label>
                          <Input id="current_password" type="password" {...passwordForm.register("current_password")} />
                          {passwordForm.formState.errors.current_password && <p className="text-xs text-destructive">{passwordForm.formState.errors.current_password.message}</p>}
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="new_password">{t("auth.newPassword")}</Label>
                          <Input id="new_password" type="password" {...passwordForm.register("new_password")} />
                          {passwordForm.formState.errors.new_password && <p className="text-xs text-destructive">{passwordForm.formState.errors.new_password.message}</p>}
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="confirm_password">{t("auth.confirmNewPassword")}</Label>
                          <Input id="confirm_password" type="password" {...passwordForm.register("confirm_password")} />
                          {passwordForm.formState.errors.confirm_password && <p className="text-xs text-destructive">{passwordForm.formState.errors.confirm_password.message}</p>}
                        </div>
                        <Button type="submit" disabled={changePassword.isPending}>
                          {changePassword.isPending ? t("profile.changing") : t("profile.changePassword")}
                        </Button>
                      </form>
                    </CardContent>
                  </Card>
                </motion.div>

                {/* 2FA Placeholder */}
                <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.15 }}>
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2"><Fingerprint className="h-5 w-5" /> {t("profile.twoFactor")}</CardTitle>
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

                {/* Account Security */}
                <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.2 }}>
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2"><Shield className="h-5 w-5" /> {t("profile.accountSecurity")}</CardTitle>
                      <CardDescription>{t("profile.accountSecurityDesc")}</CardDescription>
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
                      <div className="flex items-center justify-between rounded-lg border p-3">
                        <div className="flex items-center gap-3">
                          <Fingerprint className="h-5 w-5 text-muted-foreground" />
                          <div>
                            <p className="text-sm font-medium">{t("profile.twoFactor")}</p>
                            <p className="text-xs text-muted-foreground">{t("profile.notEnabled")}</p>
                          </div>
                        </div>
                        <Badge variant="outline">{t("profile.disabled")}</Badge>
                      </div>
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
                    </CardContent>
                  </Card>
                </motion.div>
              </div>
            </TabsContent>

            <TabsContent value="notifications" className="space-y-8">
              <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.1 }}>
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2"><Bell className="h-5 w-5" /> {t("profile.notificationPreferences")}</CardTitle>
                    <CardDescription>{t("profile.notificationPrefsDesc")}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {([
                        { key: "email_notifications" as keyof NotificationPreference, labelKey: "profile.emailNotifications", descriptionKey: "profile.emailNotificationsDesc" },
                        { key: "product_updates" as keyof NotificationPreference, labelKey: "profile.productUpdates", descriptionKey: "profile.productUpdatesDesc" },
                        { key: "security_alerts" as keyof NotificationPreference, labelKey: "profile.securityAlerts", descriptionKey: "profile.securityAlertsDesc" },
                        { key: "marketing_emails" as keyof NotificationPreference, labelKey: "profile.marketingEmails", descriptionKey: "profile.marketingEmailsDesc" },
                        { key: "blog_digest" as keyof NotificationPreference, labelKey: "profile.blogDigest", descriptionKey: "profile.blogDigestDesc" },
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

            <TabsContent value="sessions" className="space-y-8">
              <div className="grid gap-8 lg:grid-cols-2">
                {/* Active Sessions */}
                <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.1 }}>
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2"><Monitor className="h-5 w-5" /> {t("profile.activeSessions")}</CardTitle>
                      <CardDescription>{t("profile.activeSessionsDesc")}</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-3">
                        {mockSessions.map((session) => (
                          <div key={session.id} className="flex items-center justify-between rounded-lg border p-3">
                            <div className="flex items-center gap-3">
                              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent">
                                {session.device.includes("iPhone") || session.device.includes("Mobile") ? (
                                  <Smartphone className="h-4 w-4 text-primary" />
                                ) : (
                                  <Monitor className="h-4 w-4 text-primary" />
                                )}
                              </div>
                              <div>
                                <div className="flex items-center gap-2">
                                  <p className="text-sm font-medium">{session.device}</p>
                                  {session.is_current && <Badge variant="success">{t("common.current")}</Badge>}
                                </div>
                                <p className="text-xs text-muted-foreground">
                                  {session.browser} · {session.ip} · {session.location}
                                </p>
                                <p className="text-xs text-muted-foreground">{t("profile.lastActive")}: {session.last_active}</p>
                              </div>
                            </div>
                            {!session.is_current && (
                              <Button variant="ghost" size="sm" className="text-destructive hover:text-destructive">
                                <LogOut className="h-4 w-4" />
                              </Button>
                            )}
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                </motion.div>

                {/* Connected Devices */}
                <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.15 }}>
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2"><Smartphone className="h-5 w-5" /> {t("profile.connectedDevices")}</CardTitle>
                      <CardDescription>{t("profile.connectedDevicesDesc")}</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <Callout variant="info" title={t("profile.noConnectedDevices")}>
                        {t("profile.noConnectedDevicesDesc")}
                      </Callout>
                    </CardContent>
                  </Card>
                </motion.div>
              </div>
            </TabsContent>
          </Tabs>
        )}
      </SectionWrapper>
    </>
  )
}
