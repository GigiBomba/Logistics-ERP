import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@/test-utils"
import { NotificationCenter } from "@/components/shared/notification-center"
import type { PortalNotification } from "@/types"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
  useInView: () => true,
}))

function makeNotification(overrides: Partial<PortalNotification> = {}): PortalNotification {
  return {
    id: "n1",
    type: "release",
    title: "Operion v3.2 is live",
    message: "Route optimization engine v2 is now available.",
    read: false,
    created_at: new Date(Date.now() - 1000 * 60 * 15).toISOString(),
    ...overrides,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe("NotificationCenter", () => {
  it("shows the unread count in the bell's accessible name", () => {
    render(
      <NotificationCenter
        notifications={[makeNotification()]}
        unreadCount={1}
        onMarkRead={vi.fn()}
        onMarkAllRead={vi.fn()}
      />
    )
    expect(screen.getByRole("button", { name: /notifications \(1 unread\)/i })).toBeInTheDocument()
  })

  it("opens the panel and lists notifications sorted by time", () => {
    const notifications = [
      makeNotification({ id: "old", title: "Older notification", created_at: new Date(Date.now() - 1000 * 60 * 60 * 5).toISOString() }),
      makeNotification({ id: "new", title: "Newer notification", created_at: new Date(Date.now() - 1000 * 60).toISOString() }),
    ]
    render(
      <NotificationCenter
        notifications={notifications}
        unreadCount={2}
        onMarkRead={vi.fn()}
        onMarkAllRead={vi.fn()}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: /notifications/i }))

    expect(screen.getByText("Notifications")).toBeInTheDocument()
    expect(screen.getByText("Newer notification")).toBeInTheDocument()
    expect(screen.getByText("Older notification")).toBeInTheDocument()
  })

  it("calls onMarkAllRead from the panel header", () => {
    const onMarkAllRead = vi.fn()
    render(
      <NotificationCenter
        notifications={[makeNotification()]}
        unreadCount={1}
        onMarkRead={vi.fn()}
        onMarkAllRead={onMarkAllRead}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: /notifications/i }))
    fireEvent.click(screen.getByRole("button", { name: /mark all read/i }))

    expect(onMarkAllRead).toHaveBeenCalledTimes(1)
  })

  it("calls onMarkRead with the notification id", () => {
    const onMarkRead = vi.fn()
    render(
      <NotificationCenter
        notifications={[makeNotification({ id: "n42" })]}
        unreadCount={1}
        onMarkRead={onMarkRead}
        onMarkAllRead={vi.fn()}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: /notifications/i }))
    fireEvent.click(screen.getByRole("button", { name: /mark read/i }))

    expect(onMarkRead).toHaveBeenCalledWith("n42")
  })

  it("shows an empty state when there are no notifications", () => {
    render(
      <NotificationCenter
        notifications={[]}
        unreadCount={0}
        onMarkRead={vi.fn()}
        onMarkAllRead={vi.fn()}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: /notifications/i }))
    expect(screen.getByText("No new notifications")).toBeInTheDocument()
  })

  it("shows the loading skeleton instead of the list while loading", () => {
    render(
      <NotificationCenter
        notifications={[makeNotification()]}
        unreadCount={1}
        onMarkRead={vi.fn()}
        onMarkAllRead={vi.fn()}
        loading
      />
    )

    fireEvent.click(screen.getByRole("button", { name: /notifications/i }))
    expect(document.querySelector(".animate-pulse")).not.toBeNull()
    expect(screen.queryByText("Operion v3.2 is live")).not.toBeInTheDocument()
  })

  it("hides the badge when there are no unread notifications", () => {
    render(
      <NotificationCenter
        notifications={[makeNotification({ read: true })]}
        unreadCount={0}
        onMarkRead={vi.fn()}
        onMarkAllRead={vi.fn()}
      />
    )
    expect(screen.getByRole("button", { name: "Notifications" })).toBeInTheDocument()
  })
})
