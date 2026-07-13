import { test, expect } from "@playwright/test"

test.describe("Authentication Flow", () => {
  test("login page renders correctly", async ({ page }) => {
    await page.goto("/login")
    await expect(page.getByText("Welcome back")).toBeVisible()
    await expect(page.getByLabelText("Email")).toBeVisible()
    await expect(page.getByLabelText("Password")).toBeVisible()
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
    await expect(page.getByText("Create your account")).toBeVisible()
    await expect(page.getByLabelText(/full name/i)).toBeVisible()
    await expect(page.getByLabelText("Email")).toBeVisible()
    await expect(page.getByLabelText(/^password$/i)).toBeVisible()
    await expect(page.getByLabelText(/confirm password/i)).toBeVisible()
    await expect(page.getByRole("button", { name: /create account/i })).toBeVisible()
  })

  test("register links to login", async ({ page }) => {
    await page.goto("/register")
    await page.getByText(/sign in/i).click()
    await expect(page).toHaveURL(/\/login/)
  })

  test("forgot password page renders", async ({ page }) => {
    await page.goto("/forgot-password")
    await expect(page.getByText("Reset your password")).toBeVisible()
    await expect(page.getByLabelText("Email")).toBeVisible()
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
    await page.getByRole("button", { name: /create account/i }).click()
    await expect(page.getByText(/name must be at least 2 characters/i)).toBeVisible()
    await expect(page.getByText("Please enter a valid email")).toBeVisible()
  })
})
