import { Helmet } from "react-helmet-async"
import { motion } from "motion/react"
import { Building2, Hash, CreditCard, Users, Briefcase, Upload, Mail, UserPlus, Layers, TrendingUp } from "lucide-react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { Callout } from "@/components/ui/callout"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { useLocale } from "@/i18n/locale-context"
import { EmptyState } from "@/components/shared/empty-state"

const companyInfo = [
  { label: "Company Name", value: "TransLogistica SRL" },
  { label: "Address", value: "Str. Logistica nr. 42, Sector 1" },
  { label: "City", value: "Bucharest" },
  { label: "Country", value: "Romania" },
  { label: "Postal Code", value: "010000" },
  { label: "Phone", value: "+40 123 456 789" },
  { label: "Website", value: "www.translogistica.ro" },
]

const departments = [
  { name: "Operations", count: 8, lead: "Alex M." },
  { name: "Fleet", count: 5, lead: "Maria D." },
  { name: "Dispatch", count: 4, lead: "Ion P." },
  { name: "Finance", count: 3, lead: "Elena R." },
]

const invitations = [
  { email: "new.user@translogistica.ro", role: "Fleet Manager", status: "pending" as const, sent: "2 days ago" },
  { email: "driver1@translogistica.ro", role: "Driver", status: "accepted" as const, sent: "1 week ago" },
]

export default function CompanyPage() {
  const { t } = useLocale()
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
                        <AvatarFallback className="bg-primary/10 text-primary text-lg">TL</AvatarFallback>
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
                        <p className="text-xs text-muted-foreground">{t("company.industry")}</p>
                        <p className="text-sm font-medium">{t("company.industryValue")}</p>
                      </div>
                      <div className="space-y-1">
                        <p className="text-xs text-muted-foreground">{t("company.employeeCount")}</p>
                        <p className="text-sm font-medium">{t("company.employeeCountValue")}</p>
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
                        <Users className="h-4 w-4" /> Team Size
                      </div>
                      <span className="text-sm font-medium">20</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Layers className="h-4 w-4" /> Departments
                      </div>
                      <span className="text-sm font-medium">4</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <TrendingUp className="h-4 w-4" /> Plan
                      </div>
                      <Badge variant="success">Professional</Badge>
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Briefcase className="h-4 w-4" /> Licenses Used
                      </div>
                      <span className="text-sm font-medium">5 / 25</span>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base">{t("company.info")}</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    <Button variant="outline" className="w-full" disabled>
                      <Upload className="mr-2 h-4 w-4" /> {t("company.uploadLogo")}
                    </Button>
                    <Button variant="outline" className="w-full" disabled>
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
                  <EmptyState title={t("company.noVatInfo")} description={t("company.comingSoonDesc")} />
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
                    <EmptyState title={t("company.noTeamMembers")} description={t("company.comingSoonDesc")} />
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
                    <div className="space-y-3">
                      {departments.map((dept) => (
                        <div key={dept.name} className="flex items-center justify-between rounded-lg border p-3">
                          <div className="flex items-center gap-3">
                            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent">
                              <Briefcase className="h-4 w-4 text-primary" />
                            </div>
                            <div>
                              <p className="text-sm font-medium">{dept.name}</p>
                              <p className="text-xs text-muted-foreground">Lead: {dept.lead}</p>
                            </div>
                          </div>
                          <Badge variant="secondary">{dept.count} members</Badge>
                        </div>
                      ))}
                    </div>
                    <Callout variant="info" className="mt-4" title={t("company.comingSoon")}>
                      {t("company.comingSoonDesc")}
                    </Callout>
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
                    <div className="space-y-3">
                      {invitations.map((inv) => (
                        <div key={inv.email} className="flex items-center justify-between rounded-lg border p-3">
                          <div className="flex items-center gap-3">
                            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent">
                              <Mail className="h-4 w-4 text-primary" />
                            </div>
                            <div>
                              <p className="text-sm font-medium">{inv.email}</p>
                              <p className="text-xs text-muted-foreground">{inv.role} · Sent {inv.sent}</p>
                            </div>
                          </div>
                          <Badge variant={inv.status === "accepted" ? "success" : "secondary"}>
                            {inv.status === "accepted" ? t("company.accepted") : t("company.pending")}
                          </Badge>
                        </div>
                      ))}
                    </div>
                    <Button variant="outline" className="mt-4 w-full" disabled>
                      <UserPlus className="mr-2 h-4 w-4" /> {t("company.inviteMember")}
                    </Button>
                    <p className="mt-2 text-center text-xs text-muted-foreground">{t("company.comingSoonDesc")}</p>
                  </CardContent>
                </Card>
              </motion.div>

              {/* Employee Count */}
              <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.25 }}>
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2"><TrendingUp className="h-5 w-5" /> {t("company.employeeOverview")}</CardTitle>
                    <CardDescription>Workforce metrics and license allocation.</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Total Employees</span>
                      <span className="font-medium">20</span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Active Users</span>
                      <span className="font-medium">12</span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Pending Invitations</span>
                      <span className="font-medium">1</span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">License Utilization</span>
                      <span className="font-medium">5 / 25</span>
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
                  <EmptyState title={t("company.noBillingInfo")} description={t("company.comingSoonDesc")} />
                </CardContent>
              </Card>
            </motion.div>
          </TabsContent>
        </Tabs>
      </SectionWrapper>
    </>
  )
}
