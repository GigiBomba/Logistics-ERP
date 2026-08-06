import { useState } from "react"
import { Helmet } from "react-helmet-async"
import { motion } from "motion/react"
import { Building2, Hash, CreditCard, Users, Briefcase, Upload, Mail, UserPlus, Layers, TrendingUp } from "lucide-react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { LoadingSpinner } from "@/components/ui/loading-spinner"
import { Input, Label } from "@/components/ui/input"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { useLocale } from "@/i18n/locale-context"
import { EmptyState } from "@/components/shared/empty-state"
import { toast } from "sonner"
import { extractApiError } from "@/api/client"
import { useCompany, useOrganizationMembers, useOrganizationInvitations, useInviteMember, useLicenses } from "@/services/queries"

function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^\w\s-]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .trim()
}

export default function CompanyPage() {
  const { t } = useLocale()
  const { data: company, isLoading } = useCompany()
  const { data: licenses } = useLicenses()

  const companySlug = company?.company_name ? slugify(company.company_name) : ""
  const { data: members = [] } = useOrganizationMembers(companySlug)
  const { data: invitations = [] } = useOrganizationInvitations(companySlug)
  const inviteMember = useInviteMember()
  const [showInviteForm, setShowInviteForm] = useState(false)
  const [inviteEmail, setInviteEmail] = useState("")
  const [inviteRole, setInviteRole] = useState<"admin" | "member">("member")

  const companyInfo = company ? [
    { label: "Company Name", value: company.company_name || company.name || "" },
    { label: "Address", value: company.address || "" },
    { label: "City", value: company.city || "" },
    { label: "Country", value: company.country || "" },
    { label: "Postal Code", value: company.postal_code || "" },
    { label: "Phone", value: company.phone || "" },
    { label: "Website", value: company.website || "" },
  ] : [
    { label: "Company Name", value: "..." },
    { label: "Address", value: "..." },
    { label: "City", value: "..." },
    { label: "Country", value: "..." },
    { label: "Postal Code", value: "..." },
    { label: "Phone", value: "..." },
    { label: "Website", value: "..." },
  ]

  const companyName = company?.company_name || company?.name || ""
  const initials = companyName
    .split(" ")
    .map((n: string) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2) || "CO"

  const planTier = company?.subscription_tier
    ? company.subscription_tier.charAt(0).toUpperCase() + company.subscription_tier.slice(1)
    : "Starter"

  const memberCount = members?.length ?? 0
  const totalSeats = licenses?.reduce((sum, l) => sum + l.seats, 0) ?? 0
  const usedSeats = licenses?.reduce((sum, l) => sum + l.seats_used, 0) ?? 0
  const pendingInvites = members?.filter((m) => m.status === "pending").length ?? 0

  if (isLoading) {
    return (
      <>
        <Helmet><title>{t("company.pageTitle")}</title></Helmet>
        <SectionWrapper>
          <div className="flex justify-center py-32">
            <LoadingSpinner size="lg" />
          </div>
        </SectionWrapper>
      </>
    )
  }

  return (
    <>
      <Helmet><title>{t("company.pageTitle")}</title></Helmet>
      <SectionWrapper>
        <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}>
          <h1 className="text-3xl font-bold tracking-tight">{t("company.heading")}</h1>
          <p className="mt-2 text-muted-foreground">{t("company.description")}</p>
        </motion.div>

        <Tabs defaultValue="overview" className="mt-8">
          <TabsList className="mb-6">
            <TabsTrigger value="overview">{t("company.general")}</TabsTrigger>
            <TabsTrigger value="team">{t("company.team")}</TabsTrigger>
            <TabsTrigger value="billing">{t("company.billing")}</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-8">
            <div className="grid gap-8 lg:grid-cols-3">
              {/* Company Logo + Info */}
              <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.1 }} className="lg:col-span-2">
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2"><Building2 className="h-5 w-5" /> {t("company.companyInfo")}</CardTitle>
                    <CardDescription>{t("company.companyInfoDesc")}</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    <div className="flex items-center gap-4">
                      <Avatar size="lg">
                        <AvatarFallback className="bg-primary/10 text-primary text-lg">{initials}</AvatarFallback>
                      </Avatar>
                      <div>
                        <p className="text-sm font-medium">{t("company.companyLogo")}</p>
                        <p className="text-xs text-muted-foreground">{t("company.companyLogoDesc")}</p>
                      </div>
                    </div>

                    <div className="grid gap-4 sm:grid-cols-2">
                      {companyInfo.map((item) => (
                        <div key={item.label} className="space-y-1">
                          <p className="text-xs text-muted-foreground">{item.label}</p>
                          <p className="text-sm font-medium">{item.value}</p>
                        </div>
                      ))}
                      <div className="space-y-1">
                        <p className="text-xs text-muted-foreground">{t("company.employeeCount")}</p>
                        <p className="text-sm font-medium">{memberCount}</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>

              {/* Quick Stats */}
              <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.15 }} className="space-y-6">
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base">{t("company.quickStats")}</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Users className="h-4 w-4" /> {t("company.teamSize")}
                      </div>
                      <span className="text-sm font-medium">{memberCount}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Layers className="h-4 w-4" /> {t("company.departments")}
                      </div>
                      <span className="text-sm font-medium">—</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <TrendingUp className="h-4 w-4" /> {t("company.plan")}
                      </div>
                      <Badge variant="success">{planTier}</Badge>
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Briefcase className="h-4 w-4" /> {t("company.licensesUsed")}
                      </div>
                      <span className="text-sm font-medium">{usedSeats} / {totalSeats}</span>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base">{t("company.info")}</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {/* TODO: Wire to a real logo upload endpoint when backend supports multipart upload */}
                    <Button variant="outline" className="w-full" disabled title={t("company.logoUploadTitle")}>
                      <Upload className="mr-2 h-4 w-4" /> {t("company.uploadLogo")}
                    </Button>
                    {/* TODO: Wire to useUpdateCompany() mutation — PATCH /api/v1/company — once the endpoint is confirmed working */}
                    <Button variant="outline" className="w-full" disabled title={t("company.editDetailsTitle")}>
                      <Mail className="mr-2 h-4 w-4" /> {t("company.editDetails")}
                    </Button>
                  </CardContent>
                </Card>
              </motion.div>
            </div>

            {/* VAT Information */}
            <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.2 }}>
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2"><Hash className="h-5 w-5" /> {t("company.vatInfo")}</CardTitle>
                  <CardDescription>{t("company.vatInfo")}</CardDescription>
                </CardHeader>
                <CardContent>
                  {company?.vat_number ? (
                    <p className="text-sm font-medium">{company.vat_number}</p>
                  ) : (
                    <EmptyState
                      title={t("company.noVatInfo")}
                      description={t("company.vatComingSoonDesc")}
                    />
                  )}
                </CardContent>
              </Card>
            </motion.div>
          </TabsContent>

          <TabsContent value="team" className="space-y-8">
            <div className="grid gap-8 lg:grid-cols-2">
              {/* Team Management */}
              <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.1 }}>
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2"><Users className="h-5 w-5" /> {t("company.team")}</CardTitle>
                    <CardDescription>{t("company.teamDesc")}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    {members.length > 0 ? (
                      <div className="space-y-3">
                        {members.map((member) => (
                          <div key={member.id} className="flex items-center justify-between rounded-lg border p-3">
                            <div className="flex items-center gap-3">
                              <Avatar className="h-8 w-8">
                                <AvatarFallback className="bg-accent text-xs">
                                  {(member.name || member.email || "?")[0]?.toUpperCase() ?? "?"}
                                </AvatarFallback>
                              </Avatar>
                              <div>
                                <p className="text-sm font-medium">{member.name || member.email}</p>
                                <p className="text-xs text-muted-foreground capitalize">{member.role}</p>
                              </div>
                            </div>
                            <Badge variant={member.status === "active" ? "success" : "secondary"}>
                              {member.status}
                            </Badge>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <EmptyState title={t("company.noTeamMembers")} description={t("company.comingSoonDesc")} />
                    )}
                  </CardContent>
                </Card>
              </motion.div>

              {/* Departments */}
              <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.15 }}>
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2"><Layers className="h-5 w-5" /> {t("company.departments")}</CardTitle>
                    <CardDescription>{t("company.departmentsDesc")}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <EmptyState
                      title={t("company.departmentsComingSoon")}
                      description={t("company.departmentsComingSoonDesc")}
                    />
                  </CardContent>
                </Card>
              </motion.div>

              {/* Invitations */}
              <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.2 }}>
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2"><UserPlus className="h-5 w-5" /> {t("company.invitations")}</CardTitle>
                    <CardDescription>{t("company.invitationsDesc")}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    {invitations.length > 0 ? (
                      <div className="space-y-2 mb-4">
                        {invitations.map((inv) => (
                          <div key={inv.id} className="flex items-center justify-between rounded-lg border p-3">
                            <div className="flex items-center gap-3">
                              <Mail className="h-4 w-4 text-muted-foreground" />
                              <div>
                                <p className="text-sm font-medium">{inv.email}</p>
                                <p className="text-xs text-muted-foreground capitalize">{inv.role}</p>
                              </div>
                            </div>
                            <Badge variant="secondary">{inv.status}</Badge>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <EmptyState
                        title={t("company.noPendingInvitations")}
                        description={t("company.noPendingInvitationsDesc")}
                      />
                    )}

                    {showInviteForm ? (
                      <div className="mt-4 space-y-3 rounded-lg border p-4">
                        <div className="space-y-2">
                          <Label htmlFor="invite-email-company">{t("company.emailAddress")}</Label>
                          <Input
                            id="invite-email-company"
                            type="email"
                            placeholder={t("company.emailPlaceholder")}
                            value={inviteEmail}
                            onChange={(e) => setInviteEmail(e.target.value)}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="invite-role-company">{t("company.role")}</Label>
                          <select
                            id="invite-role-company"
                            value={inviteRole}
                            onChange={(e) => setInviteRole(e.target.value as "admin" | "member")}
                            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                          >
                            <option value="member">{t("company.member")}</option>
                            <option value="admin">{t("company.admin")}</option>
                          </select>
                        </div>
                        <div className="flex gap-2">
                          <Button
                            onClick={() => {
                              inviteMember.mutate(
                                { slug: companySlug, data: { email: inviteEmail, role: inviteRole } },
                                {
                                  onSuccess: () => {
                                    toast.success(t("company.invitationSent"))
                                    setShowInviteForm(false)
                                    setInviteEmail("")
                                    setInviteRole("member")
                                  },
                                  onError: (err) => {
                                    toast.error(extractApiError(err))
                                  },
                                }
                              )
                            }}
                            disabled={!inviteEmail || inviteMember.isPending}
                          >
                            <Mail className="mr-2 h-4 w-4" /> {t("company.sendInvitation")}
                          </Button>
                          <Button variant="ghost" onClick={() => setShowInviteForm(false)}>
                            {t("common.cancel")}
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <Button variant="outline" className="mt-4 w-full" onClick={() => setShowInviteForm(true)}>
                        <UserPlus className="mr-2 h-4 w-4" /> {t("company.inviteMember")}
                      </Button>
                    )}
                  </CardContent>
                </Card>
              </motion.div>

              {/* Employee Count */}
              <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.25 }}>
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2"><TrendingUp className="h-5 w-5" /> {t("company.employeeOverview")}</CardTitle>
                    <CardDescription>{t("dashboard.workforceMetrics")}</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">{t("company.totalEmployees")}</span>
                      <span className="font-medium">{memberCount}</span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">{t("company.activeUsers")}</span>
                      <span className="font-medium">{members.filter((m) => m.status === "active").length}</span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">{t("company.pendingInvitations")}</span>
                      <span className="font-medium">{pendingInvites}</span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">{t("company.licenseUtilization")}</span>
                      <span className="font-medium">{usedSeats} / {totalSeats}</span>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            </div>
          </TabsContent>

          <TabsContent value="billing" className="space-y-8">
            {/* Billing Information */}
            <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.1 }}>
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2"><CreditCard className="h-5 w-5" /> {t("company.billing")}</CardTitle>
                  <CardDescription>{t("company.billingDesc")}</CardDescription>
                </CardHeader>
                <CardContent>
                  <EmptyState
                    title={t("company.noBillingInfo")}
                    description={t("company.billingComingSoonDesc")}
                  />
                </CardContent>
              </Card>
            </motion.div>
          </TabsContent>
        </Tabs>
      </SectionWrapper>
    </>
  )
}
