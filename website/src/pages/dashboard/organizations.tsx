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
} from "lucide-react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import type { Organization } from "@/types"

const mockOrganizations: Array<Organization & { member_count: number; plan: string; user_role: "owner" | "admin" | "member" }> = [
  {
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
    member_count: 20,
    plan: "Professional",
    user_role: "owner",
  },
  {
    id: "org-2",
    name: "FastRoute GmbH",
    slug: "fastroute",
    industry: "Courier & Delivery",
    size: "51-200",
    address: "Hauptstrasse 88",
    city: "Berlin",
    country: "Germany",
    postal_code: "10115",
    phone: "+49 30 1234567",
    website: "www.fastroute.de",
    created_at: "2025-06-20T14:00:00Z",
    updated_at: "2026-06-28T09:15:00Z",
    member_count: 64,
    plan: "Enterprise",
    user_role: "admin",
  },
  {
    id: "org-3",
    name: "GreenFleet Logistics",
    slug: "greenfleet",
    industry: "Sustainable Transport",
    size: "1-10",
    address: "Eco Park, Building C",
    city: "Cluj-Napoca",
    country: "Romania",
    postal_code: "400000",
    phone: "+40 234 567 890",
    website: "www.greenfleet.ro",
    created_at: "2026-01-10T11:00:00Z",
    updated_at: "2026-07-05T16:45:00Z",
    member_count: 7,
    plan: "Starter",
    user_role: "member",
  },
]

const activeOrgId = "org-1"

function getInitials(name: string) {
  return name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase()
}

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

export default function OrganizationsPage() {
  const [orgs] = useState(mockOrganizations)
  const activeOrg = orgs.find((o) => o.id === activeOrgId)

  return (
    <>
      <Helmet>
        <title>Organizations — Operion ERP</title>
      </Helmet>
      <SectionWrapper>
        {/* Page Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
        >
          <h1 className="text-3xl font-bold tracking-tight">Organizations</h1>
          <p className="mt-2 text-muted-foreground">
            Manage your organizations and team members
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
          <h2 className="text-lg font-semibold tracking-tight">Organization Selector</h2>
          <p className="text-sm text-muted-foreground">
            Your currently active organization is highlighted below.
          </p>

          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {orgs.map((org, i) => {
              const isActive = org.id === activeOrgId
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
                                Current
                              </Badge>
                            )}
                          </div>
                          <p className="text-xs text-muted-foreground mt-0.5">
                            {org.industry}
                          </p>
                          <div className="mt-3 flex flex-wrap items-center gap-2">
                            <Badge variant="secondary" className="text-xs">
                              <Users className="mr-1 h-3 w-3" />
                              {org.member_count} members
                            </Badge>
                            <Badge
                              variant={
                                org.plan === "Enterprise"
                                  ? "default"
                                  : org.plan === "Professional"
                                    ? "success"
                                    : "secondary"
                              }
                              className="text-xs"
                            >
                              {org.plan}
                            </Badge>
                            <Badge variant={roleBadgeVariant(org.user_role)} className="text-xs">
                              <RoleIcon className="mr-1 h-3 w-3" />
                              {org.user_role.charAt(0).toUpperCase() + org.user_role.slice(1)}
                            </Badge>
                          </div>
                        </div>
                      </div>

                      <div className="mt-4 flex items-center gap-2">
                        {!isActive && (
                          <Button variant="outline" size="sm" className="flex-1">
                            <ArrowRightLeft className="mr-1.5 h-3.5 w-3.5" />
                            Switch to this org
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
                            Manage
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
            <h2 className="text-lg font-semibold tracking-tight">Current Organization</h2>
            <div className="mt-4 grid gap-6 lg:grid-cols-3">
              <Card className="lg:col-span-2">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Building2 className="h-5 w-5" />
                    {activeOrg.name}
                  </CardTitle>
                  <CardDescription>
                    Overview of your active organization.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-1">
                      <p className="text-xs text-muted-foreground">Industry</p>
                      <p className="text-sm font-medium">{activeOrg.industry}</p>
                    </div>
                    <div className="space-y-1">
                      <p className="text-xs text-muted-foreground">Size</p>
                      <p className="text-sm font-medium">{activeOrg.size} employees</p>
                    </div>
                    <div className="space-y-1">
                      <p className="text-xs text-muted-foreground">Address</p>
                      <p className="text-sm font-medium">{activeOrg.address}</p>
                    </div>
                    <div className="space-y-1">
                      <p className="text-xs text-muted-foreground">City</p>
                      <p className="text-sm font-medium">
                        {activeOrg.city}, {activeOrg.country}
                      </p>
                    </div>
                    <div className="space-y-1">
                      <p className="text-xs text-muted-foreground">Phone</p>
                      <p className="text-sm font-medium">{activeOrg.phone}</p>
                    </div>
                    <div className="space-y-1">
                      <p className="text-xs text-muted-foreground">Website</p>
                      <p className="text-sm font-medium">{activeOrg.website}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Quick Stats</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Members</span>
                    <span className="text-sm font-medium">{activeOrg.member_count}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Plan</span>
                    <Badge
                      variant={
                        activeOrg.plan === "Enterprise"
                          ? "default"
                          : activeOrg.plan === "Professional"
                            ? "success"
                            : "secondary"
                      }
                    >
                      {activeOrg.plan}
                    </Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Your Role</span>
                    <Badge variant={roleBadgeVariant(activeOrg.user_role)}>
                      {activeOrg.user_role.charAt(0).toUpperCase() +
                        activeOrg.user_role.slice(1)}
                    </Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Created</span>
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
          <h2 className="text-lg font-semibold tracking-tight">Create Organization</h2>
          <p className="text-sm text-muted-foreground">
            Add a new organization to your account.
          </p>

          <Card className="mt-4">
            <CardContent className="p-6">
              <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                  <Plus className="h-6 w-6 text-primary" />
                </div>
                <div className="flex-1">
                  <p className="font-semibold text-sm">Start a new organization</p>
                  <p className="text-sm text-muted-foreground mt-0.5">
                    Multi-organization support lets you manage separate teams, billing, and
                    settings under one account. Perfect for agencies, franchises, or
                    subsidiaries.
                  </p>
                </div>
                <Button disabled className="shrink-0">
                  <Plus className="mr-2 h-4 w-4" />
                  Create Organization
                </Button>
              </div>
              <p className="mt-3 text-xs text-muted-foreground text-center sm:text-left">
                Organization creation is coming soon.
              </p>
            </CardContent>
          </Card>
        </motion.div>
      </SectionWrapper>
    </>
  )
}
