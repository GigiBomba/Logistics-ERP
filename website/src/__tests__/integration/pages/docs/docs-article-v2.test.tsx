import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import { Routes, Route } from "react-router"
import DocsArticlePage from "@/pages/docs/docs-article"

vi.mock("motion/react", () => ({
  motion: { div: ({ children, ...props }: any) => <div {...props}>{children}</div> },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe("DocsArticlePage", () => {
  function renderArticle(slug: string) {
    const routeMap: Record<string, string> = {
      installation: "/docs/getting-started/installation",
      "first-route": "/docs/route-planning/first-route",
      "creating-account": "/docs/getting-started/creating-account",
    }
    const path = routeMap[slug] ?? `/docs/unknown/${slug}`

    return render(
      <Routes>
        <Route path="/docs/:category/:slug" element={<DocsArticlePage />} />
      </Routes>,
      { initialEntries: [path] }
    )
  }

  // ── Known article ───────────────────────────────────────────────

  describe("for a known article", () => {
    it("renders the article title as an h1 heading", () => {
      renderArticle("installation")
      expect(
        screen.getByRole("heading", { level: 1, name: "Installing Operion ERP" })
      ).toBeInTheDocument()
    })

    it("shows breadcrumbs: Docs → Category → Title", () => {
      renderArticle("installation")
      expect(screen.getByText("Docs")).toBeInTheDocument()
      expect(screen.getByText("Getting Started")).toBeInTheDocument()
      // Title appears in both breadcrumb and h1
      expect(screen.getAllByText("Installing Operion ERP").length).toBe(2)
    })

    it("shows reading time", () => {
      renderArticle("installation")
      expect(screen.getByText(/min read/)).toBeInTheDocument()
    })

    it("shows tags", () => {
      renderArticle("installation")
      expect(screen.getByText("installation")).toBeInTheDocument()
      expect(screen.getByText("setup")).toBeInTheDocument()
      expect(screen.getByText("Windows")).toBeInTheDocument()
    })

    it("shows Copy article button", () => {
      renderArticle("installation")
      expect(screen.getByText("Copy")).toBeInTheDocument()
    })

    it("shows related articles section", () => {
      renderArticle("installation")
      expect(screen.getByText("Related Articles")).toBeInTheDocument()
      // installation has related: ["creating-account", "first-route"]
      expect(screen.getByText("Creating Your Account")).toBeInTheDocument()
      expect(screen.getByText("Creating Your First Route")).toBeInTheDocument()
    })

    it("shows Was this helpful? feedback section", () => {
      renderArticle("installation")
      expect(
        screen.getByText("Was this article helpful?")
      ).toBeInTheDocument()
      expect(
        screen.getByText(
          "Your feedback helps us improve the documentation."
        )
      ).toBeInTheDocument()
      expect(screen.getByText("Yes")).toBeInTheDocument()
      expect(screen.getByText("No")).toBeInTheDocument()
    })

    it("shows Suggest edits placeholder", () => {
      renderArticle("installation")
      expect(
        screen.getByText(/Suggest edits on GitHub/)
      ).toBeInTheDocument()
    })

    it("shows Back link to category", () => {
      renderArticle("installation")
      expect(screen.getByText("Back to Getting Started")).toBeInTheDocument()
    })

    it("renders callout boxes from markdown content", () => {
      renderArticle("installation")
      // installation article has :::warning "System Requirements"
      expect(screen.getByText("System Requirements")).toBeInTheDocument()
      expect(
        screen.getByText(
          /Ensure your system meets all minimum requirements/
        )
      ).toBeInTheDocument()
      // :::success "Installation Complete"
      expect(screen.getByText("Installation Complete")).toBeInTheDocument()
      // :::info "Need Help?"
      expect(screen.getByText("Need Help?")).toBeInTheDocument()
    })

    it("renders article content (headings and paragraphs)", () => {
      renderArticle("installation")
      expect(screen.getByText("Before You Begin")).toBeInTheDocument()
      expect(screen.getByText("Download the Installer")).toBeInTheDocument()
      expect(screen.getByText("Installation Steps")).toBeInTheDocument()
      expect(screen.getByText("First Launch")).toBeInTheDocument()
      expect(screen.getByText("Troubleshooting")).toBeInTheDocument()
    })
  })

  // ── Different article ────────────────────────────────────────────

  describe("for first-route article", () => {
    it("renders the correct article and its breadcrumbs", () => {
      renderArticle("first-route")
      expect(
        screen.getByRole("heading", { level: 1, name: "Creating Your First Route" })
      ).toBeInTheDocument()
      // Route Planning appears in breadcrumbs and article content (**Route Planning**)
      const routePlanningTexts = screen.getAllByText("Route Planning")
      expect(routePlanningTexts.length).toBeGreaterThanOrEqual(1)
    })

    it("shows tags specific to the article", () => {
      renderArticle("first-route")
      expect(screen.getByText("routes")).toBeInTheDocument()
      expect(screen.getByText("optimization")).toBeInTheDocument()
      expect(screen.getByText("beginners")).toBeInTheDocument()
    })

    it("shows related articles for first-route", () => {
      renderArticle("first-route")
      // first-route has related: ["installation", "multi-stop"]
      expect(screen.getByText("Installing Operion ERP")).toBeInTheDocument()
    })
  })

  // ── Unknown article ──────────────────────────────────────────────

  describe("for an unknown slug", () => {
    it("renders article not found message", () => {
      renderArticle("non-existent-article")
      expect(screen.getByText("Article Not Found")).toBeInTheDocument()
      expect(
        screen.getByText(
          "The article you're looking for doesn't exist yet."
        )
      ).toBeInTheDocument()
    })

    it("shows back to documentation link", () => {
      renderArticle("non-existent-article")
      const backLink = screen.getByText("Back to Documentation")
      expect(backLink.closest("a")).toHaveAttribute("href", "/docs")
    })

    it("does not render article content sections", () => {
      renderArticle("non-existent-article")
      expect(
        screen.queryByText("Before You Begin")
      ).not.toBeInTheDocument()
      expect(screen.queryByText("Copy")).not.toBeInTheDocument()
    })
  })
})
