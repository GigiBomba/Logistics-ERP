import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@/test-utils"
import { NotificationCenter, MOCK_NOTIFICATIONS } from "@/components/shared/notification-center"

vi.mock("motion/react", () => {
  const MotionComponent = (props: any) => {
    const { children, ...rest } = props
    return <div {...rest}>{children}</div>
  }
  return {
    motion: new Proxy(
      {},
      {
        get: () => MotionComponent,
      }
    ),
    AnimatePresence: ({ children }: any) => <>{children}</>,
  }
})

function getDefaultProps(overrides = {}) {
  return {
    notifications: MOCK_NOTIFICATIONS,
    unreadCount: MOCK_NOTIFICATIONS.filter((n) => !n.read).length,
    onMarkRead: vi.fn(),
    onMarkAllRead: vi.fn(),
    ...overrides,
  }
}

describe("NotificationCenter", () => {
  it("renders the bell notification button", () => {
    render(<NotificationCenter {...getDefaultProps()} />)
    const button = screen.getByRole("button", { name: /notifications/i })
    expect(button).toBeInTheDocument()
  })

  it("shows unread count badge on the bell button", () => {
    render(<NotificationCenter {...getDefaultProps()} />)
    const button = screen.getByRole("button", { name: /notifications \(3 unread\)/i })
    expect(button).toHaveTextContent("3")
  })

  it("shows 9+ badge when unread count exceeds 9", () => {
    const notifications = Array.from({ length: 12 }, (_, i) => ({
      id: `n${i}`,
      type: "system" as const,
      title: `Notification ${i}`,
      message: "Test message",
      read: false,
      created_at: new Date().toISOString(),
    }))
    render(<NotificationCenter {...getDefaultProps({ notifications, unreadCount: 12 })} />)
    const button = screen.getByRole("button", { name: /notifications/i })
    expect(button).toHaveTextContent("9+")
  })

  it("does not show unread badge when unreadCount is 0", () => {
    const notifications = MOCK_NOTIFICATIONS.map((n) => ({ ...n, read: true }))
    render(<NotificationCenter {...getDefaultProps({ notifications, unreadCount: 0 })} />)
    const button = screen.getByRole("button", { name: "Notifications" })
    expect(button).toBeInTheDocument()
    // The badge element should not be present
    const badgeText = button.querySelector('[class*="bg-red-500"]')
    expect(badgeText).not.toBeInTheDocument()
  })

  it("opens the dropdown panel when bell is clicked", () => {
    render(<NotificationCenter {...getDefaultProps()} />)
    const button = screen.getByRole("button", { name: /notifications/i })
    fireEvent.click(button)
    expect(screen.getByText("Notifications")).toBeInTheDocument()
  })

  it("displays all notifications in the dropdown when open", () => {
    render(<NotificationCenter {...getDefaultProps()} />)
    fireEvent.click(screen.getByRole("button", { name: /notifications/i }))

    for (const n of MOCK_NOTIFICATIONS) {
      expect(screen.getByText(n.title)).toBeInTheDocument()
    }
  })

  it("shows unread indicator (blue dot) for unread notifications", () => {
    const { container } = render(<NotificationCenter {...getDefaultProps()} />)
    fireEvent.click(screen.getByRole("button", { name: /notifications/i }))

    const unreadNotifications = MOCK_NOTIFICATIONS.filter((n) => !n.read)
    // Each unread notification has a small colored dot by its title
    const dots = container.querySelectorAll('[class*="bg-primary"]')
    // There should be at least as many dots as unread items (dots + badge)
    expect(dots.length).toBeGreaterThanOrEqual(unreadNotifications.length)
  })

  it("shows empty state when there are no notifications", () => {
    render(<NotificationCenter {...getDefaultProps({ notifications: [], unreadCount: 0 })} />)
    fireEvent.click(screen.getByRole("button", { name: "Notifications" }))
    expect(screen.getByText("No new notifications")).toBeInTheDocument()
    expect(
      screen.getByText("We'll let you know when something arrives.")
    ).toBeInTheDocument()
  })

  it("calls onMarkRead when Mark read button is clicked", () => {
    const onMarkRead = vi.fn()
    render(<NotificationCenter {...getDefaultProps({ onMarkRead })} />)
    fireEvent.click(screen.getByRole("button", { name: /notifications/i }))

    const markReadButtons = screen.getAllByText("Mark read")
    expect(markReadButtons.length).toBeGreaterThan(0)

    fireEvent.click(markReadButtons[0])
    expect(onMarkRead).toHaveBeenCalled()
  })

  it("calls onMarkRead with the correct notification id", () => {
    const onMarkRead = vi.fn()
    render(
      <NotificationCenter
        {...getDefaultProps({
          notifications: [MOCK_NOTIFICATIONS[0]],
          unreadCount: 1,
          onMarkRead,
        })}
      />
    )
    fireEvent.click(screen.getByRole("button", { name: /notifications/i }))
    fireEvent.click(screen.getByText("Mark read"))
    expect(onMarkRead).toHaveBeenCalledWith(MOCK_NOTIFICATIONS[0].id)
  })

  it("calls onMarkAllRead when Mark all read is clicked", () => {
    const onMarkAllRead = vi.fn()
    render(<NotificationCenter {...getDefaultProps({ onMarkAllRead })} />)
    fireEvent.click(screen.getByRole("button", { name: /notifications/i }))
    fireEvent.click(screen.getByText("Mark all read"))
    expect(onMarkAllRead).toHaveBeenCalled()
  })

  it("does not show Mark all read when there are no unread notifications", () => {
    const notifications = MOCK_NOTIFICATIONS.map((n) => ({ ...n, read: true }))
    render(
      <NotificationCenter
        {...getDefaultProps({ notifications, unreadCount: 0 })}
      />
    )
    fireEvent.click(screen.getByRole("button", { name: "Notifications" }))
    expect(screen.queryByText("Mark all read")).not.toBeInTheDocument()
  })

  it("does not show Mark read for already-read notifications", () => {
    const notifications = [
      { ...MOCK_NOTIFICATIONS[0], read: true },
      { ...MOCK_NOTIFICATIONS[1], read: false },
    ]
    render(
      <NotificationCenter
        {...getDefaultProps({
          notifications,
          unreadCount: 1,
        })}
      />
    )
    fireEvent.click(screen.getByRole("button", { name: /notifications/i }))

    const markReadButtons = screen.getAllByText("Mark read")
    expect(markReadButtons.length).toBe(1)
  })

  it("sorts notifications by created_at descending", () => {
    const older = {
      id: "old",
      type: "system" as const,
      title: "Older notification",
      message: "Older message",
      read: false,
      created_at: new Date(Date.now() - 86400000).toISOString(),
    }
    const newer = {
      id: "new",
      type: "system" as const,
      title: "Newer notification",
      message: "Newer message",
      read: false,
      created_at: new Date().toISOString(),
    }
    render(
      <NotificationCenter
        {...getDefaultProps({
          notifications: [older, newer],
          unreadCount: 2,
        })}
      />
    )
    fireEvent.click(screen.getByRole("button", { name: /notifications/i }))

    // Collect all rendered text from notification items (exclude header)
    const notificationItems = document.querySelectorAll('[class*="group flex gap-3"]')
    const titles: string[] = []
    notificationItems.forEach((item) => {
      const titleEl = item.querySelector("p.text-sm.font-medium")
      if (titleEl) titles.push(titleEl.textContent!)
    })

    // Newer should appear before older
    expect(titles[0]).toBe("Newer notification")
    expect(titles[titles.length - 1]).toBe("Older notification")
  })

  it("closes the dropdown when clicking outside", () => {
    render(<NotificationCenter {...getDefaultProps()} />)
    fireEvent.click(screen.getByRole("button", { name: /notifications/i }))
    expect(screen.getByText("Notifications")).toBeInTheDocument()

    // Click outside (on document body)
    fireEvent.mouseDown(document.body)
    expect(screen.queryByText("Notifications")).not.toBeInTheDocument()
  })

  it("closes the dropdown on Escape key", () => {
    render(<NotificationCenter {...getDefaultProps()} />)
    fireEvent.click(screen.getByRole("button", { name: /notifications/i }))
    expect(screen.getByText("Notifications")).toBeInTheDocument()

    fireEvent.keyDown(document, { key: "Escape" })
    expect(screen.queryByText("Notifications")).not.toBeInTheDocument()
  })

  it("toggles dropdown on bell button click", () => {
    render(<NotificationCenter {...getDefaultProps()} />)
    const button = screen.getByRole("button", { name: /notifications/i })

    // Open
    fireEvent.click(button)
    expect(screen.getByText("Notifications")).toBeInTheDocument()

    // Close (toggle)
    fireEvent.click(button)
    expect(screen.queryByText("Notifications")).not.toBeInTheDocument()
  })

  it("shows loading skeleton state", () => {
    render(<NotificationCenter {...getDefaultProps({ loading: true })} />)
    fireEvent.click(screen.getByRole("button", { name: /notifications/i }))
    // Loading skeleton items should appear (they have animate-pulse class)
    const skeletonItems = document.querySelectorAll(".animate-pulse")
    expect(skeletonItems.length).toBe(4)
  })

  it("does not show Mark all read while loading", () => {
    render(
      <NotificationCenter
        {...getDefaultProps({ loading: true, unreadCount: 3 })}
      />
    )
    fireEvent.click(screen.getByRole("button", { name: /notifications/i }))
    expect(screen.queryByText("Mark all read")).not.toBeInTheDocument()
  })

  it("renders timeAgo text for each notification", () => {
    render(<NotificationCenter {...getDefaultProps()} />)
    fireEvent.click(screen.getByRole("button", { name: /notifications/i }))

    // Notifications have relative time labels like "15m ago", "2h ago", etc.
    // n1 is 15min ago → "15m ago"
    expect(screen.getByText("15m ago")).toBeInTheDocument()
  })

  it("renders a type icon (svg) for each notification", () => {
    const { container } = render(<NotificationCenter {...getDefaultProps()} />)
    fireEvent.click(screen.getByRole("button", { name: /notifications/i }))

    const svgs = container.querySelectorAll("svg")
    // There should be at least one SVG per notification + bell icon
    expect(svgs.length).toBeGreaterThanOrEqual(MOCK_NOTIFICATIONS.length)
  })

  it("forwards className to the root element", () => {
    const { container } = render(
      <NotificationCenter {...getDefaultProps()} className="custom-wrapper" />
    )
    const root = container.querySelector(".custom-wrapper")
    expect(root).toBeInTheDocument()
  })

  it("sets aria-expanded on the bell button", () => {
    render(<NotificationCenter {...getDefaultProps()} />)
    const button = screen.getByRole("button", { name: /notifications/i })

    expect(button.getAttribute("aria-expanded")).toBe("false")
    fireEvent.click(button)
    expect(button.getAttribute("aria-expanded")).toBe("true")
  })
})
