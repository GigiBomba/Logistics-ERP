import { test, expect } from "@playwright/test"
import { stabilizeHydration, waitForHydration } from "./helpers"

test.describe("Authentication Flow", () => {
  test.beforeEach(async ({ page }) => {
    stabilizeHydration(page)
  })

  test("login page renders correctly", async ({ page }) => {
    await page.goto("/login")
    await expect(page.getByText("Welcome back")).toBeVisible()
    await expect(page.getByLabel("Email", { exact: true })).toBeVisible()
    await expect(page.getByLabel(/^password$/i)).toBeVisible()
    await expect(page.getByRole("button", { name: /sign in/i })).toBeVisible()
    await expect(page.getByText(/don't have an account/i)).toBeVisible()
  })

  test("login has link to register", async ({ page }) => {
    await page.goto("/login")
    await page.getByText(/sign up/i).click()
    await expect(page).toHaveURL(/\/register/)
  })

  test("login has link to forgot password", async ({ page }) => {
    await page.goto("/login")
    await page.getByText(/forgot password/i).click()
    await expect(page).toHaveURL(/\/forgot-password/)
  })

  test("register page renders correctly", async ({ page }) => {
    await page.goto("/register")
    await expect(page.getByRole("heading", { name: /create account/i })).toBeVisible()
    await expect(page.getByLabel(/full name/i)).toBeVisible()
    await expect(page.getByLabel("Email", { exact: true })).toBeVisible()
    await expect(page.getByLabel(/^password$/i)).toBeVisible()
    await expect(page.getByLabel(/confirm password/i)).toBeVisible()
    await expect(page.getByRole("button", { name: /^create$/i })).toBeVisible()
  })

  test("register links to login", async ({ page }) => {
    await page.goto("/register")
    await page.getByText(/sign in/i).click()
    await expect(page).toHaveURL(/\/login/)
  })

  test("forgot password page renders", async ({ page }) => {
    await page.goto("/forgot-password")
    await expect(page.getByRole("heading", { name: /reset password/i })).toBeVisible()
    await expect(page.getByLabel("Email", { exact: true })).toBeVisible()
    await expect(page.getByRole("button", { name: /send reset link/i })).toBeVisible()
  })

  test("reset password shows invalid for missing token", async ({ page }) => {
    await page.goto("/reset-password")
    await expect(page.getByText("Invalid Reset Link")).toBeVisible()
  })

  test("verify email page shows confirmation", async ({ page }) => {
    await page.goto("/verify-email")
    await expect(page.getByText("Check your email")).toBeVisible()
    await expect(page.getByRole("link", { name: /go to sign in/i })).toBeVisible()
  })

  test("login form shows validation errors", async ({ page }) => {
    await page.goto("/login")
    await page.getByRole("button", { name: /sign in/i }).click()
    await expect(page.getByText("Please enter a valid email")).toBeVisible()
    await expect(page.getByText("Password is required")).toBeVisible()
  })

  test("register form shows validation errors", async ({ page }) => {
    await page.goto("/register")
    await waitForHydration(page)
    // The terms checkbox is `required` (native HTML5 validation), so submission
    // is blocked until it is checked — then zod validation runs on the empty form.
    await page.check("#termsAccepted")
    await page.getByRole("button", { name: /^create$/i }).click()
    await expect(page.getByText(/name must be at least 2 characters/i)).toBeVisible()
    await expect(page.getByText("Please enter a valid email")).toBeVisible()
  })
})
