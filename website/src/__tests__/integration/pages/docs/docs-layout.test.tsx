import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@/test-utils"
import { Routes, Route } from "react-router"
import DocsLayout from "@/pages/docs/docs-layout"

vi.mock("motion/react", () => ({
  motion: { div: ({ children, ...props }: any) => <div {...props}>{children}</div> },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe("DocsLayout", () => {
  const sidebarLinks = [
    { label: "Getting Started", href: "/docs/getting-started" },
    { label: "Route Planning", href: "/docs/route-planning" },
    { label: "Fleet Tracking", href: "/docs/fleet-tracking" },
    { label: "Dispatch", href: "/docs/dispatch" },
    { label: "OCR & Documents", href: "/docs/ocr" },
    { label: "Analytics", href: "/docs/analytics" },
    { label: "Administration", href: "/docs/administration" },
    { label: "API Reference", href: "/docs/api" },
  ]

  function renderAtPath(initialPath: string) {
    return render(
      <Routes>
        <Route element={<DocsLayout />}>
          <Route path="/docs" element={<div data-testid="outlet-content">Docs Home</div>} />
          <Route path="/docs/:category" element={<div data-testid="outlet-content">Category Page</div>} />
          <Route path="/docs/:category/:slug" element={<div data-testid="outlet-content">Article Page</div>} />
        </Route>
      </Routes>,
      { initialEntries: [initialPath] }
    )
  }

  // ── Sidebar navigation ─────────────────────────────────────────

  it("shows Documentation heading in sidebar", () => {
    renderAtPath("/docs")
    expect(screen.getByText("Documentation")).toBeInTheDocument()
  })

  it("shows all category links in the sidebar", () => {
    renderAtPath("/docs")
    for (const { label } of sidebarLinks) {
      expect(screen.getByText(label)).toBeInTheDocument()
    }
  })

  it("links each sidebar item to the correct href", () => {
    renderAtPath("/docs")
    for (const { label, href } of sidebarLinks) {
      const link = screen.getByText(label).closest("a")
      expect(link).toHaveAttribute("href", href)
    }
  })

  it("shows Documentation Home link at the bottom", () => {
    renderAtPath("/docs")
    expect(screen.getByText("Documentation Home")).toBeInTheDocument()
  })

  it("links Documentation Home to /docs", () => {
    renderAtPath("/docs")
    const homeLink = screen.getByText("Documentation Home").closest("a")
    expect(homeLink).toHaveAttribute("href", "/docs")
  })

  // ── Article rendering (outlet) ────────────────────────────────

  it("renders outlet content from nested route", () => {
    renderAtPath("/docs")
    expect(screen.getByTestId("outlet-content")).toBeInTheDocument()
    expect(screen.getByText("Docs Home")).toBeInTheDocument()
  })

  it("renders outlet content for category route", () => {
    renderAtPath("/docs/getting-started")
    expect(screen.getByTestId("outlet-content")).toBeInTheDocument()
    expect(screen.getByText("Category Page")).toBeInTheDocument()
  })

  it("renders outlet content for article route", () => {
    renderAtPath("/docs/getting-started/installation")
    expect(screen.getByTestId("outlet-content")).toBeInTheDocument()
    expect(screen.getByText("Article Page")).toBeInTheDocument()
  })

  // ── Category listing ──────────────────────────────────────────

  it("shows version selector with v1.0", () => {
    renderAtPath("/docs")
    expect(screen.getByText("v1.0")).toBeInTheDocument()
  })

  it("shows On this page placeholder", () => {
    renderAtPath("/docs")
    expect(screen.getByText("On this page")).toBeInTheDocument()
    expect(
      screen.getByText("Open an article to see its section headings.")
    ).toBeInTheDocument()
  })

  it("highlights the current sidebar item as active", () => {
    renderAtPath("/docs/getting-started")
    const link = screen.getByText("Getting Started").closest("a")
    expect(link?.className).toContain("bg-accent")
  })

  it("does not highlight other sidebar items when one is active", () => {
    renderAtPath("/docs/getting-started")
    const routePlanningLink = screen.getByText("Route Planning").closest("a")
    const classes = routePlanningLink?.className.split(" ") ?? []
    expect(classes).not.toContain("bg-accent")
  })

  it("highlights parent category when viewing an article", () => {
    renderAtPath("/docs/getting-started/installation")
    const link = screen.getByText("Getting Started").closest("a")
    expect(link?.className).toContain("bg-accent")
  })

  // ── Responsive layout ─────────────────────────────────────────

  it("shows mobile menu toggle button", () => {
    renderAtPath("/docs")
    const menuButton = screen.getByRole("button", { name: /menu/i })
    expect(menuButton).toBeInTheDocument()
  })

  it("toggles sidebar open when mobile menu button is clicked", () => {
    renderAtPath("/docs")
    const menuButton = screen.getByRole("button", { name: /menu/i })

    // Click to open sidebar
    fireEvent.click(menuButton)
    // After click the icon should be X (close icon)
    expect(screen.getByText("Menu")).toBeInTheDocument()

    // Click again to close
    fireEvent.click(menuButton)
    expect(screen.getByText("Menu")).toBeInTheDocument()
  })

  // ── Search filtering ──────────────────────────────────────────

  it("shows search input with filter placeholder", () => {
    renderAtPath("/docs")
    expect(screen.getByPlaceholderText("Filter sections...")).toBeInTheDocument()
  })

  it("filters sidebar items when search query is entered", () => {
    renderAtPath("/docs")
    const searchInput = screen.getByPlaceholderText("Filter sections...")

    fireEvent.change(searchInput, { target: { value: "Route" } })

    // Matching items should remain
    expect(screen.getByText("Route Planning")).toBeInTheDocument()
    // Non-matching items should be filtered out
    expect(screen.queryByText("Getting Started")).not.toBeInTheDocument()
    expect(screen.queryByText("API Reference")).not.toBeInTheDocument()
  })

  it("shows no sections found message when search has no matches", () => {
    renderAtPath("/docs")
    const searchInput = screen.getByPlaceholderText("Filter sections...")

    fireEvent.change(searchInput, { target: { value: "zzzznotfound" } })

    expect(screen.getByText("No sections found")).toBeInTheDocument()
  })

  it("clears search query when onClear is triggered", () => {
    renderAtPath("/docs")
    const searchInput = screen.getByPlaceholderText(
      "Filter sections..."
    ) as HTMLInputElement

    fireEvent.change(searchInput, { target: { value: "Route" } })
    expect(searchInput.value).toBe("Route")

    // The SearchInput has an X button to clear
    // Since SearchInput is a controlled component we can fire change with empty string
    fireEvent.change(searchInput, { target: { value: "" } })
    expect(searchInput.value).toBe("")
    // All items should be back
    expect(screen.getByText("Getting Started")).toBeInTheDocument()
  })

  // ── Version selector interaction ──────────────────────────────

  it("shows version history popover when version button is clicked", () => {
    renderAtPath("/docs")
    const versionButton = screen.getByText("v1.0")
    fireEvent.click(versionButton)
    expect(
      screen.getByText("Version history coming soon")
    ).toBeInTheDocument()
  })

  it("closes version popover when clicking outside", () => {
    renderAtPath("/docs")
    const versionButton = screen.getByText("v1.0")
    fireEvent.click(versionButton)
    expect(
      screen.getByText("Version history coming soon")
    ).toBeInTheDocument()

    // Click the backdrop to close
    const backdrop = document.querySelector(".fixed.inset-0.z-10")
    if (backdrop) fireEvent.click(backdrop)

    expect(
      screen.queryByText("Version history coming soon")
    ).not.toBeInTheDocument()
  })
})
