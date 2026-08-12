import { test, expect, type Page } from "@playwright/test"

// ─── Deterministic API mocks ─────────────────────────────────────────────
//
// The production build talks to the live api.operionerp.xyz backend, which is
// unreachable/401 from the e2e sandbox. The critical tier already routes-mocks
// /api/v1/** for the same reason (see e2e/helpers.ts). Blog / tutorials /
// changelog / roadmap / status content is data-driven, so these tests mock the
// endpoints to render the current real UI deterministically.

const MOCK_BLOG_POSTS = [
  {
    id: 1,
    title: "Introducing AI-Powered OCR for Package Recognition",
    slug: "ai-powered-ocr-package-recognition",
    excerpt: "Our new AI-powered OCR engine can recognize package labels with 99.8% accuracy, even in challenging lighting conditions.",
    author_name: "Sarah Chen",
    category: "AI & Automation",
    tags: ["ai", "ocr", "product"],
    reading_time_minutes: 5,
    published_at: "2026-07-20T10:00:00Z",
  },
  {
    id: 2,
    title: "Trip Profitability: How to Calculate Profit Per Transport Job",
    slug: "how-to-calculate-trip-profitability-road-transport",
    excerpt: "Learn how to calculate trip profitability in road transport. This practical guide covers cost components, revenue tracking, and margin analysis for freight operators.",
    author_name: "Operion Team",
    category: "Profitability & Transport Finance",
    tags: ["trip-profitability", "transport-finance"],
    reading_time_minutes: 8,
    published_at: "2026-07-12T10:00:00Z",
  },
]

const MOCK_AUTHOR = {
  id: "sarah-chen",
  name: "Sarah Chen",
  role: "Engineering Lead",
  bio: "Sarah leads engineering at Operion.",
}

const MOCK_CHANGELOG = [
  { version: "1.0.0", release_date: "2026-09-01", sections: [{ type: "added", items: ["Initial public release"] }] },
  { version: "0.9.0", release_date: "2026-07-20", sections: [{ type: "added", items: ["Beta release for early access partners"] }] },
]

const MOCK_ROADMAP = [
  { id: "r1", title: "AI-Powered Route Optimization", description: "AI-driven route optimization across the fleet.", status: "planned", category: "AI" },
  { id: "r2", title: "Autonomous Dispatch Engine", description: "AI workflow execution engine that turns dispatcher intent into executed operations.", status: "in_progress", category: "Integrations" },
  { id: "r3", title: "Mobile Companion App", description: "Native mobile app for drivers with GPS tracking and messaging.", status: "completed", category: "Mobile" },
]

const MOCK_STATUS = [
  {
    name: "Components",
    services: [
      { name: "Desktop App", status: "operational", updated_at: "2026-08-06T10:00:00Z" },
      { name: "Web Portal", status: "operational", updated_at: "2026-08-06T10:00:00Z" },
      { name: "API Backend", status: "operational", updated_at: "2026-08-06T10:00:00Z" },
    ],
  },
]

const MOCK_TUTORIALS = [
  {
    id: "t1",
    title: "Your First Route Plan",
    slug: "your-first-route-plan",
    excerpt: "Plan your first route from scratch using the Operion route planner.",
    content:
      "<p>This guide walks you through creating your first route.</p><h2>Step 1: Prepare your data</h2><p>Gather your delivery points and vehicle details before you begin.</p><h2>Step 2: Optimize</h2><p>Operion will calculate the most efficient sequence automatically.</p>",
    category: "beginner",
    reading_time_minutes: 6,
    published_at: "2026-07-01T10:00:00Z",
    updated_at: "2026-07-15T10:00:00Z",
  },
  {
    id: "t2",
    title: "Installing Operion ERP on Windows",
    slug: "installing-operion-erp-on-windows",
    excerpt: "Step-by-step installation guide for the Operion desktop application.",
    content: "<p>Download the installer and follow the setup wizard.</p>",
    category: "installation",
    reading_time_minutes: 5,
    published_at: "2026-06-20T10:00:00Z",
    updated_at: "2026-07-01T10:00:00Z",
  },
]

async function mockBlogApi(page: Page) {
  await page.route("**/api/v1/blog/posts**", async (route) => {
    const url = new URL(route.request().url())
    if (/\/blog\/posts\/[^/]+$/.test(url.pathname)) {
      // Force the frontend BLOG_ARTICLES fallback (deterministic article content).
      await route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "Post not found" }) })
      return
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: MOCK_BLOG_POSTS, total: MOCK_BLOG_POSTS.length, page: 1, page_size: 20 }),
    })
  })
  await page.route("**/api/v1/blog/authors/**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_AUTHOR) })
  )
  await page.route("**/api/v1/blog/categories", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) })
  )
}

async function mockTutorialsApi(page: Page) {
  await page.route("**/api/v1/tutorials**", async (route) => {
    const url = new URL(route.request().url())
    const match = url.pathname.match(/\/api\/v1\/tutorials\/([^/]+)$/)
    if (match) {
      const tutorial = MOCK_TUTORIALS.find((t) => t.slug === match[1])
      if (!tutorial) {
        await route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "Tutorial not found" }) })
        return
      }
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(tutorial) })
      return
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_TUTORIALS) })
  })
}

async function mockChangelogApi(page: Page) {
  await page.route("**/api/v1/changelog", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_CHANGELOG) })
  )
}

async function mockRoadmapApi(page: Page) {
  await page.route("**/api/v1/roadmap", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_ROADMAP) })
  )
}

async function mockStatusApi(page: Page) {
  await page.route("**/api/v1/status", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_STATUS) })
  )
}

test.describe("V2 Public Navigation", () => {
  /* ─── Blog Section ─────────────────────────────────────────────── */

  test("/blog page loads", async ({ page }) => {
    await mockBlogApi(page)
    await page.goto("/blog")
    await expect(page.getByRole("heading", { name: /blog/i })).toBeVisible()
    // The blog "All" filter button is "All (N)" — the cookie banner also has
    // "Accept All"/"Reject All" buttons, so scope to the exact count label.
    await expect(page.getByRole("button", { name: /^all \(\d+\)$/i })).toBeVisible()
    await expect(page.getByText("Introducing AI-Powered OCR for Package Recognition")).toBeVisible()
    await expect(page.getByText(/min read/i).first()).toBeVisible()
  })

  test("/blog/:slug loads blog article", async ({ page }) => {
    await mockBlogApi(page)
    await page.goto("/blog/operion-ai-copilot-intelligent-logistics-automation")
    await expect(page.getByRole("heading", { name: /operion ai co-pilot/i })).toBeVisible()
    await expect(page.getByText(/min read/i).first()).toBeVisible()
    // The intro paragraph also mentions "design philosophy" — scope to the h2 section heading.
    await expect(page.getByRole("heading", { name: /design philosophy/i })).toBeVisible()
    await expect(page.getByText(/back to all articles/i)).toBeVisible()
  })

  test("/blog/category/:category filters by category", async ({ page }) => {
    await page.goto("/blog/category/engineering")
    await expect(page.getByRole("heading", { name: /engineering/i })).toBeVisible()
    await expect(page.getByText(/all articles in the engineering/i)).toBeVisible()
  })

  test("/blog/author/:id renders author page", async ({ page }) => {
    await mockBlogApi(page)
    await page.goto("/blog/author/sarah-chen")
    // Author name renders in both the page header (h1) and the profile card (h2).
    await expect(page.getByRole("heading", { name: /sarah chen/i }).first()).toBeVisible()
    // Role renders in the page description ("Engineering Lead at Operion") and the profile card.
    await expect(page.getByText(/engineering lead/i).first()).toBeVisible()
    await expect(page.getByText(/\d+ articles?/i)).toBeVisible()
  })

  /* ─── Changelog, Roadmap, Status ──────────────────────────────── */

  test("/changelog page loads", async ({ page }) => {
    await mockChangelogApi(page)
    await page.goto("/changelog")
    await expect(page.getByRole("heading", { name: /changelog/i })).toBeVisible()
    await expect(page.getByText(/1\.0\.0/i)).toBeVisible()
    await expect(page.getByText(/0\.9\.0/i)).toBeVisible()
  })

  test("/roadmap page loads", async ({ page }) => {
    await mockRoadmapApi(page)
    await page.goto("/roadmap")
    // The h1 "Roadmap" and the h2 "Want to influence the roadmap?" both match — use .first().
    await expect(page.getByRole("heading", { name: /roadmap/i }).first()).toBeVisible()
    // The "All" status filter button renders "View all" — cookie banner buttons ("Accept All") also match /all/i.
    await expect(page.getByRole("button", { name: /^view all$/i })).toBeVisible()
    await expect(page.getByRole("button", { name: /planned/i })).toBeVisible()
    await expect(page.getByRole("button", { name: /in progress/i })).toBeVisible()
    await expect(page.getByRole("button", { name: /completed/i })).toBeVisible()
    await expect(page.getByText(/ai-powered route optimization/i)).toBeVisible()
  })

  test("/status page loads", async ({ page }) => {
    await mockStatusApi(page)
    await page.goto("/status")
    await expect(page.getByRole("heading", { name: /system status/i })).toBeVisible()
    // The footer status link also reads "All systems operational" — scope to the banner heading.
    await expect(page.getByRole("heading", { name: /all systems operational/i })).toBeVisible()
    // The page description also mentions "components" — scope to the group heading.
    await expect(page.getByRole("heading", { name: /^components$/i })).toBeVisible()
    await expect(page.getByText(/desktop app/i)).toBeVisible()
    await expect(page.getByText(/web portal/i)).toBeVisible()
    await expect(page.getByText(/api backend/i)).toBeVisible()
    await expect(page.getByText(/operational/i).first()).toBeVisible()
  })

  /* ─── Security & Developer ────────────────────────────────────── */

  test("/security page loads", async ({ page }) => {
    await page.goto("/security")
    await expect(page.getByRole("heading", { name: /security at operion/i })).toBeVisible()
    await expect(page.getByText(/encryption in transit/i)).toBeVisible()
    await expect(page.getByText(/^access control$/i)).toBeVisible()
    // The bug-bounty paragraph also mentions "responsible disclosures" — scope to the section heading.
    await expect(page.getByRole("heading", { name: /responsible disclosure/i })).toBeVisible()
    await expect(page.getByText(/security faq/i)).toBeVisible()
    await expect(page.getByText(/security@operionerp\.xyz/i)).toBeVisible()
  })

  test("/developers page loads", async ({ page }) => {
    await page.goto("/developers")
    await expect(page.getByRole("heading", { name: /developer resources/i })).toBeVisible()
    await expect(page.getByText(/toolkit/i).first()).toBeVisible()
    await expect(page.getByText(/api reference/i)).toBeVisible()
    await expect(page.getByText(/quick start/i).first()).toBeVisible()
    await expect(page.getByText(/install the toolkit/i)).toBeVisible()
  })

  test("/developers/toolkit page loads", async ({ page }) => {
    await page.goto("/developers/toolkit")
    // h1 "Operion Toolkit" and the download card h2 "Operion Toolkit 1.0.0" both match — anchor the h1.
    await expect(page.getByRole("heading", { name: /^operion toolkit$/i })).toBeVisible()
    await expect(page.getByRole("link", { name: /download toolkit/i })).toBeVisible()
    await expect(page.getByText(/system requirements/i)).toBeVisible()
    // The footer tagline also contains "operating system" — anchor the requirement label.
    await expect(page.getByText(/^operating system$/i)).toBeVisible()
    // "Verify the installation" step heading also contains "installation" — anchor the section heading.
    await expect(page.getByRole("heading", { name: /^installation$/i })).toBeVisible()
    await expect(page.getByText(/download the installer/i)).toBeVisible()
  })

  /* ─── Tutorials ────────────────────────────────────────────────── */

  test("/tutorials page loads", async ({ page }) => {
    await mockTutorialsApi(page)
    await page.goto("/tutorials")
    await expect(page.getByRole("heading", { name: /tutorials/i })).toBeVisible()
    await expect(page.getByPlaceholder(/search tutorials/i)).toBeVisible()
    // The cookie banner also has "Accept All"/"Reject All" — match the exact "All" filter tag.
    await expect(page.getByRole("button", { name: /^all$/i })).toBeVisible()
    await expect(page.getByRole("button", { name: /beginner/i })).toBeVisible()
    await expect(page.getByRole("button", { name: /intermediate/i })).toBeVisible()
    await expect(page.getByText(/installing operion erp/i)).toBeVisible()
    await expect(page.getByText(/min read/i).first()).toBeVisible()
  })

  test("/tutorials/:slug loads tutorial detail", async ({ page }) => {
    await mockTutorialsApi(page)
    await page.goto("/tutorials/your-first-route-plan")
    await expect(page.getByRole("heading", { name: /your first route plan/i })).toBeVisible()
    // Category renders as both the header badge and the tag below the content.
    await expect(page.getByText(/beginner/i).first()).toBeVisible()
    await expect(page.getByText(/min read/i)).toBeVisible()
    // The TOC sidebar mirrors article headings as anchor links — scope to the heading.
    await expect(page.getByRole("heading", { name: /step 1: prepare your data/i })).toBeVisible()
    await expect(page.getByText(/back to tutorials/i)).toBeVisible()
  })

  /* ─── Enhanced Pages (V2 Content) ─────────────────────────────── */

  test("/ home page has V2 sections", async ({ page }) => {
    await page.goto("/")
    await expect(page.getByText("6", { exact: true })).toBeVisible()
    await expect(page.getByText("Autonomous Workflows", { exact: true })).toBeVisible()
    await expect(page.getByText("Platform Apps", { exact: true })).toBeVisible()
    await expect(page.getByText("Web Portal", { exact: true })).toBeVisible()
    await expect(page.getByText("Operational", { exact: true })).toBeVisible()
    await expect(page.getByText(/from intent to execution/i).first()).toBeVisible()
    await expect(page.getByText("State Your Objective")).toBeVisible()
    await expect(page.getByText("AI Executes the Workflow")).toBeVisible()
    await expect(page.getByText("Deliver the Result")).toBeVisible()
    await expect(page.getByText(/built for transport companies/i)).toBeVisible()
    await expect(page.getByText(/frequently asked questions/i).first()).toBeVisible()
  })

  test("/features has comparison table and FAQ", async ({ page }) => {
    await page.goto("/features")
    await expect(page.getByRole("heading", { name: /autonomous logistics workflows/i })).toBeVisible()
    await expect(page.getByText(/ai route optimization/i)).toBeVisible()
    await expect(page.getByText(/live fleet visibility/i)).toBeVisible()
    await expect(page.getByText(/autonomous workflow faq/i)).toBeVisible()
  })

  test("/pricing has comparison table, FAQ and enterprise", async ({ page }) => {
    await page.goto("/pricing")
    await expect(page.getByRole("heading", { name: /simple, transparent pricing/i })).toBeVisible()
    await expect(page.getByText(/coming soon/i)).toBeVisible()
    await expect(page.getByText(/pricing faq/i)).toBeVisible()
    await expect(page.getByRole("link", { name: /sign up for early access/i })).toBeVisible()
  })

  test("/download has installation, release history, checksums, toolkit", async ({ page }) => {
    await page.goto("/download")
    await expect(page.getByRole("heading", { name: /download operion desktop/i })).toBeVisible()
    // "Installation Instructions" is a substring of "Uninstallation Instructions" — anchor it.
    await expect(page.getByRole("heading", { name: /^installation instructions$/i })).toBeVisible()
    // The release-history placeholder paragraph also starts with "Release history" — scope to the heading.
    await expect(page.getByRole("heading", { name: /^release history$/i })).toBeVisible()
    await expect(page.getByText(/operion developer toolkit/i)).toBeVisible()
  })

  test("/about has tech stack, timeline, security philosophy", async ({ page }) => {
    await page.goto("/about")
    await expect(page.getByRole("heading", { name: /about operion/i })).toBeVisible()
    await expect(page.getByText(/technology stack/i)).toBeVisible()
    await expect(page.getByText(/python & pyside6/i)).toBeVisible()
    await expect(page.getByText(/fastapi backend/i)).toBeVisible()
    await expect(page.getByText(/company timeline/i)).toBeVisible()
    await expect(page.getByText(/development philosophy/i)).toBeVisible()
  })

  test("/mission has vision, values, commitments", async ({ page }) => {
    await page.goto("/mission")
    await expect(page.getByRole("heading", { name: /our mission/i })).toBeVisible()
    await expect(page.getByText(/our vision/i)).toBeVisible()
    await expect(page.getByText(/what we believe/i)).toBeVisible()
    await expect(page.getByText(/our values/i).first()).toBeVisible()
    await expect(page.getByText(/our commitments/i)).toBeVisible()
    await expect(page.getByText(/to our customers/i)).toBeVisible()
  })

  test("/faq has category tabs and search", async ({ page }) => {
    await page.goto("/faq")
    await expect(page.getByRole("heading", { name: /frequently asked questions/i })).toBeVisible()
    await expect(page.getByPlaceholder(/search frequently asked questions/i)).toBeVisible()
    await expect(page.getByRole("tab", { name: /general/i })).toBeVisible()
    await expect(page.getByRole("tab", { name: /billing/i })).toBeVisible()
    await expect(page.getByRole("tab", { name: /technical/i })).toBeVisible()
    await expect(page.getByRole("tab", { name: /security/i })).toBeVisible()
  })

  test("/contact has contact methods and response times", async ({ page }) => {
    await page.goto("/contact")
    await expect(page.getByRole("heading", { name: /get in touch/i })).toBeVisible()
    await expect(page.getByLabel("Name")).toBeVisible()
    await expect(page.getByLabel("Email")).toBeVisible()
    await expect(page.getByLabel("Subject")).toBeVisible()
    await expect(page.getByLabel("Message")).toBeVisible()
    await expect(page.getByText(/contact methods/i)).toBeVisible()
  })
})
