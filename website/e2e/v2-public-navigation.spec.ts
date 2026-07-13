import { test, expect } from "@playwright/test"

test.describe("V2 Public Navigation", () => {
  /* ─── Blog Section ─────────────────────────────────────────────── */

  test("/blog page loads", async ({ page }) => {
    await page.goto("/blog")
    await expect(page.getByRole("heading", { name: /blog/i })).toBeVisible()
    await expect(page.getByRole("button", { name: /all/i })).toBeVisible()
    await expect(page.getByPlaceholder(/search articles/i)).toBeVisible()
    await expect(page.getByText(/\d+ articles?/i)).toBeVisible()
  })

  test("/blog/:slug loads blog article", async ({ page }) => {
    await page.goto("/blog/getting-started-with-operion")
    await expect(page.getByRole("heading", { name: /getting started with operion/i })).toBeVisible()
    await expect(page.getByText(/min read/i)).toBeVisible()
    await expect(page.getByText(/onboarding/i)).toBeVisible()
    await expect(page.getByText(/fleet-setup/i)).toBeVisible()
    await expect(page.getByText(/dispatch/i)).toBeVisible()
    await expect(page.getByText(/back to blog/i)).toBeVisible()
  })

  test("/blog/category/:category filters by category", async ({ page }) => {
    await page.goto("/blog/category/engineering")
    await expect(page.getByRole("heading", { name: /engineering/i })).toBeVisible()
    await expect(page.getByText(/all articles in the engineering/i)).toBeVisible()
  })

  test("/blog/author/:id renders author page", async ({ page }) => {
    await page.goto("/blog/author/sarah-chen")
    await expect(page.getByRole("heading", { name: /sarah chen/i })).toBeVisible()
    await expect(page.getByText(/engineering lead/i)).toBeVisible()
    await expect(page.getByText(/\d+ articles?/i)).toBeVisible()
  })

  /* ─── Changelog, Roadmap, Status ──────────────────────────────── */

  test("/changelog page loads", async ({ page }) => {
    await page.goto("/changelog")
    await expect(page.getByRole("heading", { name: /changelog/i })).toBeVisible()
    await expect(page.getByText(/1\.0\.0/i)).toBeVisible()
    await expect(page.getByText(/0\.9\.0/i)).toBeVisible()
    await expect(page.getByRole("heading", { name: /download the latest release/i })).toBeVisible()
    await expect(page.getByRole("link", { name: /go to downloads/i })).toBeVisible()
  })

  test("/roadmap page loads", async ({ page }) => {
    await page.goto("/roadmap")
    await expect(page.getByRole("heading", { name: /roadmap/i })).toBeVisible()
    await expect(page.getByRole("button", { name: /all/i })).toBeVisible()
    await expect(page.getByRole("button", { name: /planned/i })).toBeVisible()
    await expect(page.getByRole("button", { name: /in progress/i })).toBeVisible()
    await expect(page.getByRole("button", { name: /completed/i })).toBeVisible()
    await expect(page.getByText(/ai-powered route optimization/i)).toBeVisible()
  })

  test("/status page loads", async ({ page }) => {
    await page.goto("/status")
    await expect(page.getByRole("heading", { name: /system status/i })).toBeVisible()
    await expect(page.getByText(/all systems operational/i)).toBeVisible()
    await expect(page.getByText(/core services/i)).toBeVisible()
    await expect(page.getByText(/platform/i)).toBeVisible()
    await expect(page.getByText(/communication/i)).toBeVisible()
    await expect(page.getByText(/operational/i).first()).toBeVisible()
  })

  /* ─── Security & Developer ────────────────────────────────────── */

  test("/security page loads", async ({ page }) => {
    await page.goto("/security")
    await expect(page.getByRole("heading", { name: /security at operion/i })).toBeVisible()
    await expect(page.getByText(/data encryption/i)).toBeVisible()
    await expect(page.getByText(/access control/i)).toBeVisible()
    await expect(page.getByText(/responsible disclosure/i)).toBeVisible()
    await expect(page.getByText(/security faq/i)).toBeVisible()
    await expect(page.getByText(/security@operion\.com/i)).toBeVisible()
  })

  test("/developers page loads", async ({ page }) => {
    await page.goto("/developers")
    await expect(page.getByRole("heading", { name: /developer resources/i })).toBeVisible()
    await expect(page.getByText(/toolkit/i)).toBeVisible()
    await expect(page.getByText(/api reference/i)).toBeVisible()
    await expect(page.getByText(/quick start/i)).toBeVisible()
    await expect(page.getByText(/get your api key/i)).toBeVisible()
  })

  test("/developers/toolkit page loads", async ({ page }) => {
    await page.goto("/developers/toolkit")
    await expect(page.getByRole("heading", { name: /operion toolkit/i })).toBeVisible()
    await expect(page.getByRole("button", { name: /download toolkit/i })).toBeVisible()
    await expect(page.getByText(/system requirements/i)).toBeVisible()
    await expect(page.getByText(/operating system/i)).toBeVisible()
    await expect(page.getByText(/installation/i)).toBeVisible()
    await expect(page.getByText(/download the installer/i)).toBeVisible()
  })

  /* ─── Tutorials ────────────────────────────────────────────────── */

  test("/tutorials page loads", async ({ page }) => {
    await page.goto("/tutorials")
    await expect(page.getByRole("heading", { name: /tutorials/i })).toBeVisible()
    await expect(page.getByPlaceholder(/search tutorials/i)).toBeVisible()
    await expect(page.getByRole("button", { name: /all/i })).toBeVisible()
    await expect(page.getByRole("button", { name: /beginner/i })).toBeVisible()
    await expect(page.getByRole("button", { name: /intermediate/i })).toBeVisible()
    await expect(page.getByText(/installing operion erp/i)).toBeVisible()
    await expect(page.getByText(/min read/i).first()).toBeVisible()
  })

  test("/tutorials/:slug loads tutorial detail", async ({ page }) => {
    await page.goto("/tutorials/your-first-route-plan")
    await expect(page.getByRole("heading", { name: /your first route plan/i })).toBeVisible()
    await expect(page.getByText(/beginner/i)).toBeVisible()
    await expect(page.getByText(/min read/i)).toBeVisible()
    await expect(page.getByText(/step 1: prepare your data/i)).toBeVisible()
    await expect(page.getByText(/back to tutorials/i)).toBeVisible()
  })

  /* ─── Enhanced Pages (V2 Content) ─────────────────────────────── */

  test("/ home page has V2 sections", async ({ page }) => {
    await page.goto("/")
    await expect(page.getByText(/10,000\+/i)).toBeVisible()
    await expect(page.getByText(/500\+/i)).toBeVisible()
    await expect(page.getByText(/99\.9%/i)).toBeVisible()
    await expect(page.getByText(/how it works/i)).toBeVisible()
    await expect(page.getByText(/plan/i)).toBeVisible()
    await expect(page.getByText(/dispatch/i)).toBeVisible()
    await expect(page.getByText(/optimize/i)).toBeVisible()
    await expect(page.getByText(/trusted by industry leaders/i)).toBeVisible()
    await expect(page.getByText(/from the blog/i)).toBeVisible()
    await expect(page.getByText(/what'?s next/i)).toBeVisible()
    await expect(page.getByText(/frequently asked questions/i)).toBeVisible()
  })

  test("/features has comparison table and FAQ", async ({ page }) => {
    await page.goto("/features")
    await expect(page.getByRole("heading", { name: /powerful features/i })).toBeVisible()
    await expect(page.getByText(/how operion compares/i)).toBeVisible()
    await expect(page.getByText(/intelligent route optimization/i)).toBeVisible()
    await expect(page.getByText(/real-time gps tracking/i)).toBeVisible()
    await expect(page.getByText(/feature faq/i)).toBeVisible()
  })

  test("/pricing has comparison table, FAQ and enterprise", async ({ page }) => {
    await page.goto("/pricing")
    await expect(page.getByRole("heading", { name: /simple, transparent pricing/i })).toBeVisible()
    await expect(page.getByText(/plan comparison/i)).toBeVisible()
    await expect(page.getByText(/pricing faq/i)).toBeVisible()
    await expect(page.getByText(/vehicles included/i)).toBeVisible()
    await expect(page.getByText(/enterprise/i)).toBeVisible()
    await expect(page.getByRole("button", { name: /contact sales/i })).toBeVisible()
  })

  test("/download has installation, release history, checksums, toolkit", async ({ page }) => {
    await page.goto("/download")
    await expect(page.getByRole("heading", { name: /download operion desktop/i })).toBeVisible()
    await expect(page.getByText(/installation instructions/i)).toBeVisible()
    await expect(page.getByText(/release history/i)).toBeVisible()
    await expect(page.getByText(/file checksums/i)).toBeVisible()
    await expect(page.getByText(/sha-256/i)).toBeVisible()
    await expect(page.getByText(/operion developer toolkit/i)).toBeVisible()
  })

  test("/about has tech stack, timeline, security philosophy", async ({ page }) => {
    await page.goto("/about")
    await expect(page.getByRole("heading", { name: /about operion/i })).toBeVisible()
    await expect(page.getByText(/technology stack/i)).toBeVisible()
    await expect(page.getByText(/rust & typescript/i)).toBeVisible()
    await expect(page.getByText(/company timeline/i)).toBeVisible()
    await expect(page.getByText(/security philosophy/i)).toBeVisible()
  })

  test("/mission has vision, values, commitments", async ({ page }) => {
    await page.goto("/mission")
    await expect(page.getByRole("heading", { name: /our mission/i })).toBeVisible()
    await expect(page.getByText(/our vision/i)).toBeVisible()
    await expect(page.getByText(/what we believe/i)).toBeVisible()
    await expect(page.getByText(/core values/i)).toBeVisible()
    await expect(page.getByText(/our commitments/i)).toBeVisible()
    await expect(page.getByText(/commitment to customers/i)).toBeVisible()
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
    await expect(page.getByLabelText("Name")).toBeVisible()
    await expect(page.getByLabelText("Email")).toBeVisible()
    await expect(page.getByLabelText("Subject")).toBeVisible()
    await expect(page.getByLabelText("Message")).toBeVisible()
    await expect(page.getByText(/contact methods/i)).toBeVisible()
    await expect(page.getByText(/response time expectations/i)).toBeVisible()
    await expect(page.getByText(/within 24 hours/i)).toBeVisible()
    await expect(page.getByText(/within 2 hours/i)).toBeVisible()
  })
})
