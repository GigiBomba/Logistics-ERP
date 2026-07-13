import { describe, it, expect } from "vitest"
import { z } from "zod"

// ── Auth form schemas (replicated from source for isolated unit testing) ──

const forgotPasswordSchema = z.object({
  email: z.string().email("Please enter a valid email"),
})

const resetPasswordSchema = z
  .object({
    password: z.string().min(8, "Password must be at least 8 characters"),
    confirm_password: z.string(),
  })
  .refine((data) => data.password === data.confirm_password, {
    message: "Passwords don't match",
    path: ["confirm_password"],
  })

const contactSchema = z.object({
  name: z.string().min(2, "Name must be at least 2 characters"),
  email: z.string().email("Please enter a valid email"),
  subject: z.string().min(5, "Subject must be at least 5 characters"),
  message: z.string().min(10, "Message must be at least 10 characters"),
})

// ── Forgot Password ───────────────────────────────────────────────────────

describe("ForgotPassword form schema", () => {
  it("accepts a valid email", () => {
    const result = forgotPasswordSchema.safeParse({ email: "user@example.com" })
    expect(result.success).toBe(true)
  })

  it("rejects an invalid email", () => {
    const result = forgotPasswordSchema.safeParse({ email: "not-an-email" })
    expect(result.success).toBe(false)
    if (!result.success) {
      expect(result.error.issues[0].message).toBe("Please enter a valid email")
    }
  })

  it("rejects an empty email", () => {
    const result = forgotPasswordSchema.safeParse({ email: "" })
    expect(result.success).toBe(false)
  })

  it("rejects missing email field", () => {
    const result = forgotPasswordSchema.safeParse({})
    expect(result.success).toBe(false)
  })
})

// ── Reset Password ────────────────────────────────────────────────────────

describe("ResetPassword form schema", () => {
  it("accepts matching passwords of sufficient length", () => {
    const result = resetPasswordSchema.safeParse({
      password: "securePass123",
      confirm_password: "securePass123",
    })
    expect(result.success).toBe(true)
  })

  it("rejects a password shorter than 8 characters", () => {
    const result = resetPasswordSchema.safeParse({
      password: "short",
      confirm_password: "short",
    })
    expect(result.success).toBe(false)
    if (!result.success) {
      expect(result.error.issues[0].message).toBe(
        "Password must be at least 8 characters"
      )
    }
  })

  it("rejects mismatched passwords", () => {
    const result = resetPasswordSchema.safeParse({
      password: "longEnoughPass",
      confirm_password: "differentPass",
    })
    expect(result.success).toBe(false)
    if (!result.success) {
      const mismatchIssue = result.error.issues.find(
        (i) => i.message === "Passwords don't match"
      )
      expect(mismatchIssue).toBeDefined()
    }
  })

  it("rejects empty password", () => {
    const result = resetPasswordSchema.safeParse({
      password: "",
      confirm_password: "",
    })
    expect(result.success).toBe(false)
  })
})

// ── Contact Form ──────────────────────────────────────────────────────────

describe("Contact form schema", () => {
  it("accepts valid contact data", () => {
    const result = contactSchema.safeParse({
      name: "John Doe",
      email: "john@example.com",
      subject: "Partnership inquiry",
      message: "I would like to discuss a potential partnership opportunity.",
    })
    expect(result.success).toBe(true)
  })

  it("rejects a name shorter than 2 characters", () => {
    const result = contactSchema.safeParse({
      name: "J",
      email: "john@example.com",
      subject: "Valid subject",
      message: "Valid message body here",
    })
    expect(result.success).toBe(false)
  })

  it("rejects an invalid email", () => {
    const result = contactSchema.safeParse({
      name: "John Doe",
      email: "bad-email",
      subject: "Valid subject",
      message: "Valid message body here",
    })
    expect(result.success).toBe(false)
  })

  it("rejects a short subject", () => {
    const result = contactSchema.safeParse({
      name: "John Doe",
      email: "john@example.com",
      subject: "Hi",
      message: "Valid message body here",
    })
    expect(result.success).toBe(false)
  })

  it("rejects a short message", () => {
    const result = contactSchema.safeParse({
      name: "John Doe",
      email: "john@example.com",
      subject: "Valid subject",
      message: "Short",
    })
    expect(result.success).toBe(false)
  })

  it("rejects missing fields", () => {
    const result = contactSchema.safeParse({})
    expect(result.success).toBe(false)
  })
})
