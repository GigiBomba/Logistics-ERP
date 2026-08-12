import { test, expect } from "@playwright/test"
import { stabilizeHydration, waitForHydration } from "./helpers"

test.describe("Public Navigation", () => {
  test("home page loads with all sections", async ({ page }) => {
    await page.goto("/")
    await expect(page).toHaveTitle(/Operion/)
    await expect(page.getByRole("heading", { name: /The Complete Logistics Operating System/i })).toBeVisible()
    await expect(page.getByRole("link", { name: /see the ai in action/i })).toBeVisible()
    await expect(page.getByRole("link", { name: /watch the workflow demo/i })).toBeVisible()
    await expect(page.getByText(/smart route planning/i)).toBeVisible()
    await expect(page.getByText(/built for transport companies/i)).toBeVisible()
    await expect(page.getByRole("link", { name: /read our story/i })).toBeVisible()
    await expect(page.getByText(/ready to see autonomous logistics/i)).toBeVisible()
  })

  test("navbar navigates between pages", async ({ page }) => {
    await page.goto("/")
    await page.getByRole("link", { name: "Product", exact: true }).click()
    await expect(page).toHaveURL(/\/features/)
    await expect(page.getByRole("heading", { name: /autonomous logistics workflows/i })).toBeVisible()
  })

  test("features page has feature sections", async ({ page }) => {
    await page.goto("/features")
    await expect(page.getByRole("heading", { name: /intelligent route execution/i })).toBeVisible()
    await expect(page.getByRole("heading", { name: /autonomous fleet operations/i })).toBeVisible()
    await expect(page.getByRole("heading", { name: /one-instruction dispatching/i })).toBeVisible()
    await expect(page.getByRole("heading", { name: /automated document workflows/i })).toBeVisible()
  })

  test("pricing page shows coming soon CTA and FAQ", async ({ page }) => {
    await page.goto("/pricing")
    await expect(page.getByText("Coming Soon")).toBeVisible()
    await expect(page.getByText(/Pricing FAQ/)).toBeVisible()
    await expect(page.getByRole("link", { name: /sign up for early access/i })).toBeVisible()
  })

  test("pricing page header and early-access card render", async ({ page }) => {
    // The plan-card monthly/yearly toggle was removed in the S-grade redesign —
    // pricing is now a single "Coming Soon" early-access CTA card. Assert the
    // current card + FAQ render (same "pricing page loads" intent).
    await page.goto("/pricing")
    await expect(page.getByText("Coming Soon")).toBeVisible()
    await expect(page.getByRole("heading", { name: /simple, transparent pricing/i })).toBeVisible()
    await expect(page.getByText(/Pricing FAQ/)).toBeVisible()
  })

  test("download page has download card and requirements", async ({ page }) => {
    await page.goto("/download")
    await expect(page.getByText(/download operion desktop/i)).toBeVisible()
    await expect(page.getByText(/system requirements/i)).toBeVisible()
    await expect(page.getByRole("link", { name: /download for (android|ios)/i }).first()).toBeVisible()
  })

  test("about page loads", async ({ page }) => {
    await page.goto("/about")
    await expect(page.getByRole("heading", { name: /about operion/i })).toBeVisible()
    await expect(page.getByText(/our story/i)).toBeVisible()
    await expect(page.getByText(/our values/i).first()).toBeVisible()
  })

  test("mission page loads", async ({ page }) => {
    await page.goto("/mission")
    await expect(page.getByRole("heading", { name: /our mission/i })).toBeVisible()
    await expect(page.getByText(/what we believe/i)).toBeVisible()
  })

  test("FAQ page accordion works", async ({ page }) => {
    await page.goto("/faq")
    await expect(page.getByText(/what is operion/i)).toBeVisible()
    await page.getByText(/what is operion/i).click()
    await expect(page.getByText(/operion is an ai logistics operating system/i)).toBeVisible()
  })

  test("contact page has form", async ({ page }) => {
    await page.goto("/contact")
    await expect(page.getByRole("heading", { name: /get in touch/i })).toBeVisible()
    await expect(page.getByLabel("Name")).toBeVisible()
    await expect(page.getByLabel("Email")).toBeVisible()
    await expect(page.getByLabel("Subject")).toBeVisible()
    await expect(page.getByLabel("Message")).toBeVisible()
    await expect(page.getByRole("button", { name: /send message/i })).toBeVisible()
  })

  test("privacy page has sections", async ({ page }) => {
    await page.goto("/privacy")
    await expect(page.getByText(/table of contents/i)).toBeVisible()
    await expect(page.getByRole("heading", { name: /information we collect/i })).toBeVisible()
  })

  test("terms page has sections", async ({ page }) => {
    await page.goto("/terms")
    await expect(page.getByText(/table of contents/i)).toBeVisible()
    await expect(page.getByRole("heading", { name: /acceptance of terms/i })).toBeVisible()
  })

  test("404 page shows for unknown routes", async ({ page }) => {
    await page.goto("/nonexistent-page")
    await expect(page.getByText("404")).toBeVisible()
    await expect(page.getByRole("heading", { name: /page not found/i })).toBeVisible()
    await expect(page.getByRole("link", { name: /go home/i })).toBeVisible()
    await expect(page.getByRole("main").getByRole("link", { name: /contact/i })).toBeVisible()
  })

  test("footer links are present", async ({ page }) => {
    stabilizeHydration(page)
    await page.goto("/")
    await waitForHydration(page)
    const footer = page.locator("footer")
    await expect(footer.getByText("Features")).toBeVisible()
    // "Privacy"/"Terms" render both in the Legal column and the bottom bar — use .first().
    await expect(footer.getByText("Privacy").first()).toBeVisible()
    await expect(footer.getByText("Terms").first()).toBeVisible()
  })
})
