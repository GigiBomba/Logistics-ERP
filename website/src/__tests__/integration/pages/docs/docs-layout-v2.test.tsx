import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
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
        </Route>
      </Routes>,
      { initialEntries: [initialPath] }
    )
  }

  it("shows Documentation heading in sidebar", () => {
    renderAtPath("/docs")
    expect(screen.getByText("Documentation")).toBeInTheDocument()
  })

  it("shows search input with filter placeholder", () => {
    renderAtPath("/docs")
    expect(screen.getByPlaceholderText("Filter sections...")).toBeInTheDocument()
  })

  it("renders all category links in the sidebar", () => {
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

  it("renders outlet content from nested route", () => {
    renderAtPath("/docs")
    expect(screen.getByTestId("outlet-content")).toBeInTheDocument()
    expect(screen.getByText("Docs Home")).toBeInTheDocument()
  })

  it("highlights the current sidebar item as active", () => {
    renderAtPath("/docs/getting-started")
    const link = screen.getByText("Getting Started").closest("a")
    expect(link?.className).toContain("bg-accent")
  })

  it("does not highlight other sidebar items when one is active", () => {
    renderAtPath("/docs/getting-started")
    const routePlanningLink = screen.getByText("Route Planning").closest("a")
    // `hover:bg-accent` is present on all links; check plain `bg-accent` is absent
    const classes = routePlanningLink?.className.split(" ") ?? []
    expect(classes).not.toContain("bg-accent")
  })
})
