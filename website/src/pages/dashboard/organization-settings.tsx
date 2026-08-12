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
  RefreshCw,
} from "lucide-react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { Callout } from "@/components/ui/callout"
import { Input, Label } from "@/components/ui/input"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { toast } from "sonner"
import { extractApiError } from "@/api/client"
import { useOrganization, useOrganizationMembers, useOrganizationInvitations, useUpdateOrganization, useInviteMember, useRemoveMember } from "@/services/queries"
import { useLocale } from "@/i18n/locale-context"

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

function getInitials(name?: string) {
  if (!name) return "??"
  return name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase()
}

export default function OrganizationSettingsPage() {
  const { t } = useLocale()
  const { slug } = useParams<{ slug: string }>()
  const { data: currentOrg, isLoading: orgLoading, isError: orgError, error: orgErrorObj, refetch: orgRefetch } = useOrganization(slug ?? "")
  const { data: members, isLoading: membersLoading } = useOrganizationMembers(slug ?? "")
  const { data: invitations } = useOrganizationInvitations(slug ?? "")
  const [inviteEmail, setInviteEmail] = useState("")
  const [inviteRole, setInviteRole] = useState<"admin" | "member">("member")

  const updateOrganization = useUpdateOrganization()
  const inviteMember = useInviteMember()
  const removeMember = useRemoveMember()
  const [isEditing, setIsEditing] = useState(false)
  const [editName, setEditName] = useState("")
  const [editIndustry, setEditIndustry] = useState("")
  const [editSize, setEditSize] = useState("")
  const [editAddress, setEditAddress] = useState("")
  const [editCity, setEditCity] = useState("")
  const [editCountry, setEditCountry] = useState("")
  const [editPostalCode, setEditPostalCode] = useState("")
  const [editPhone, setEditPhone] = useState("")
  const [editWebsite, setEditWebsite] = useState("")
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  if (orgLoading) {
    return (
      <SectionWrapper>
        <Skeleton className="h-5 w-32 mb-4" />
        <div className="flex items-center gap-3">
          <Skeleton className="h-12 w-12 rounded-full" />
          <div className="space-y-2">
            <Skeleton className="h-7 w-56" />
            <Skeleton className="h-4 w-72" />
          </div>
        </div>
        <div className="mt-8">
          <Skeleton className="h-10 w-96" />
          <div className="mt-6 grid gap-6 lg:grid-cols-3">
            <div className="lg:col-span-2">
              <Skeleton className="h-64 w-full rounded-lg" />
            </div>
            <Skeleton className="h-48 w-full rounded-lg" />
          </div>
        </div>
      </SectionWrapper>
    )
  }

  if (orgError) {
    return (
      <SectionWrapper>
        <Callout variant="danger" title={t("organizationSettings.failedToLoad")}>
          {orgErrorObj instanceof Error ? orgErrorObj.message : t("organizationSettings.unexpectedError")}
        </Callout>
        <div className="mt-4 flex gap-3">
          <Button variant="outline" onClick={() => orgRefetch()}>
            <RefreshCw className="mr-2 h-4 w-4" />
            {t("common.retry")}
          </Button>
          <Button variant="outline" asChild>
            <Link to="/dashboard/organizations">
              <ArrowLeft className="mr-2 h-4 w-4" />
              {t("organizationSettings.backToOrganizations")}
            </Link>
          </Button>
        </div>
      </SectionWrapper>
    )
  }

  if (!currentOrg) {
    return (
      <SectionWrapper>
        <Callout variant="warning" title={t("organizationSettings.notFound")}>
          {t("organizationSettings.notFoundDesc")}
        </Callout>
        <Button variant="outline" className="mt-4" asChild>
          <Link to="/dashboard/organizations">
            <ArrowLeft className="mr-2 h-4 w-4" />
            {t("organizationSettings.backToOrganizations")}
          </Link>
        </Button>
      </SectionWrapper>
    )
  }

  return (
    <>
      <Helmet>
        <title>{currentOrg.name} Settings — Operion ERP</title>
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
              {t("organizationSettings.backToOrganizations")}
            </Link>
          </Button>
          <div className="flex items-center gap-3">
            <Avatar size="lg">
              <AvatarFallback className="bg-primary/10 text-primary text-lg">
                {getInitials(currentOrg.name)}
              </AvatarFallback>
            </Avatar>
            <div>
              <h1 className="text-3xl font-bold tracking-tight">{currentOrg.name}</h1>
              <p className="mt-1 text-muted-foreground">
                {t("organizationSettings.description")}
              </p>
            </div>
          </div>
        </motion.div>

        <Tabs defaultValue="general" className="mt-8">
          <TabsList className="mb-6">
            <TabsTrigger value="general">{t("organizationSettings.general")}</TabsTrigger>
            <TabsTrigger value="members">{t("organizationSettings.members")}</TabsTrigger>
            <TabsTrigger value="billing">{t("organizationSettings.billing")}</TabsTrigger>
            <TabsTrigger value="danger">{t("organizationSettings.dangerZone")}</TabsTrigger>
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
                      {t("organizationSettings.generalInfo")}
                    </CardTitle>
                    <CardDescription>
                      {t("organizationSettings.generalInfoDesc")}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    {/* Logo placeholder */}
                    <div className="flex items-center gap-4">
                      <Avatar size="lg">
                        <AvatarFallback className="bg-primary/10 text-primary text-lg">
                          {getInitials(currentOrg.name)}
                        </AvatarFallback>
                      </Avatar>
                      <div>
                        <p className="text-sm font-medium">{t("organizationSettings.logo")}</p>
                        <p className="text-xs text-muted-foreground">
                          {t("organizationSettings.logoDesc")}
                        </p>
                      </div>
                    </div>

                    <div className="grid gap-4 sm:grid-cols-2">
                      <div className="space-y-2">
                        <Label htmlFor="org-name">{t("organizationSettings.name")}</Label>
                        <Input
                          id="org-name"
                          value={isEditing ? editName : currentOrg.name}
                          onChange={(e) => setEditName(e.target.value)}
                          disabled={!isEditing}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="org-slug">{t("organizationSettings.slug")}</Label>
                        <Input id="org-slug" value={currentOrg.slug} disabled />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="org-industry">{t("organizationSettings.industry")}</Label>
                        <select
                          id="org-industry"
                          value={isEditing ? editIndustry : currentOrg.industry}
                          onChange={(e) => setEditIndustry(e.target.value)}
                          disabled={!isEditing}
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
                        <Label htmlFor="org-size">{t("organizationSettings.size")}</Label>
                        <select
                          id="org-size"
                          value={isEditing ? editSize : currentOrg.size}
                          onChange={(e) => setEditSize(e.target.value)}
                          disabled={!isEditing}
                          className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          {sizes.map((s) => (
                            <option key={s} value={s}>
                              {t("organizationSettings.sizeEmployees").replace("{size}", s)}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="space-y-2 sm:col-span-2">
                        <Label htmlFor="org-address">{t("organizationSettings.address")}</Label>
                        <Input
                          id="org-address"
                          value={isEditing ? editAddress : currentOrg.address}
                          onChange={(e) => setEditAddress(e.target.value)}
                          disabled={!isEditing}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="org-city">{t("organizationSettings.city")}</Label>
                        <Input
                          id="org-city"
                          value={isEditing ? editCity : currentOrg.city}
                          onChange={(e) => setEditCity(e.target.value)}
                          disabled={!isEditing}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="org-country">{t("organizationSettings.country")}</Label>
                        <Input
                          id="org-country"
                          value={isEditing ? editCountry : currentOrg.country}
                          onChange={(e) => setEditCountry(e.target.value)}
                          disabled={!isEditing}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="org-postal">{t("organizationSettings.postalCode")}</Label>
                        <Input
                          id="org-postal"
                          value={isEditing ? editPostalCode : currentOrg.postal_code}
                          onChange={(e) => setEditPostalCode(e.target.value)}
                          disabled={!isEditing}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="org-phone">{t("organizationSettings.phone")}</Label>
                        <Input
                          id="org-phone"
                          value={isEditing ? editPhone : currentOrg.phone}
                          onChange={(e) => setEditPhone(e.target.value)}
                          disabled={!isEditing}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="org-website">{t("organizationSettings.website")}</Label>
                        <Input
                          id="org-website"
                          value={isEditing ? editWebsite : currentOrg.website}
                          onChange={(e) => setEditWebsite(e.target.value)}
                          disabled={!isEditing}
                        />
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      {isEditing ? (
                        <>
                          <Button
                            onClick={() => {
                              updateOrganization.mutate(
                                {
                                  slug: slug ?? "",
                                  data: {
                                    name: editName || undefined,
                                    website: editWebsite || undefined,
                                  },
                                },
                                {
                                  onSuccess: () => {
                                    toast.success(t("organizationSettings.updatedSuccess"))
                                    setIsEditing(false)
                                  },
                                  onError: (err) => {
                                    toast.error(extractApiError(err))
                                  },
                                }
                              )
                            }}
                            disabled={updateOrganization.isPending}
                          >
                            {t("organizationSettings.saveChanges")}
                          </Button>
                          <Button variant="ghost" onClick={() => setIsEditing(false)}>
                            {t("common.cancel")}
                          </Button>
                        </>
                      ) : (
                        <Button
                          onClick={() => {
                            setEditName(currentOrg.name ?? "")
                            setEditIndustry(currentOrg.industry ?? "")
                            setEditSize(currentOrg.size ?? "")
                            setEditAddress(currentOrg.address ?? "")
                            setEditCity(currentOrg.city ?? "")
                            setEditCountry(currentOrg.country ?? "")
                            setEditPostalCode(currentOrg.postal_code ?? "")
                            setEditPhone(currentOrg.phone ?? "")
                            setEditWebsite(currentOrg.website ?? "")
                            setIsEditing(true)
                          }}
                        >
                          {t("organizationSettings.editOrganization")}
                        </Button>
                      )}
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
                    <CardTitle className="text-base">{t("organizationSettings.details")}</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">{t("organizationSettings.created")}</span>
                      <span className="font-medium">
                        {new Date(currentOrg.created_at ?? "").toLocaleDateString()}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">{t("organizationSettings.lastUpdated")}</span>
                      <span className="font-medium">
                        {new Date(currentOrg.updated_at ?? "").toLocaleDateString()}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">{t("organizationSettings.id")}</span>
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
                      {t("organizationSettings.members")}
                    </CardTitle>
                    <CardDescription>
                      {t("organizationSettings.membersDesc")}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {membersLoading ? (
                      <div className="space-y-3">
                        {Array.from({ length: 3 }).map((_, i) => (
                          <div key={i} className="flex items-center justify-between rounded-lg border p-3">
                            <div className="flex items-center gap-3">
                              <Skeleton className="h-8 w-8 rounded-full" />
                              <div className="space-y-1">
                                <Skeleton className="h-4 w-32" />
                                <Skeleton className="h-3 w-48" />
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (members ?? []).length === 0 ? (
                      <p className="text-sm text-muted-foreground py-4 text-center">
                        {t("organizationSettings.noMembers")}
                      </p>
                    ) : (
                      <div className="space-y-3">
                        {(members ?? []).map((member, i) => {
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
                                    {getInitials(member.name)}
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
                                  {t("organizationSettings.joined")}{" "}
                                  {member.joined_at
                                    ? new Date(member.joined_at).toLocaleDateString()
                                    : "—"}
                                </div>
                                <Badge variant={roleBadgeVariant(member.role)} className="text-xs">
                                  <RoleIcon className="mr-1 h-3 w-3" />
                                  {member.role
                                    ? member.role.charAt(0).toUpperCase() + member.role.slice(1)
                                    : t("organizationSettings.member")}
                                </Badge>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => {
                                    if (window.confirm(t("organizationSettings.removeMember").replace("{name}", member.name || member.email || ""))) {
                                      removeMember.mutate(
                                        { slug: slug ?? "", memberId: String(member.id) },
                                        {
                                          onSuccess: () => toast.success(t("organizationSettings.memberRemoved")),
                                          onError: (err) => toast.error(extractApiError(err)),
                                        }
                                      )
                                    }
                                  }}
                                  disabled={removeMember.isPending}
                                  className="text-destructive hover:text-destructive"
                                >
                                  <X className="h-4 w-4" />
                                </Button>
                              </div>
                            </motion.div>
                          )
                        })}
                      </div>
                    )}
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
                      {t("organizationSettings.inviteMember")}
                    </CardTitle>
                    <CardDescription>
                      {t("organizationSettings.inviteMemberDesc")}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="invite-email">{t("organizationSettings.emailAddress")}</Label>
                      <Input
                        id="invite-email"
                        type="email"
                        placeholder={t("organizationSettings.emailPlaceholder")}
                        value={inviteEmail}
                        onChange={(e) => setInviteEmail(e.target.value)}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="invite-role">{t("organizationSettings.role")}</Label>
                      <select
                        id="invite-role"
                        value={inviteRole}
                        onChange={(e) => setInviteRole(e.target.value as "admin" | "member")}
                        className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                      >
                        <option value="member">{t("organizationSettings.member")}</option>
                        <option value="admin">{t("company.admin")}</option>
                      </select>
                    </div>
                    <Button
                      className="w-full"
                      onClick={() => {
                        inviteMember.mutate(
                          { slug: slug ?? "", data: { email: inviteEmail, role: inviteRole } },
                          {
                            onSuccess: () => {
                              toast.success(t("organizationSettings.invitationSent"))
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
                      <Mail className="mr-2 h-4 w-4" />
                      {t("organizationSettings.sendInvitation")}
                    </Button>
                  </CardContent>
                </Card>
              </motion.div>
            </div>

            {/* Pending Invitations */}
            {(invitations ?? []).length > 0 && (
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
                      {t("organizationSettings.pendingInvitations")}
                    </CardTitle>
                    <CardDescription>
                      {t("organizationSettings.pendingInvitationsDesc")}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {(invitations ?? []).map((inv) => (
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
                                {inv.role} · {t("organizationSettings.invitedBy").replace("{name}", inv.invited_by_name ?? "")} ·{" "}
                                {inv.created_at
                                  ? new Date(inv.created_at).toLocaleDateString()
                                  : "—"}
                              </p>
                            </div>
                          </div>
                          <Badge variant="secondary">
                            <Clock className="mr-1 h-3 w-3" />
                            {t("organizationSettings.pending")}
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
                    {t("organizationSettings.billing")}
                  </CardTitle>
                  <CardDescription>
                    {t("organizationSettings.billingDesc")}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center justify-between rounded-lg border p-4">
                    <div>
                      <p className="text-sm font-medium">{t("organizationSettings.currentPlan")}</p>
                      <p className="text-xs text-muted-foreground">
                        {t("organizationSettings.planSuffix").replace("{plan}", currentOrg.subscription_tier ?? "Free")}
                      </p>
                    </div>
                    <Badge variant="success">{t("organizationSettings.active")}</Badge>
                  </div>
                  <p className="text-xs text-muted-foreground mt-4">
                    {t("organizationSettings.billingUnderDevelopment")}
                  </p>
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
                    {t("organizationSettings.dangerZone")}
                  </CardTitle>
                  <CardDescription>
                    {t("organizationSettings.dangerZoneDesc")}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  <Callout variant="danger" title={t("organizationSettings.warning")}>
                    {t("organizationSettings.deleteWarningDesc")}
                  </Callout>

                  <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 rounded-lg border p-4">
                    <div>
                      <p className="text-sm font-medium">{t("organizationSettings.deleteOrganization")}</p>
                      <p className="text-xs text-muted-foreground">
                        {t("organizationSettings.deleteOrganizationDesc").replace("{name}", currentOrg.name ?? "")}
                      </p>
                    </div>
                    {showDeleteConfirm ? (
                      <div className="w-full sm:w-auto space-y-3 rounded-lg border border-destructive/30 bg-destructive/5 p-4">
                        <p className="text-sm font-medium text-destructive">
                          {t("organizationSettings.areYouAbsolutelySure")}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {t("organizationSettings.deletePlaceholderNote")}
                        </p>
                        <div className="flex gap-2">
                          <Button variant="destructive" disabled>
                            <Trash2 className="mr-2 h-4 w-4" />
                            {t("organizationSettings.confirmDelete")}
                          </Button>
                          <Button variant="ghost" onClick={() => setShowDeleteConfirm(false)}>
                            {t("common.cancel")}
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <Button
                        variant="destructive"
                        onClick={() => setShowDeleteConfirm(true)}
                      >
                        <Trash2 className="mr-2 h-4 w-4" />
                        {t("organizationSettings.deleteOrganization")}
                      </Button>
                    )}
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
