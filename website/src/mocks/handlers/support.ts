import { http, HttpResponse } from "msw"
import type { SupportTicket } from "@/types"

const mockTickets: SupportTicket[] = [
  {
    id: 1,
    subject: "Cannot connect scanner to Wi-Fi",
    status: "open",
    priority: "high",
    created_at: "2026-07-28T09:00:00Z",
    updated_at: "2026-07-28T09:00:00Z",
  },
  {
    id: 2,
    subject: "Billing inquiry for July invoice",
    status: "in_progress",
    priority: "medium",
    created_at: "2026-07-27T14:00:00Z",
    updated_at: "2026-07-28T10:30:00Z",
  },
  {
    id: 3,
    subject: "Feature request: bulk label printing",
    status: "resolved",
    priority: "low",
    created_at: "2026-07-20T08:00:00Z",
    updated_at: "2026-07-25T16:00:00Z",
  },
  {
    id: 4,
    subject: "API rate limiting issue",
    status: "closed",
    priority: "urgent",
    created_at: "2026-07-15T11:00:00Z",
    updated_at: "2026-07-16T09:00:00Z",
  },
]

export const supportHandlers = [
  http.get("*/api/v1/support/tickets", ({ request }) => {
    const url = new URL(request.url)
    const status = url.searchParams.get("status")
    let filtered = mockTickets
    if (status) {
      filtered = mockTickets.filter((t) => t.status === status)
    }
    return HttpResponse.json(filtered)
  }),

  http.get("*/api/v1/support/tickets/:id", ({ params }) => {
    const ticket = mockTickets.find((t) => t.id === Number(params.id))
    if (!ticket) {
      return HttpResponse.json({ detail: "Ticket not found" }, { status: 404 })
    }
    return HttpResponse.json(ticket)
  }),

  http.post("*/api/v1/support/tickets", async ({ request }) => {
    const body = (await request.json()) as Partial<SupportTicket>
    const newTicket: SupportTicket = {
      id: mockTickets.length + 1,
      subject: body.subject ?? "Untitled Ticket",
      status: "open",
      priority: body.priority ?? "medium",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }
    return HttpResponse.json(newTicket, { status: 201 })
  }),

  http.patch("*/api/v1/support/tickets/:id", async ({ params, request }) => {
    const ticket = mockTickets.find((t) => t.id === Number(params.id))
    if (!ticket) {
      return HttpResponse.json({ detail: "Ticket not found" }, { status: 404 })
    }
    const body = (await request.json()) as Partial<SupportTicket>
    const updated = { ...ticket, ...body, updated_at: new Date().toISOString() }
    return HttpResponse.json(updated)
  }),

  http.delete("*/api/v1/support/tickets/:id", ({ params }) => {
    const ticket = mockTickets.find((t) => t.id === Number(params.id))
    if (!ticket) {
      return HttpResponse.json({ detail: "Ticket not found" }, { status: 404 })
    }
    return HttpResponse.json({ detail: "Ticket deleted successfully" })
  }),
]
