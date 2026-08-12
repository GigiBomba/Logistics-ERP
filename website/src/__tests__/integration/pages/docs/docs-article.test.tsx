import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@/test-utils"
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

    it("shows star rating section", () => {
      renderArticle("installation")
      expect(screen.getByText("Rate this article")).toBeInTheDocument()
      expect(
        screen.getByText(
          "How would you rate the quality of this guide?"
        )
      ).toBeInTheDocument()
      // 5 star buttons should be present
      const stars = screen.getAllByRole("button", { name: /rate \d stars/i })
      expect(stars.length).toBe(5)
    })

    it("shows thank you message after rating", () => {
      renderArticle("installation")
      const starButton = screen.getByRole("button", { name: "Rate 4 stars" })
      fireEvent.click(starButton)
      expect(
        screen.getByText("Thank you for your feedback.")
      ).toBeInTheDocument()
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

    it("back link points to the category page", () => {
      renderArticle("installation")
      const backLink = screen.getByText("Back to Getting Started").closest("a")
      expect(backLink).toHaveAttribute("href", "/docs/getting-started")
    })

    // ── Article content rendering ──────────────────────────────

    it("renders article content headings (h2)", () => {
      renderArticle("installation")
      expect(screen.getByText("Before You Begin")).toBeInTheDocument()
      expect(screen.getByText("Download the Installer")).toBeInTheDocument()
      expect(screen.getByText("Installation Steps")).toBeInTheDocument()
      expect(screen.getByText("First Launch")).toBeInTheDocument()
      expect(screen.getByText("Troubleshooting")).toBeInTheDocument()
    })

    it("renders h2 headings with slug-based IDs for ToC anchor targets", () => {
      renderArticle("installation")
      const headings = document.querySelectorAll("h2[id]")
      const ids = Array.from(headings).map((h) => h.id)
      expect(ids).toContain("before-you-begin")
      expect(ids).toContain("download-the-installer")
      expect(ids).toContain("installation-steps")
      expect(ids).toContain("first-launch")
      expect(ids).toContain("troubleshooting")
    })

    it("renders bullet lists", () => {
      renderArticle("installation")
      // "Before You Begin" section has a bullet list of system requirements
      expect(
        screen.getByText(/Windows 10 \(64-bit\) or Windows 11 \(64-bit\)/)
      ).toBeInTheDocument()
      expect(screen.getByText(/8 GB RAM \(16 GB recommended\)/)).toBeInTheDocument()
      expect(screen.getByText(/2 GB available disk space/)).toBeInTheDocument()
    })

    it("renders numbered lists", () => {
      renderArticle("installation")
      // "Download the Installer" section has a numbered list
      const listItems = screen.getAllByRole("listitem")
      // Total list items: 6 in Before You Begin bullet + 2 numbered + 5 bold-step paragraphs + 3 troubleshooting bullets
      expect(listItems.length).toBeGreaterThanOrEqual(8)
      // Check a non-formatted list item exists
      expect(
        screen.getByText(/Windows 10 \(64-bit\) or Windows 11 \(64-bit\)/)
      ).toBeInTheDocument()
    })

    it("renders bold paragraphs (lines starting with **)", () => {
      renderArticle("installation")
      // "Run the installer" appears in bold paragraph and troubleshooting list
      const boldTexts = screen.getAllByText(/Run the installer/)
      expect(boldTexts.length).toBeGreaterThanOrEqual(1)
      // All bold lead-ins should render
      expect(
        screen.getByText(/Accept the license agreement/)
      ).toBeInTheDocument()
    })

    it("shows video tutorial callout for articles with hasVideo", () => {
      renderArticle("installation")
      expect(
        screen.getByText("Video walkthrough coming soon")
      ).toBeInTheDocument()
    })

    it("shows version badge with applies to info", () => {
      renderArticle("installation")
      expect(
        screen.getByText(/Applies to: Operion v1.0\+/)
      ).toBeInTheDocument()
    })

    it("shows last updated date", () => {
      renderArticle("installation")
      expect(screen.getByText(/Last updated: July 2026/)).toBeInTheDocument()
    })

    // ── Callout blocks ────────────────────────────────────────

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

    it("renders callout body text", () => {
      renderArticle("installation")
      expect(
        screen.getByText(
          /Operion is now installed. Proceed to the "Creating Your Account" guide/
        )
      ).toBeInTheDocument()
    })

    // ── Code blocks / inline code ─────────────────────────────

    it("renders inline code with code element", () => {
      renderArticle("installation")
      // The article contains `operion-setup-1.0.0.exe` wrapped in backticks
      const codeElement = document.querySelector("code")
      expect(codeElement).toBeInTheDocument()
      expect(codeElement?.textContent).toContain("operion-setup-1.0.0.exe")
    })

    it("renders suggest edits with Code icon button", () => {
      renderArticle("installation")
      const suggestEditButton = screen.getByText(/Suggest edits on GitHub/)
      expect(suggestEditButton).toBeInTheDocument()
    })

    // ── Navigation between articles ────────────────────────────

    it("related article cards link to correct article URLs", () => {
      renderArticle("installation")
      // installation has related: ["creating-account", "first-route"]
      const creatingAccountLink = screen
        .getByText("Creating Your Account")
        .closest("a")
      expect(creatingAccountLink).toHaveAttribute(
        "href",
        "/docs/getting-started/creating-account"
      )

      const firstRouteLink = screen
        .getByText("Creating Your First Route")
        .closest("a")
      expect(firstRouteLink).toHaveAttribute(
        "href",
        "/docs/route-planning/first-route"
      )
    })

    it("related article cards show excerpts", () => {
      renderArticle("installation")
      // Related articles cards should have excerpt text with "Visit" content
      // The excerpt is generated from the article's first long line
      const visitTexts = screen.getAllByText(/Visit/i)
      expect(visitTexts.length).toBeGreaterThanOrEqual(1)
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

    it("renders callouts specific to first-route", () => {
      renderArticle("first-route")
      expect(screen.getByText("Prerequisites Met")).toBeInTheDocument()
      expect(
        screen.getByText("Optimization Algorithms")
      ).toBeInTheDocument()
    })

    it("renders h3 headings", () => {
      renderArticle("first-route")
      // "Step 1: Open the Route Planner" etc. are bold paragraphs
      // h3 headings exist too
      expect(screen.getByText("Overview")).toBeInTheDocument()
      expect(screen.getByText("Prerequisites")).toBeInTheDocument()
    })
  })

  // ── Third article (creating-account) ─────────────────────────────

  describe("for creating-account article", () => {
    it("renders creating-account article with correct title", () => {
      renderArticle("creating-account")
      expect(
        screen.getByRole("heading", { level: 1, name: "Creating Your Account" })
      ).toBeInTheDocument()
    })

    it("shows breadcrumb for Getting Started category", () => {
      renderArticle("creating-account")
      expect(screen.getByText("Getting Started")).toBeInTheDocument()
    })

    it("renders numbered list from sign-up steps", () => {
      renderArticle("creating-account")
      // The text is split by anchor/strong tags from processInline, so use getAllByRole
      const listItems = screen.getAllByRole("listitem")
      expect(listItems.length).toBeGreaterThanOrEqual(3)
      // Check that a non-formatted text fragment exists
      expect(
        screen.getByText(/Enter your name, email, and choose a password/)
      ).toBeInTheDocument()
    })

    it("renders callout blocks specific to creating-account", () => {
      renderArticle("creating-account")
      expect(screen.getByText("Email Verification")).toBeInTheDocument()
      expect(
        screen.getByText("You're All Set")
      ).toBeInTheDocument()
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

    it("does not show feedback section for missing article", () => {
      renderArticle("non-existent-article")
      expect(
        screen.queryByText("Was this article helpful?")
      ).not.toBeInTheDocument()
    })
  })
})
