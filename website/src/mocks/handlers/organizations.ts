import { http, HttpResponse } from "msw"
import type { Organization, OrganizationMember, OrganizationInvitation } from "@/types"

const mockOrganizations: Organization[] = [
  {
    id: 1,
    name: "Test Company",
    company_name: "Test Company",
    subscription_tier: "professional",
    is_active: true,
    slug: "test-company",
    industry: "Logistics",
    address: "123 Main Street",
    city: "New York",
    country: "US",
    postal_code: "10001",
    phone: "+1-555-0100",
    website: "https://testcompany.example.com",
    size: "51-200",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-07-01T12:00:00Z",
    member_count: 5,
    user_role: "owner",
  },
]

const mockMembers: OrganizationMember[] = [
  {
    id: 1,
    org_id: 1,
    user_id: "user-1",
    role: "owner",
    status: "active",
    name: "Test User",
    email: "test@operion.dev",
    joined_at: "2026-01-01T00:00:00Z",
  },
  {
    id: 2,
    org_id: 1,
    user_id: "user-2",
    role: "admin",
    status: "active",
    name: "Alice Admin",
    email: "alice@operion.dev",
    joined_at: "2026-02-01T00:00:00Z",
  },
  {
    id: 3,
    org_id: 1,
    user_id: "user-3",
    role: "member",
    status: "pending",
    name: "Bob Member",
    email: "bob@operion.dev",
    invited_at: "2026-07-20T00:00:00Z",
  },
]

const mockInvitations: OrganizationInvitation[] = [
  {
    id: 1,
    org_id: 1,
    email: "charlie@operion.dev",
    role: "member",
    token: "invite-token-abc123",
    invited_by: "user-1",
    invited_by_name: "Test User",
    status: "pending",
    created_at: "2026-07-25T10:00:00Z",
    expires_at: "2026-08-25T10:00:00Z",
  },
  {
    id: 2,
    org_id: 1,
    email: "diana@operion.dev",
    role: "admin",
    token: "invite-token-def456",
    invited_by: "user-1",
    invited_by_name: "Test User",
    status: "accepted",
    created_at: "2026-07-15T08:00:00Z",
    expires_at: "2026-08-15T08:00:00Z",
  },
  {
    id: 3,
    org_id: 1,
    email: "erin@operion.dev",
    role: "member",
    token: "invite-token-expired789",
    invited_by: "user-1",
    invited_by_name: "Test User",
    status: "expired",
    created_at: "2026-06-01T10:00:00Z",
    expires_at: "2026-07-01T10:00:00Z",
  },
]

export const organizationsHandlers = [
  http.get("*/api/v1/organizations", () => {
    return HttpResponse.json(mockOrganizations)
  }),

  http.get("*/api/v1/organizations/:id", ({ params }) => {
    const org = mockOrganizations.find((o) => o.id === Number(params.id))
    if (!org) {
      return HttpResponse.json({ detail: "Organization not found" }, { status: 404 })
    }
    return HttpResponse.json(org)
  }),

  http.patch("*/api/v1/organizations/:id", async ({ params, request }) => {
    const org = mockOrganizations.find((o) => o.id === Number(params.id))
    if (!org) {
      return HttpResponse.json({ detail: "Organization not found" }, { status: 404 })
    }
    const body = (await request.json()) as Partial<Organization>
    const updated = { ...org, ...body, updated_at: new Date().toISOString() }
    return HttpResponse.json(updated)
  }),

  http.get("*/api/v1/organizations/:id/members", () => {
    return HttpResponse.json(mockMembers)
  }),

  http.delete("*/api/v1/organizations/:id/members/:memberId", ({ params }) => {
    const member = mockMembers.find((m) => m.id === Number(params.memberId) && m.org_id === Number(params.id))
    if (!member) {
      return HttpResponse.json({ detail: "Member not found" }, { status: 404 })
    }
    return HttpResponse.json({ detail: "Member removed successfully" })
  }),

  http.get("*/api/v1/organizations/:id/invitations", () => {
    return HttpResponse.json(mockInvitations)
  }),

  http.post("*/api/v1/organizations/:id/invitations", async ({ request }) => {
    const body = (await request.json()) as { email: string; role: string }
    const newInvitation: OrganizationInvitation = {
      id: mockInvitations.length + 1,
      org_id: 1,
      email: body.email,
      role: body.role ?? "member",
      token: `invite-token-${Math.random().toString(36).substring(2, 10)}`,
      invited_by: "user-1",
      invited_by_name: "Test User",
      status: "pending",
      created_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
    }
    return HttpResponse.json(newInvitation, { status: 201 })
  }),

  http.delete("*/api/v1/organizations/:id/invitations/:invitationId", ({ params }) => {
    const invitation = mockInvitations.find((i) => i.id === Number(params.invitationId))
    if (!invitation) {
      return HttpResponse.json({ detail: "Invitation not found" }, { status: 404 })
    }
    return HttpResponse.json({ detail: "Invitation revoked successfully" })
  }),

  http.post("*/api/v1/organizations/invitations/:token/accept", ({ params }) => {
    const token = String(params.token)
    const invitation = mockInvitations.find((i) => i.token === token)
    if (!invitation) {
      return HttpResponse.json(
        { detail: "Invalid invitation token", error_code: "invitation/invalid" },
        { status: 404 },
      )
    }
    if (invitation.status === "expired") {
      return HttpResponse.json(
        { detail: "Invitation has expired", error_code: "invitation/expired" },
        { status: 400 },
      )
    }
    if (invitation.status === "accepted") {
      return HttpResponse.json(
        { detail: "Invitation already accepted", error_code: "invitation/already-accepted" },
        { status: 409 },
      )
    }
    // pending → accept
    invitation.status = "accepted"
    const newMember: OrganizationMember = {
      id: mockMembers.length + 1,
      org_id: invitation.org_id,
      user_id: `user-${mockMembers.length + 1}`,
      role: invitation.role as "owner" | "admin" | "member",
      status: "active",
      name: invitation.email.split("@")[0],
      email: invitation.email,
      joined_at: new Date().toISOString(),
    }
    mockMembers.push(newMember)
    return HttpResponse.json(newMember)
  }),
]
