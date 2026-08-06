import { http, HttpResponse } from "msw"
import type { PortalNotification } from "@/types"

const mockNotifications: PortalNotification[] = [
  {
    id: "notif-1",
    type: "release",
    title: "New version 2.5.0 available",
    message: "Version 2.5.0 is now available with enhanced OCR capabilities and performance improvements.",
    read: false,
    link: "/changelog",
    created_at: "2026-07-29T08:00:00Z",
  },
  {
    id: "notif-2",
    type: "billing",
    title: "Invoice available",
    message: "Your July invoice has been generated and is ready for review.",
    read: false,
    link: "/dashboard/billing/invoices",
    created_at: "2026-07-28T12:00:00Z",
  },
  {
    id: "notif-3",
    type: "security",
    title: "Security alert: new login",
    message: "A new login was detected from New York, US on July 27.",
    read: true,
    created_at: "2026-07-27T09:00:00Z",
  },
  {
    id: "notif-4",
    type: "support",
    title: "Support ticket updated",
    message: "Your ticket #2 (Billing inquiry) has been updated by support.",
    read: true,
    link: "/dashboard/support",
    created_at: "2026-07-26T14:00:00Z",
  },
  {
    id: "notif-5",
    type: "system",
    title: "Scheduled maintenance",
    message: "The system will undergo maintenance on August 1st from 02:00-04:00 UTC.",
    read: false,
    created_at: "2026-07-25T10:00:00Z",
  },
]

export const notificationsHandlers = [
  http.get("*/api/v1/notifications", ({ request }) => {
    const url = new URL(request.url)
    const unreadOnly = url.searchParams.get("unread_only")
    let filtered = mockNotifications
    if (unreadOnly === "true") {
      filtered = mockNotifications.filter((n) => !n.read)
    }
    return HttpResponse.json(filtered)
  }),

  http.get("*/api/v1/notifications/unread-count", () => {
    const unreadCount = mockNotifications.filter((n) => !n.read).length
    return HttpResponse.json({ count: unreadCount })
  }),

  http.patch("*/api/v1/notifications/:id/read", ({ params }) => {
    const notification = mockNotifications.find((n) => n.id === params.id)
    if (!notification) {
      return HttpResponse.json({ detail: "Notification not found" }, { status: 404 })
    }
    return HttpResponse.json({ ...notification, read: true })
  }),

  http.post("*/api/v1/notifications/read-all", () => {
    return HttpResponse.json({ detail: "All notifications marked as read" })
  }),
]
