import { useState } from "react"
import { Helmet } from "react-helmet-async"
import { Link, useParams } from "react-router"
import { motion } from "motion/react"
import {
  ArrowLeft,
  Building2,
  Users,
  CreditCard,
  AlertTriangle,
  Mail,
  UserPlus,
  Shield,
  Crown,
  User,
  Trash2,
  Clock,
  X,
} from "lucide-react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { Callout } from "@/components/ui/callout"
import { Input, Label } from "@/components/ui/input"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { useLocale } from "@/i18n/locale-context"
import type { Organization, OrganizationMember, OrganizationInvitation } from "@/types"

const mockOrganization: Organization = {
  id: "org-1",
  name: "TransLogistica SRL",
  slug: "translogistica",
  industry: "Logistics & Transportation",
  size: "11-50",
  address: "Str. Logistica nr. 42, Sector 1",
  city: "Bucharest",
  country: "Romania",
  postal_code: "010000",
  phone: "+40 123 456 789",
  website: "www.translogistica.ro",
  created_at: "2025-03-15T10:00:00Z",
  updated_at: "2026-07-01T08:30:00Z",
}

const mockMembers: Array<OrganizationMember & { name: string; email: string; avatar_initials: string }> = [
  {
    id: "mem-1",
    org_id: "org-1",
    user_id: "user-1",
    role: "owner",
    joined_at: "2025-03-15T10:00:00Z",
    status: "active",
    name: "Alexandru Marin",
    email: "alex.marin@translogistica.ro",
    avatar_initials: "AM",
  },
  {
    id: "mem-2",
    org_id: "org-1",
    user_id: "user-2",
    role: "admin",
    joined_at: "2025-04-10T09:30:00Z",
    status: "active",
    name: "Maria Dumitrescu",
    email: "maria.d@translogistica.ro",
    avatar_initials: "MD",
  },
  {
    id: "mem-3",
    org_id: "org-1",
    user_id: "user-3",
    role: "admin",
    joined_at: "2025-05-22T11:15:00Z",
    status: "active",
    name: "Ion Popescu",
    email: "ion.popescu@translogistica.ro",
    avatar_initials: "IP",
  },
  {
    id: "mem-4",
    org_id: "org-1",
    user_id: "user-4",
    role: "member",
    joined_at: "2025-08-05T08:00:00Z",
    status: "active",
    name: "Elena Radu",
    email: "elena.radu@translogistica.ro",
    avatar_initials: "ER",
  },
  {
    id: "mem-5",
    org_id: "org-1",
    user_id: "user-5",
    role: "member",
    joined_at: "2026-01-12T14:20:00Z",
    status: "active",
    name: "Andrei Stancu",
    email: "andrei.s@translogistica.ro",
    avatar_initials: "AS",
  },
]

const mockInvitations: Array<OrganizationInvitation & { invited_by_name: string }> = [
  {
    id: "inv-1",
    org_id: "org-1",
    email: "new.dispatcher@translogistica.ro",
    role: "member",
    invited_by: "user-1",
    created_at: "2026-07-08T10:00:00Z",
    expires_at: "2026-07-15T10:00:00Z",
    status: "pending",
    invited_by_name: "Alexandru Marin",
  },
]

const industries = [
  "Logistics & Transportation",
  "Courier & Delivery",
  "Freight & Shipping",
  "Warehouse & Distribution",
  "Public Transit",
  "Field Services",
  "Other",
]

const sizes = ["1-10", "11-50", "51-200", "201-500", "501+"] as const

function roleIcon(role: string) {
  if (role === "owner") return Crown
  if (role === "admin") return Shield
  return User
}

function roleBadgeVariant(role: string): "default" | "secondary" | "outline" | "success" | "destructive" {
  if (role === "owner") return "default"
  if (role === "admin") return "secondary"
  return "outline"
}

export default function OrganizationSettingsPage() {
  const { slug } = useParams<{ slug: string }>()
  const [org] = useState(mockOrganization)
  const [members] = useState(mockMembers)
  const [invitations] = useState(mockInvitations)
  const [inviteEmail, setInviteEmail] = useState("")
  const [inviteRole, setInviteRole] = useState<"admin" | "member">("member")
  const { t } = useLocale()

  // In a real app, we'd fetch by slug. For demo, use mock data.
  const currentOrg = slug === org.slug ? org : null

  if (!currentOrg) {
    return (
      <SectionWrapper>
        <Callout variant="warning" title={t("orgSettings.notFoundTitle")}>
          {t("orgSettings.notFoundDesc")}
        </Callout>
        <Button variant="outline" className="mt-4" asChild>
          <Link to="/dashboard/organizations">
            <ArrowLeft className="mr-2 h-4 w-4" />
            {t("orgSettings.backToOrganizations")}
          </Link>
        </Button>
      </SectionWrapper>
    )
  }

  return (
    <>
      <Helmet>
        <title>{currentOrg.name} {t("orgSettings.pageTitleSuffix")}</title>
      </Helmet>
      <SectionWrapper>
        {/* Back Link + Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
        >
          <Button variant="ghost" size="sm" className="mb-4 -ml-2" asChild>
            <Link to="/dashboard/organizations">
              <ArrowLeft className="mr-1.5 h-4 w-4" />
              {t("orgSettings.backToOrganizations")}
            </Link>
          </Button>
          <div className="flex items-center gap-3">
            <Avatar size="lg">
              <AvatarFallback className="bg-primary/10 text-primary text-lg">
                {currentOrg.name
                  .split(" ")
                  .map((w) => w[0])
                  .join("")
                  .slice(0, 2)
                  .toUpperCase()}
              </AvatarFallback>
            </Avatar>
            <div>
              <h1 className="text-3xl font-bold tracking-tight">{currentOrg.name}</h1>
              <p className="mt-1 text-muted-foreground">
                {t("orgSettings.pageDescription")}
              </p>
            </div>
          </div>
        </motion.div>

        <Tabs defaultValue="general" className="mt-8">
          <TabsList className="mb-6">
            <TabsTrigger value="general">{t("orgSettings.tabs.general")}</TabsTrigger>
            <TabsTrigger value="members">{t("orgSettings.tabs.members")}</TabsTrigger>
            <TabsTrigger value="billing">{t("orgSettings.tabs.billing")}</TabsTrigger>
            <TabsTrigger value="danger">{t("orgSettings.tabs.dangerZone")}</TabsTrigger>
          </TabsList>

          {/* ─── General Tab ─── */}
          <TabsContent value="general" className="space-y-8">
            <div className="grid gap-6 lg:grid-cols-3">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.1 }}
                className="lg:col-span-2"
              >
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Building2 className="h-5 w-5" />
                      {t("orgSettings.general.title")}
                    </CardTitle>
                    <CardDescription>
                      {t("orgSettings.general.description")}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    {/* Logo placeholder */}
                    <div className="flex items-center gap-4">
                      <Avatar size="lg">
                        <AvatarFallback className="bg-primary/10 text-primary text-lg">
                          {currentOrg.name
                            .split(" ")
                            .map((w) => w[0])
                            .join("")
                            .slice(0, 2)
                            .toUpperCase()}
                        </AvatarFallback>
                      </Avatar>
                      <div>
                        <p className="text-sm font-medium">{t("orgSettings.general.logoLabel")}</p>
                        <p className="text-xs text-muted-foreground">
                          {t("orgSettings.general.logoDescription")}
                        </p>
                      </div>
                    </div>

                    <div className="grid gap-4 sm:grid-cols-2">
                      <div className="space-y-2">
                        <Label htmlFor="org-name">{t("orgSettings.general.nameLabel")}</Label>
                        <Input
                          id="org-name"
                          defaultValue={currentOrg.name}
                          disabled
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="org-slug">{t("orgSettings.general.slugLabel")}</Label>
                        <Input id="org-slug" defaultValue={currentOrg.slug} disabled />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="org-industry">{t("orgSettings.general.industryLabel")}</Label>
                        <select
                          id="org-industry"
                          defaultValue={currentOrg.industry}
                          disabled
                          className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          {industries.map((ind) => (
                            <option key={ind} value={ind}>
                              {ind}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="org-size">{t("orgSettings.general.sizeLabel")}</Label>
                        <select
                          id="org-size"
                          defaultValue={currentOrg.size}
                          disabled
                          className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          {sizes.map((s) => (
                            <option key={s} value={s}>
                              {s} {t("orgSettings.general.employeesSuffix")}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="space-y-2 sm:col-span-2">
                        <Label htmlFor="org-address">{t("orgSettings.general.addressLabel")}</Label>
                        <Input
                          id="org-address"
                          defaultValue={currentOrg.address}
                          disabled
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="org-city">{t("orgSettings.general.cityLabel")}</Label>
                        <Input id="org-city" defaultValue={currentOrg.city} disabled />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="org-country">{t("orgSettings.general.countryLabel")}</Label>
                        <Input
                          id="org-country"
                          defaultValue={currentOrg.country}
                          disabled
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="org-postal">{t("orgSettings.general.postalCodeLabel")}</Label>
                        <Input
                          id="org-postal"
                          defaultValue={currentOrg.postal_code}
                          disabled
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="org-phone">{t("orgSettings.general.phoneLabel")}</Label>
                        <Input id="org-phone" defaultValue={currentOrg.phone} disabled />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="org-website">{t("orgSettings.general.websiteLabel")}</Label>
                        <Input
                          id="org-website"
                          defaultValue={currentOrg.website}
                          disabled
                        />
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      <Button disabled>{t("orgSettings.general.saveButton")}</Button>
                      <p className="text-xs text-muted-foreground">
                        {t("orgSettings.general.comingSoon")}
                      </p>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.15 }}
                className="space-y-6"
              >
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base">{t("orgSettings.details.title")}</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">{t("orgSettings.details.created")}</span>
                      <span className="font-medium">
                        {new Date(currentOrg.created_at ?? "").toLocaleDateString()}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">{t("orgSettings.details.lastUpdated")}</span>
                      <span className="font-medium">
                        {new Date(currentOrg.updated_at ?? "").toLocaleDateString()}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">{t("orgSettings.details.id")}</span>
                      <span className="font-medium font-mono text-xs">
                        {currentOrg.id}
                      </span>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            </div>
          </TabsContent>

          {/* ─── Members Tab ─── */}
          <TabsContent value="members" className="space-y-8">
            <div className="grid gap-6 lg:grid-cols-3">
              {/* Member List */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.1 }}
                className="lg:col-span-2"
              >
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Users className="h-5 w-5" />
                      {t("orgSettings.members.title")}
                    </CardTitle>
                    <CardDescription>
                      {t("orgSettings.members.description")}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {members.map((member, i) => {
                        const RoleIcon = roleIcon(member.role)
                        return (
                          <motion.div
                            key={member.id}
                            initial={{ opacity: 0, x: -10 }}
                            whileInView={{ opacity: 1, x: 0 }}
                            viewport={{ once: true }}
                            transition={{ delay: 0.05 + i * 0.03 }}
                            className="flex items-center justify-between rounded-lg border p-3"
                          >
                            <div className="flex items-center gap-3">
                              <Avatar size="sm">
                                <AvatarFallback className="bg-primary/10 text-primary text-xs">
                                  {member.avatar_initials}
                                </AvatarFallback>
                              </Avatar>
                              <div>
                                <p className="text-sm font-medium">{member.name}</p>
                                <p className="text-xs text-muted-foreground">
                                  {member.email}
                                </p>
                              </div>
                            </div>
                            <div className="flex items-center gap-3">
                              <div className="hidden sm:flex items-center gap-1.5 text-xs text-muted-foreground">
                                <Clock className="h-3 w-3" />
                                {t("orgSettings.members.joined")} {new Date(member.joined_at).toLocaleDateString()}
                              </div>
                              <Badge variant={roleBadgeVariant(member.role)} className="text-xs">
                                <RoleIcon className="mr-1 h-3 w-3" />
                                {t(`orgSettings.roles.${member.role}`)}
                              </Badge>
                              <Button
                                variant="ghost"
                                size="sm"
                                disabled
                                className="text-destructive hover:text-destructive"
                              >
                                <X className="h-4 w-4" />
                              </Button>
                            </div>
                          </motion.div>
                        )
                      })}
                    </div>
                  </CardContent>
                </Card>
              </motion.div>

              {/* Invite Member */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.15 }}
              >
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-base">
                      <UserPlus className="h-5 w-5" />
                      {t("orgSettings.invite.title")}
                    </CardTitle>
                    <CardDescription>
                      {t("orgSettings.invite.description")}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="invite-email">{t("orgSettings.invite.emailLabel")}</Label>
                      <Input
                        id="invite-email"
                        type="email"
                        placeholder={t("orgSettings.invite.emailPlaceholder")}
                        value={inviteEmail}
                        onChange={(e) => setInviteEmail(e.target.value)}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="invite-role">{t("orgSettings.invite.roleLabel")}</Label>
                      <select
                        id="invite-role"
                        value={inviteRole}
                        onChange={(e) => setInviteRole(e.target.value as "admin" | "member")}
                        className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                      >
                        <option value="member">{t("orgSettings.invite.roleMember")}</option>
                        <option value="admin">{t("orgSettings.invite.roleAdmin")}</option>
                      </select>
                    </div>
                    <Button className="w-full" disabled>
                      <Mail className="mr-2 h-4 w-4" />
                      {t("orgSettings.invite.sendButton")}
                    </Button>
                    <p className="text-xs text-muted-foreground text-center">
                      {t("orgSettings.invite.comingSoon")}
                    </p>
                  </CardContent>
                </Card>
              </motion.div>
            </div>

            {/* Pending Invitations */}
            {invitations.length > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.2 }}
              >
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-base">
                      <Mail className="h-5 w-5" />
                      {t("orgSettings.pendingInvitations.title")}
                    </CardTitle>
                    <CardDescription>
                      {t("orgSettings.pendingInvitations.description")}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {invitations.map((inv) => (
                        <div
                          key={inv.id}
                          className="flex items-center justify-between rounded-lg border p-3"
                        >
                          <div className="flex items-center gap-3">
                            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent">
                              <Mail className="h-4 w-4 text-primary" />
                            </div>
                            <div>
                              <p className="text-sm font-medium">{inv.email}</p>
                              <p className="text-xs text-muted-foreground">
                                {t(`orgSettings.roles.${inv.role}`)} · {t("orgSettings.pendingInvitations.invitedBy")} {inv.invited_by_name} ·{" "}
                                {new Date(inv.created_at).toLocaleDateString()}
                              </p>
                            </div>
                          </div>
                          <Badge variant="secondary">
                            <Clock className="mr-1 h-3 w-3" />
                            {t("orgSettings.pendingInvitations.pending")}
                          </Badge>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            )}
          </TabsContent>

          {/* ─── Billing Tab ─── */}
          <TabsContent value="billing" className="space-y-8">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.1 }}
            >
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <CreditCard className="h-5 w-5" />
                    {t("orgSettings.billing.title")}
                  </CardTitle>
                  <CardDescription>
                    {t("orgSettings.billing.description")}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Callout variant="info" title={t("orgSettings.billing.comingSoonTitle")}>
                    {t("orgSettings.billing.comingSoonText")}
                  </Callout>
                  <div className="mt-6 flex items-center justify-between rounded-lg border p-4">
                    <div>
                      <p className="text-sm font-medium">{t("orgSettings.billing.currentPlan")}</p>
                      <p className="text-xs text-muted-foreground">
                        {t("orgSettings.billing.planDescription")}
                      </p>
                    </div>
                    <Badge variant="success">{t("orgSettings.billing.active")}</Badge>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          </TabsContent>

          {/* ─── Danger Zone ─── */}
          <TabsContent value="danger" className="space-y-8">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.1 }}
            >
              <Card className="border-destructive/20">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-destructive">
                    <AlertTriangle className="h-5 w-5" />
                    {t("orgSettings.danger.title")}
                  </CardTitle>
                  <CardDescription>
                    {t("orgSettings.danger.description")}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  <Callout variant="danger" title={t("orgSettings.danger.warningTitle")}>
                    {t("orgSettings.danger.warningText")}
                  </Callout>

                  <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 rounded-lg border p-4">
                    <div>
                      <p className="text-sm font-medium">{t("orgSettings.danger.deleteTitle")}</p>
                      <p className="text-xs text-muted-foreground">
                        {t("orgSettings.danger.deleteDescription")} {currentOrg.name} {t("orgSettings.danger.deleteDescriptionSuffix")}
                      </p>
                    </div>
                    <Button variant="destructive" disabled>
                      <Trash2 className="mr-2 h-4 w-4" />
                      {t("orgSettings.danger.deleteButton")}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          </TabsContent>
        </Tabs>
      </SectionWrapper>
    </>
  )
}
