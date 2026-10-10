import { test, expect } from "@playwright/test"
import { stabilizeHydration, waitForHydration, waitForFormReady } from "./helpers"

// vike dev compiles routes on demand (~7s first hit) while the default expect
// timeout is 5s — every test waits for hydration after goto before asserting.
test.describe("Authentication Flow", () => {
  test.beforeEach(async ({ page }) => {
    stabilizeHydration(page)
  })

  test("login page renders correctly", async ({ page }) => {
    await page.goto("/login")
    await waitForHydration(page)
    await expect(page.getByText("Welcome back")).toBeVisible()
    await expect(page.getByLabel("Email", { exact: true })).toBeVisible()
    await expect(page.getByLabel(/^password$/i)).toBeVisible()
    await expect(page.getByRole("button", { name: /sign in/i })).toBeVisible()
    await expect(page.getByText(/don't have an account/i)).toBeVisible()
  })

  test("login has link to register", async ({ page }) => {
    await page.goto("/login")
    await waitForHydration(page)
    await page.getByText(/sign up/i).click()
    await expect(page).toHaveURL(/\/register/)
  })

  test("login has link to forgot password", async ({ page }) => {
    await page.goto("/login")
    await waitForHydration(page)
    await page.getByText(/forgot password/i).click()
    await expect(page).toHaveURL(/\/forgot-password/)
  })

  test("register page renders correctly", async ({ page }) => {
    await page.goto("/register")
    await waitForHydration(page)
    await expect(page.getByRole("heading", { name: /create account/i })).toBeVisible()
    await expect(page.getByLabel(/full name/i)).toBeVisible()
    await expect(page.getByLabel("Email", { exact: true })).toBeVisible()
    await expect(page.getByLabel(/^password$/i)).toBeVisible()
    await expect(page.getByLabel(/confirm password/i)).toBeVisible()
    await expect(page.getByRole("button", { name: /^create$/i })).toBeVisible()
  })

  test("register links to login", async ({ page }) => {
    await page.goto("/register")
    await waitForHydration(page)
    // "Sign in" exists in the header banner and the register card footer —
    // scope to the last (in-page) link to avoid a strict-mode violation.
    await page.getByRole("link", { name: "Sign in" }).last().click()
    // The SPA transition compiles the /login route on demand (`vike dev`);
    // under parallel cross-browser load the first transition can exceed the
    // 10s default expect timeout (firefox flake). Give it cold-route headroom.
    await expect(page).toHaveURL(/\/login/, { timeout: 20_000 })
  })

  test("forgot password page renders", async ({ page }) => {
    await page.goto("/forgot-password")
    await waitForHydration(page)
    await expect(page.getByRole("heading", { name: /reset password/i })).toBeVisible()
    await expect(page.getByLabel("Email", { exact: true })).toBeVisible()
    await expect(page.getByRole("button", { name: /send reset link/i })).toBeVisible()
  })

  test("reset password shows invalid for missing token", async ({ page }) => {
    await page.goto("/reset-password")
    await waitForHydration(page)
    await expect(page.getByText("Invalid Reset Link")).toBeVisible()
  })

  test("verify email page shows confirmation", async ({ page }) => {
    await page.goto("/verify-email")
    await waitForHydration(page)
    // Scope to the heading: `getByText("Check your email")` is a substring
    // match and once the client-side <title> updates to
    // "Check your email — Operion ERP" it resolves to 2 elements → strict-mode
    // violation (race between title update and the assertion).
    await expect(page.getByRole("heading", { name: "Check your email" })).toBeVisible()
    await expect(page.getByRole("link", { name: /go to sign in/i })).toBeVisible()
  })

  test("login form shows validation errors", async ({ page }) => {
    await page.goto("/login")
    // waitForHydration alone can false-positive on shell elements before the
    // route chunk hydrates the form (native-submit race) — waitForFormReady
    // additionally gates on the form's own submit button.
    await waitForFormReady(page)
    await page.getByRole("button", { name: /sign in/i }).click()
    await expect(page.getByText("Please enter a valid email")).toBeVisible()
    await expect(page.getByText("Password is required")).toBeVisible()
  })

  test("register form shows validation errors", async ({ page }) => {
    await page.goto("/register")
    // Form-specific gate: waitForHydration can false-positive on shell
    // elements before the register route chunk hydrates (baseline showed the
    // browser falling back to a native form GET).
    await waitForFormReady(page)
    // The terms checkbox is `required` (native HTML5 validation), so submission
    // is blocked until it is checked — then zod validation runs on the empty form.
    // Toggle it via keyboard: Playwright's scrollIntoView aligns the control to
    // the viewport top where the sticky header intercepts the pointer click
    // (firefox "Clicking the checkbox did not change its state").
    await page.locator("#termsAccepted").focus()
    await page.keyboard.press("Space")
    await expect(page.locator("#termsAccepted")).toBeChecked()
    await page.getByRole("button", { name: /^create$/i }).click()
    await expect(page.getByText(/name must be at least 2 characters/i)).toBeVisible()
    await expect(page.getByText("Please enter a valid email")).toBeVisible()
  })
})
