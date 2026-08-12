import { describe, it, expect, beforeEach, afterEach, vi } from "vitest"
import { render, screen } from "@/test-utils"
import userEvent from "@testing-library/user-event"
import OfflineDetector from "@/components/shared/offline-detector"

function setNavigatorOnline(online: boolean) {
  Object.defineProperty(navigator, "onLine", {
    configurable: true,
    get: () => online,
  })
}

describe("OfflineDetector", () => {
  beforeEach(() => {
    setNavigatorOnline(true)
  })

  afterEach(() => {
    setNavigatorOnline(true)
  })

  it("renders nothing while the browser is online", () => {
    render(<OfflineDetector />)
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  })

  it("shows the offline banner when the browser starts offline", () => {
    setNavigatorOnline(false)
    render(<OfflineDetector />)
    expect(screen.getByRole("alert")).toBeInTheDocument()
    expect(screen.getByText(/currently offline/i)).toBeInTheDocument()
  })

  it("appears when an offline event fires and disappears on online", async () => {
    render(<OfflineDetector />)
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()

    setNavigatorOnline(false)
    window.dispatchEvent(new Event("offline"))
    expect(await screen.findByRole("alert")).toBeInTheDocument()

    setNavigatorOnline(true)
    window.dispatchEvent(new Event("online"))
    await vi.waitFor(() => {
      expect(screen.queryByRole("alert")).not.toBeInTheDocument()
    })
  })

  it("dismisses via the close button and stays hidden until going offline again", async () => {
    setNavigatorOnline(false)
    render(<OfflineDetector />)
    const alert = await screen.findByRole("alert")

    await userEvent.click(screen.getByRole("button", { name: /dismiss/i }))
    await vi.waitFor(() => {
      expect(alert).not.toBeVisible()
    })

    // Firing another offline event re-shows the banner (dismissed resets).
    window.dispatchEvent(new Event("offline"))
    expect(await screen.findByRole("alert")).toBeInTheDocument()
  })

  it("links to the offline page", () => {
    setNavigatorOnline(false)
    render(<OfflineDetector />)
    const link = screen.getByRole("link", { name: /view offline/i })
    expect(link).toHaveAttribute("href", "/offline")
  })
})
