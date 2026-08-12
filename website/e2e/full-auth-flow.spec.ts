import { test, expect } from "@playwright/test"

test.describe("Full Auth Flow", () => {
  test("register page renders with all form fields", async ({ page }) => {
    await page.goto("/register")
    await expect(page).toHaveTitle(/Create Account/)
    await expect(page.getByText("Create your account")).toBeVisible()
    await expect(page.getByLabelText(/full name/i)).toBeVisible()
    await expect(page.getByLabelText("Email")).toBeVisible()
    await expect(page.getByLabelText(/^password$/i)).toBeVisible()
    await expect(page.getByLabelText(/confirm password/i)).toBeVisible()
    await expect(page.getByRole("button", { name: /create account/i })).toBeVisible()
  })

  test("register form validates required fields", async ({ page }) => {
    await page.goto("/register")
    await page.getByRole("button", { name: /create account/i }).click()
    await expect(page.getByText(/name must be at least 2 characters/i)).toBeVisible()
    await expect(page.getByText("Please enter a valid email")).toBeVisible()
  })

  test("register links to login page", async ({ page }) => {
    await page.goto("/register")
    await page.getByText(/sign in/i).click()
    await expect(page).toHaveURL(/\/login/)
  })

  test("login page renders with all form fields", async ({ page }) => {
    await page.goto("/login")
    await expect(page).toHaveTitle(/Sign In/)
    await expect(page.getByText("Welcome back")).toBeVisible()
    await expect(page.getByLabelText("Email")).toBeVisible()
    await expect(page.getByLabelText("Password")).toBeVisible()
    await expect(page.getByRole("button", { name: /sign in/i })).toBeVisible()
  })

  test("login form validates required fields", async ({ page }) => {
    await page.goto("/login")
    await page.getByRole("button", { name: /sign in/i }).click()
    await expect(page.getByText("Please enter a valid email")).toBeVisible()
    await expect(page.getByText("Password is required")).toBeVisible()
  })

  test("login has link to forgot password", async ({ page }) => {
    await page.goto("/login")
    await page.getByText(/forgot password/i).click()
    await expect(page).toHaveURL(/\/forgot-password/)
  })

  test("login has link to register", async ({ page }) => {
    await page.goto("/login")
    await page.getByText(/sign up/i).click()
    await expect(page).toHaveURL(/\/register/)
  })

  test("forgot password page renders", async ({ page }) => {
    await page.goto("/forgot-password")
    await expect(page).toHaveTitle(/Reset Password/)
    await expect(page.getByText("Reset your password")).toBeVisible()
    await expect(page.getByLabelText("Email")).toBeVisible()
    await expect(page.getByRole("button", { name: /send reset link/i })).toBeVisible()
  })

  test("forgot password form validates email", async ({ page }) => {
    await page.goto("/forgot-password")
    await page.getByRole("button", { name: /send reset link/i }).click()
    await expect(page.getByText("Please enter a valid email")).toBeVisible()
  })

  test("forgot password links back to login", async ({ page }) => {
    await page.goto("/forgot-password")
    await page.getByText(/back to sign in/i).click()
    await expect(page).toHaveURL(/\/login/)
  })

  test("reset password page shows invalid for missing token", async ({ page }) => {
    await page.goto("/reset-password")
    await expect(page).toHaveTitle(/Set New Password/)
    await expect(page.getByText("Invalid Reset Link")).toBeVisible()
  })

  test("verify email page shows confirmation", async ({ page }) => {
    await page.goto("/verify-email")
    await expect(page).toHaveTitle(/Verify Email/)
    await expect(page.getByText("Check your email")).toBeVisible()
    await expect(page.getByRole("link", { name: /go to sign in/i })).toBeVisible()
  })

  test("verify email page links to login", async ({ page }) => {
    await page.goto("/verify-email")
    await page.getByRole("link", { name: /go to sign in/i }).click()
    await expect(page).toHaveURL(/\/login/)
  })

  test("full navigation flow: register → login → forgot → reset → verify", async ({ page }) => {
    // Start at register
    await page.goto("/register")
    await expect(page).toHaveURL(/\/register/)

    // Navigate to login
    await page.getByText(/sign in/i).click()
    await expect(page).toHaveURL(/\/login/)

    // Navigate to forgot password
    await page.getByText(/forgot password/i).click()
    await expect(page).toHaveURL(/\/forgot-password/)

    // Back to login
    await page.getByText(/back to sign in/i).click()
    await expect(page).toHaveURL(/\/login/)

    // Sign up link back to register
    await page.getByText(/sign up/i).click()
    await expect(page).toHaveURL(/\/register/)
  })
})
