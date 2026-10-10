import { test, expect } from "@playwright/test"
import { waitForHydration, waitForFormReady } from "./helpers"

// Every test waits for hydration after goto: vike dev compiles routes on
// demand (~7s first hit) while the default expect timeout is 5s.

test.describe("Full Auth Flow", () => {
  test("register page renders with all form fields", async ({ page }) => {
    await page.goto("/register")
    await waitForHydration(page)
    await expect(page).toHaveTitle(/Create Account/)
    await expect(page.getByRole("heading", { name: "Create Account" })).toBeVisible()
    await expect(page.getByLabel(/full name/i)).toBeVisible()
    await expect(page.getByLabel("Email")).toBeVisible()
    await expect(page.getByLabel(/^password$/i)).toBeVisible()
    await expect(page.getByLabel(/confirm password/i)).toBeVisible()
    await expect(page.getByRole("button", { name: /^create$/i })).toBeVisible()
  })

  test("register form validates required fields", async ({ page }) => {
    await page.goto("/register")
    await waitForFormReady(page)
    // The terms checkbox is `required` (native HTML5 validation), so the
    // browser blocks submission until it is checked — then zod validation
    // runs on the otherwise-empty form.
    await page.check("#termsAccepted")
    await page.getByRole("button", { name: /^create$/i }).click()
    await expect(page.getByText(/name must be at least 2 characters/i)).toBeVisible()
    await expect(page.getByText("Please enter a valid email")).toBeVisible()
  })

  test("register links to login page", async ({ page }) => {
    await page.goto("/register")
    await waitForHydration(page)
    // "Sign in" exists in both the header banner and the register card footer —
    // scope to the last (in-page) link to avoid a strict-mode violation.
    await page.getByRole("link", { name: "Sign in" }).last().click()
    await expect(page).toHaveURL(/\/login/)
  })

  test("login page renders with all form fields", async ({ page }) => {
    await page.goto("/login")
    await waitForHydration(page)
    await expect(page).toHaveTitle(/Sign in/)
    await expect(page.getByText("Welcome back")).toBeVisible()
    await expect(page.getByLabel("Email")).toBeVisible()
    // Anchor the field's own label — "Show password" (the visibility toggle's
    // aria-label) also contains "Password" and would break strict mode.
    await expect(page.getByLabel(/^password$/i)).toBeVisible()
    await expect(page.getByRole("button", { name: /sign in/i })).toBeVisible()
  })

  test("login form validates required fields", async ({ page }) => {
    await page.goto("/login")
    await waitForFormReady(page)
    await page.getByRole("button", { name: /sign in/i }).click()
    await expect(page.getByText("Please enter a valid email")).toBeVisible()
    await expect(page.getByText("Password is required")).toBeVisible()
  })

  test("login has link to forgot password", async ({ page }) => {
    await page.goto("/login")
    await waitForHydration(page)
    await page.getByText(/forgot password/i).click()
    await expect(page).toHaveURL(/\/forgot-password/)
  })

  test("login has link to register", async ({ page }) => {
    await page.goto("/login")
    await waitForHydration(page)
    await page.getByText(/sign up/i).click()
    await expect(page).toHaveURL(/\/register/)
  })

  test("forgot password page renders", async ({ page }) => {
    await page.goto("/forgot-password")
    await waitForHydration(page)
    await expect(page).toHaveTitle(/Reset Password/)
    await expect(page.getByRole("heading", { name: "Reset Password" })).toBeVisible()
    await expect(page.getByLabel("Email")).toBeVisible()
    await expect(page.getByRole("button", { name: /send reset link/i })).toBeVisible()
  })

  test("forgot password form validates email", async ({ page }) => {
    await page.goto("/forgot-password")
    await waitForFormReady(page)
    await page.getByRole("button", { name: /send reset link/i }).click()
    await expect(page.getByText("Please enter a valid email")).toBeVisible()
  })

  test("forgot password links back to login", async ({ page }) => {
    await page.goto("/forgot-password")
    await waitForHydration(page)
    // The card footer "Remember your password? Sign in" is plain text, not a
    // link — use the header Sign-in link (the footer link fix is app-side).
    await page.getByRole("banner").getByRole("link", { name: "Sign in" }).click()
    await expect(page).toHaveURL(/\/login/)
  })

  test("reset password page shows invalid for missing token", async ({ page }) => {
    await page.goto("/reset-password")
    await waitForHydration(page)
    // Without ?token= the page title is "Reset Password — Operion ERP" (the
    // "Set New Password" title only renders in the token branch) — assert the
    // branch-specific heading instead.
    await expect(page.getByRole("heading", { name: "Invalid Reset Link" })).toBeVisible()
  })

  test("verify email page shows confirmation", async ({ page }) => {
    await page.goto("/verify-email")
    await waitForHydration(page)
    await expect(page).toHaveTitle(/Check your email/)
    await expect(page.getByText("Check your email")).toBeVisible()
    await expect(page.getByRole("link", { name: /go to sign in/i })).toBeVisible()
  })

  test("verify email page links to login", async ({ page }) => {
    await page.goto("/verify-email")
    await waitForHydration(page)
    await page.getByRole("link", { name: /go to sign in/i }).click()
    await expect(page).toHaveURL(/\/login/)
  })

  test("full navigation flow: register → login → forgot → reset → verify", async ({ page }) => {
    // Start at register
    await page.goto("/register")
    await waitForHydration(page)
    await expect(page).toHaveURL(/\/register/)

    // Navigate to login — "Sign in" matches header + card footer, scope to the
    // in-page link.
    await page.getByRole("link", { name: "Sign in" }).last().click()
    await expect(page).toHaveURL(/\/login/)

    // Navigate to forgot password
    await page.getByText(/forgot password/i).click()
    await expect(page).toHaveURL(/\/forgot-password/)

    // Back to login — the footer text is not a link; use the header Sign-in link.
    await page.getByRole("banner").getByRole("link", { name: "Sign in" }).click()
    await expect(page).toHaveURL(/\/login/)

    // Sign up link back to register
    await page.getByText(/sign up/i).click()
    await expect(page).toHaveURL(/\/register/)
  })
})
