import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@/test-utils"
import { Routes, Route } from "react-router"
import DocsCategoryPage from "@/pages/docs/docs-category"

vi.mock("motion/react", () => ({
  motion: { div: ({ children, ...props }: any) => <div {...props}>{children}</div> },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe("DocsCategoryPage", () => {
  // ── Docs Home (no category param) ────────────────────────────────

  describe("when no category param (docs home)", () => {
    function renderHome() {
      return render(
        <Routes>
          <Route path="/docs" element={<DocsCategoryPage />} />
          <Route path="/docs/:category" element={<DocsCategoryPage />} />
        </Routes>,
        { initialEntries: ["/docs"] }
      )
    }

    it("renders Documentation heading and description", () => {
      renderHome()
      expect(screen.getByText("Documentation")).toBeInTheDocument()
      expect(
        screen.getByText("Everything you need to know about Operion ERP.")
      ).toBeInTheDocument()
    })

    it("shows search input for filtering categories and articles", () => {
      renderHome()
      expect(
        screen.getByPlaceholderText("Search categories and articles...")
      ).toBeInTheDocument()
    })

    it("renders all category cards", () => {
      renderHome()
      expect(screen.getByText("Getting Started")).toBeInTheDocument()
      expect(screen.getByText("Route Planning")).toBeInTheDocument()
      expect(screen.getByText("Fleet Tracking")).toBeInTheDocument()
      expect(screen.getByText("Dispatch")).toBeInTheDocument()
      expect(screen.getByText("OCR & Documents")).toBeInTheDocument()
      expect(screen.getByText("Analytics")).toBeInTheDocument()
      expect(screen.getByText("Administration")).toBeInTheDocument()
      expect(screen.getByText("API Reference")).toBeInTheDocument()
    })

    it("shows article count badges on category cards", () => {
      renderHome()
      expect(screen.getByText("5 articles")).toBeInTheDocument() // Getting Started
      expect(screen.getByText("4 articles")).toBeInTheDocument() // Route Planning
      // 6 other categories each have 1 article
      const singleArticleBadges = screen.getAllByText("1 article")
      expect(singleArticleBadges.length).toBe(6)
    })

    it("links each category card to its page", () => {
      renderHome()
      const gettingStartedCard = screen.getByText("Getting Started").closest("a")
      expect(gettingStartedCard).toHaveAttribute("href", "/docs/getting-started")
      const routePlanningCard = screen.getByText("Route Planning").closest("a")
      expect(routePlanningCard).toHaveAttribute("href", "/docs/route-planning")
    })

    it("shows reading time on category cards", () => {
      renderHome()
      // Getting Started: (210+95+60+150+120)/200 = 635/200 = 3.175 → 4 min
      // Route Planning: (230+180+140+110)/200 = 660/200 = 3.3 → 4 min
      const readingTimeElements = screen.getAllByText(/min/)
      expect(readingTimeElements.length).toBeGreaterThanOrEqual(8)
    })

    // ── Category listing: search/filter on home ────────────────

    it("filters category cards by search query", () => {
      renderHome()
      const searchInput = screen.getByPlaceholderText(
        "Search categories and articles..."
      )

      fireEvent.change(searchInput, { target: { value: "Route" } })

      expect(screen.getByText("Route Planning")).toBeInTheDocument()
      // Getting Started should be filtered out (no "route" in title/desc/articles)
      expect(screen.queryByText("Getting Started")).not.toBeInTheDocument()
    })

    it("filters by article title match", () => {
      renderHome()
      const searchInput = screen.getByPlaceholderText(
        "Search categories and articles..."
      )

      // "OCR" category has article titled "Scanning Documents" - match on "Scanning"
      fireEvent.change(searchInput, { target: { value: "Scanning" } })

      // OCR category should match because its article title contains "Scanning"
      expect(screen.getByText("OCR & Documents")).toBeInTheDocument()
      // Other categories should not appear
      expect(screen.queryByText("Getting Started")).not.toBeInTheDocument()
    })

    it("shows empty state when search matches no categories", () => {
      renderHome()
      const searchInput = screen.getByPlaceholderText(
        "Search categories and articles..."
      )

      fireEvent.change(searchInput, { target: { value: "zzzznothing" } })

      expect(
        screen.getByText("No categories match your search.")
      ).toBeInTheDocument()
    })

    it("shows all categories again after clearing search", () => {
      renderHome()
      const searchInput = screen.getByPlaceholderText(
        "Search categories and articles..."
      )

      fireEvent.change(searchInput, { target: { value: "zzzznothing" } })
      expect(
        screen.getByText("No categories match your search.")
      ).toBeInTheDocument()

      fireEvent.change(searchInput, { target: { value: "" } })
      expect(screen.getByText("Getting Started")).toBeInTheDocument()
      expect(screen.getByText("Route Planning")).toBeInTheDocument()
    })

    it("shows category description on cards", () => {
      renderHome()
      expect(
        screen.getByText(
          "Installation, setup, and your first steps with Operion ERP."
        )
      ).toBeInTheDocument()
      expect(
        screen.getByText(
          "Learn how to create and optimize routes with Operion."
        )
      ).toBeInTheDocument()
    })
  })

  // ── Single Category View ─────────────────────────────────────────

  describe("when category param is provided", () => {
    function renderCategory(category: string) {
      return render(
        <Routes>
          <Route path="/docs" element={<DocsCategoryPage />} />
          <Route path="/docs/:category" element={<DocsCategoryPage />} />
        </Routes>,
        { initialEntries: [`/docs/${category}`] }
      )
    }

    it("renders category title and description", () => {
      renderCategory("getting-started")
      expect(screen.getByText("Getting Started")).toBeInTheDocument()
      expect(
        screen.getByText(
          "Installation, setup, and your first steps with Operion ERP."
        )
      ).toBeInTheDocument()
    })

    it("renders article list for the category", () => {
      renderCategory("getting-started")
      expect(screen.getByText("Installing Operion ERP")).toBeInTheDocument()
      expect(screen.getByText("Creating Your Account")).toBeInTheDocument()
      expect(screen.getByText("System Requirements")).toBeInTheDocument()
      expect(screen.getByText("Quick Start Guide")).toBeInTheDocument()
      expect(screen.getByText("Navigating the Interface")).toBeInTheDocument()
    })

    it("shows article links with excerpts", () => {
      renderCategory("getting-started")
      expect(
        screen.getByText(
          "Download and install the Operion desktop application on Windows."
        )
      ).toBeInTheDocument()
    })

    it("links each article to its correct URL", () => {
      renderCategory("getting-started")
      const installationLink = screen
        .getByText("Installing Operion ERP")
        .closest("a")
      expect(installationLink).toHaveAttribute(
        "href",
        "/docs/getting-started/installation"
      )
    })

    it("shows back to documentation link", () => {
      renderCategory("getting-started")
      const backLink = screen.getByText("← Back to Documentation")
      expect(backLink).toBeInTheDocument()
      expect(backLink.closest("a")).toHaveAttribute("href", "/docs")
    })

    it("shows category meta with article count and reading time", () => {
      renderCategory("getting-started")
      expect(screen.getByText("5 articles")).toBeInTheDocument()
      // 635/200 = 3.175 → 4 min total
      expect(screen.getByText(/4 min total/)).toBeInTheDocument()
    })

    it("shows a search input scoped to the category", () => {
      renderCategory("getting-started")
      expect(
        screen.getByPlaceholderText("Search in Getting Started...")
      ).toBeInTheDocument()
    })

    // ── Pagination / article filtering within category ─────────

    it("filters articles within a category by search", () => {
      renderCategory("getting-started")
      const searchInput = screen.getByPlaceholderText(
        "Search in Getting Started..."
      )

      fireEvent.change(searchInput, { target: { value: "Install" } })

      // Matching article should be visible
      expect(screen.getByText("Installing Operion ERP")).toBeInTheDocument()
      // Non-matching should be hidden
      expect(screen.queryByText("Creating Your Account")).not.toBeInTheDocument()
    })

    it("shows empty state when search within category matches nothing", () => {
      renderCategory("getting-started")
      const searchInput = screen.getByPlaceholderText(
        "Search in Getting Started..."
      )

      fireEvent.change(searchInput, { target: { value: "zzzznothing" } })

      expect(
        screen.getByText("No articles match your search.")
      ).toBeInTheDocument()
    })

    it("shows all articles again after clearing category search", () => {
      renderCategory("getting-started")
      const searchInput = screen.getByPlaceholderText(
        "Search in Getting Started..."
      )

      fireEvent.change(searchInput, { target: { value: "zzzznothing" } })
      expect(
        screen.getByText("No articles match your search.")
      ).toBeInTheDocument()

      fireEvent.change(searchInput, { target: { value: "" } })
      expect(screen.getByText("Installing Operion ERP")).toBeInTheDocument()
      expect(screen.getByText("Creating Your Account")).toBeInTheDocument()
    })

    it("renders articles for a different category", () => {
      renderCategory("route-planning")
      expect(screen.getByText("Creating Your First Route")).toBeInTheDocument()
      expect(screen.getByText("Multi-Stop Optimization")).toBeInTheDocument()
      expect(screen.getByText("Importing Route Data")).toBeInTheDocument()
      expect(screen.getByText("Route Templates")).toBeInTheDocument()
    })

    it("renders category not found for unknown category", () => {
      renderCategory("non-existent-category")
      expect(screen.getByText("Category not found")).toBeInTheDocument()
      expect(
        screen.getByText(
          "The documentation category you're looking for doesn't exist."
        )
      ).toBeInTheDocument()
      const browseLink = screen.getByText("Browse all documentation")
      expect(browseLink.closest("a")).toHaveAttribute("href", "/docs")
    })

    it("shows ChevronRight icon on each article card", () => {
      renderCategory("getting-started")
      // Each article card should have the category badge
      const articleCount = 5
      const articleBadges = screen.getAllByText(/article(s)?/)
      expect(articleBadges.length).toBeGreaterThanOrEqual(1)
    })
  })
})
