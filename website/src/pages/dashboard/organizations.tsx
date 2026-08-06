import { useState } from "react"
import { Helmet } from "react-helmet-async"
import { Link } from "react-router"
import { motion } from "motion/react"
import {
  Building2,
  Users,
  ChevronRight,
  Plus,
  Crown,
  Shield,
  User,
  CheckCircle2,
  ArrowRightLeft,
  Settings,
  RefreshCw,
} from "lucide-react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Skeleton } from "@/components/ui/skeleton"
import { Callout } from "@/components/ui/callout"
import { Input, Label } from "@/components/ui/input"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { toast } from "sonner"
import { extractApiError } from "@/api/client"
import { useOrganizations, useCreateOrganization } from "@/services/queries"
import { useLocale } from "@/i18n/locale-context"

function getInitials(name: string) {
  return name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase()
}

function roleIcon(role?: string) {
  if (role === "owner") return Crown
  if (role === "admin") return Shield
  return User
}

function roleBadgeVariant(role?: string): "default" | "secondary" | "outline" | "success" | "destructive" {
  if (role === "owner") return "default"
  if (role === "admin") return "secondary"
  return "outline"
}

export default function OrganizationsPage() {
  const { t } = useLocale()
  const { data: orgs, isLoading, isError, error, refetch } = useOrganizations()
  const activeOrg = orgs?.[0] ?? null
  const createOrganization = useCreateOrganization()
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [newOrgName, setNewOrgName] = useState("")

  if (isLoading) {
    return (
      <>
        <Helmet>
          <title>{t("organizations.pageTitle")}</title>
        </Helmet>
        <SectionWrapper>
          <Skeleton className="h-9 w-48" />
          <Skeleton className="h-5 w-96 mt-2" />
          <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Card key={i}>
                <CardContent className="p-5">
                  <div className="flex items-start gap-4">
                    <Skeleton className="h-12 w-12 rounded-full" />
                    <div className="flex-1 space-y-2">
                      <Skeleton className="h-4 w-32" />
                      <Skeleton className="h-3 w-24" />
                      <Skeleton className="h-5 w-48" />
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </SectionWrapper>
      </>
    )
  }

  if (isError) {
    return (
      <>
        <Helmet>
          <title>{t("organizations.pageTitle")}</title>
        </Helmet>
        <SectionWrapper>
          <Callout variant="danger" title={t("organizations.failedToLoad")}>
            {error instanceof Error ? error.message : t("organizations.unexpectedError")}
          </Callout>
          <Button variant="outline" className="mt-4" onClick={() => refetch()}>
            <RefreshCw className="mr-2 h-4 w-4" />
            {t("organizations.tryAgain")}
          </Button>
        </SectionWrapper>
      </>
    )
  }

  if (!orgs || orgs.length === 0) {
    return (
      <>
        <Helmet>
          <title>{t("organizations.pageTitle")}</title>
        </Helmet>
        <SectionWrapper>
          <h1 className="text-3xl font-bold tracking-tight">{t("organizations.title")}</h1>
          <p className="mt-2 text-muted-foreground">
            {t("organizations.description")}
          </p>
          <Callout variant="info" title={t("organizations.noOrganizations")} className="mt-8">
            {t("organizations.noOrganizationsDesc")}
          </Callout>
        </SectionWrapper>
      </>
    )
  }

  return (
    <>
      <Helmet>
        <title>{t("organizations.pageTitle")}</title>
      </Helmet>
      <SectionWrapper>
        {/* Page Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
        >
          <h1 className="text-3xl font-bold tracking-tight">{t("organizations.title")}</h1>
          <p className="mt-2 text-muted-foreground">
            {t("organizations.description")}
          </p>
        </motion.div>

        {/* Organization Selector */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.05 }}
          className="mt-8"
        >
          <h2 className="text-lg font-semibold tracking-tight">{t("organizations.selector")}</h2>
          <p className="text-sm text-muted-foreground">
            {t("organizations.selectorDesc")}
          </p>

          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {orgs.map((org, i) => {
              const isActive = org.id === activeOrg?.id
              const RoleIcon = roleIcon(org.user_role)
              return (
                <motion.div
                  key={org.id}
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: 0.1 + i * 0.05 }}
                >
                  <Card
                    className={
                      isActive
                        ? "border-primary/50 shadow-sm ring-1 ring-primary/20"
                        : ""
                    }
                  >
                    <CardContent className="p-5">
                      <div className="flex items-start gap-4">
                        <Avatar size="lg">
                          <AvatarFallback className="bg-primary/10 text-primary text-lg">
                            {getInitials(org.name)}
                          </AvatarFallback>
                        </Avatar>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <p className="font-semibold text-sm truncate">{org.name}</p>
                            {isActive && (
                              <Badge variant="success" className="shrink-0">
                                <CheckCircle2 className="mr-1 h-3 w-3" />
                                {t("organizations.current")}
                              </Badge>
                            )}
                          </div>
                          <p className="text-xs text-muted-foreground mt-0.5">
                            {org.industry}
                          </p>
                          <div className="mt-3 flex flex-wrap items-center gap-2">
                            <Badge variant="secondary" className="text-xs">
                              <Users className="mr-1 h-3 w-3" />
                              {t("organizations.members").replace("{count}", String(org.member_count ?? 0))}
                            </Badge>
                            {org.subscription_tier && (
                              <Badge
                                variant={
                                  org.subscription_tier === "Enterprise"
                                    ? "default"
                                    : org.subscription_tier === "Professional"
                                      ? "success"
                                      : "secondary"
                                }
                                className="text-xs"
                              >
                                {org.subscription_tier}
                              </Badge>
                            )}
                            <Badge variant={roleBadgeVariant(org.user_role)} className="text-xs">
                              <RoleIcon className="mr-1 h-3 w-3" />
                              {org.user_role ? org.user_role.charAt(0).toUpperCase() + org.user_role.slice(1) : t("organizations.memberRole")}
                            </Badge>
                          </div>
                        </div>
                      </div>

                      <div className="mt-4 flex items-center gap-2">
                        {!isActive && (
                          <Button variant="outline" size="sm" className="flex-1">
                            <ArrowRightLeft className="mr-1.5 h-3.5 w-3.5" />
                            {t("organizations.switchToThisOrg")}
                          </Button>
                        )}
                        <Button
                          variant={isActive ? "outline" : "ghost"}
                          size="sm"
                          className={isActive ? "w-full" : "shrink-0"}
                          asChild
                        >
                          <Link to={`/dashboard/organizations/${org.slug}/settings`}>
                            <Settings className="mr-1.5 h-3.5 w-3.5" />
                            {t("organizations.manage")}
                            <ChevronRight className="ml-1 h-3 w-3" />
                          </Link>
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                </motion.div>
              )
            })}
          </div>
        </motion.div>

        {/* Current Organization Detail Card */}
        {activeOrg && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.2 }}
            className="mt-10"
          >
            <h2 className="text-lg font-semibold tracking-tight">{t("organizations.currentOrganization")}</h2>
            <div className="mt-4 grid gap-6 lg:grid-cols-3">
              <Card className="lg:col-span-2">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Building2 className="h-5 w-5" />
                    {activeOrg.name}
                  </CardTitle>
                  <CardDescription>
                    {t("organizations.currentOrganizationDesc")}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-1">
                      <p className="text-xs text-muted-foreground">{t("organizations.industry")}</p>
                      <p className="text-sm font-medium">{activeOrg.industry}</p>
                    </div>
                    <div className="space-y-1">
                      <p className="text-xs text-muted-foreground">{t("organizations.size")}</p>
                      <p className="text-sm font-medium">{t("organizations.sizeEmployees").replace("{size}", activeOrg.size ?? "")}</p>
                    </div>
                    <div className="space-y-1">
                      <p className="text-xs text-muted-foreground">{t("organizations.address")}</p>
                      <p className="text-sm font-medium">{activeOrg.address}</p>
                    </div>
                    <div className="space-y-1">
                      <p className="text-xs text-muted-foreground">{t("organizations.city")}</p>
                      <p className="text-sm font-medium">
                        {activeOrg.city}, {activeOrg.country}
                      </p>
                    </div>
                    <div className="space-y-1">
                      <p className="text-xs text-muted-foreground">{t("organizations.phone")}</p>
                      <p className="text-sm font-medium">{activeOrg.phone}</p>
                    </div>
                    <div className="space-y-1">
                      <p className="text-xs text-muted-foreground">{t("organizations.website")}</p>
                      <p className="text-sm font-medium">{activeOrg.website}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">{t("organizations.quickStats")}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">{t("organizations.membersLabel")}</span>
                    <span className="text-sm font-medium">{activeOrg.member_count ?? 0}</span>
                  </div>
                  {activeOrg.subscription_tier && (
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">{t("organizations.plan")}</span>
                      <Badge
                        variant={
                          activeOrg.subscription_tier === "Enterprise"
                            ? "default"
                            : activeOrg.subscription_tier === "Professional"
                              ? "success"
                              : "secondary"
                        }
                      >
                        {activeOrg.subscription_tier}
                      </Badge>
                    </div>
                  )}
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">{t("organizations.yourRole")}</span>
                    <Badge variant={roleBadgeVariant(activeOrg.user_role)}>
                      {activeOrg.user_role ? activeOrg.user_role.charAt(0).toUpperCase() + activeOrg.user_role.slice(1) : t("organizations.memberRole")}
                    </Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">{t("organizations.created")}</span>
                    <span className="text-sm font-medium">
                      {new Date(activeOrg.created_at ?? "").toLocaleDateString()}
                    </span>
                  </div>
                </CardContent>
              </Card>
            </div>
          </motion.div>
        )}

        {/* Create Organization */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.25 }}
          className="mt-10"
        >
          <h2 className="text-lg font-semibold tracking-tight">{t("organizations.createOrganization")}</h2>
          <p className="text-sm text-muted-foreground">
            {t("organizations.createOrganizationDesc")}
          </p>

          <Card className="mt-4">
            <CardContent className="p-6">
              <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                  <Plus className="h-6 w-6 text-primary" />
                </div>
                <div className="flex-1">
                  <p className="font-semibold text-sm">{t("organizations.startNewOrganization")}</p>
                  <p className="text-sm text-muted-foreground mt-0.5">
                    {t("organizations.startNewOrganizationDesc")}
                  </p>
                </div>
                {!showCreateForm && (
                  <Button className="shrink-0" onClick={() => setShowCreateForm(true)}>
                    <Plus className="mr-2 h-4 w-4" />
                    {t("organizations.createOrganization")}
                  </Button>
                )}
              </div>

              {showCreateForm && (
                <div className="mt-4 space-y-3 rounded-lg border p-4">
                  <div className="space-y-2">
                    <Label htmlFor="new-org-name">{t("organizations.name")}</Label>
                    <Input
                      id="new-org-name"
                      placeholder={t("organizations.namePlaceholder")}
                      value={newOrgName}
                      onChange={(e) => setNewOrgName(e.target.value)}
                    />
                  </div>
                  <div className="flex gap-2">
                    <Button
                      onClick={() => {
                        createOrganization.mutate(
                          { name: newOrgName },
                          {
                            onSuccess: () => {
                              toast.success(t("organizations.createdSuccess"))
                              setShowCreateForm(false)
                              setNewOrgName("")
                            },
                            onError: (err) => {
                              toast.error(extractApiError(err))
                            },
                          }
                        )
                      }}
                      disabled={!newOrgName.trim() || createOrganization.isPending}
                    >
                      <Plus className="mr-2 h-4 w-4" />
                      {t("organizations.create")}
                    </Button>
                    <Button variant="ghost" onClick={() => { setShowCreateForm(false); setNewOrgName("") }}>
                      {t("common.cancel")}
                    </Button>
                  </div>
                </div>
              )}

              {!showCreateForm && (
                <p className="mt-3 text-xs text-muted-foreground text-center sm:text-left">
                  {t("organizations.createOrganizationDesc")}
                </p>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </SectionWrapper>
    </>
  )
}
