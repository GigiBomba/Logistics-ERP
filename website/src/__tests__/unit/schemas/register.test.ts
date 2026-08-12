import { describe, it, expect } from "vitest"
import { z } from "zod"

// Must match the schema in src/pages/auth/register.tsx
const registerSchema = z
  .object({
    name: z.string().min(2, "Name must be at least 2 characters"),
    email: z.string().email("Please enter a valid email"),
    company_name: z.string().optional(),
    password: z.string().min(8, "Password must be at least 8 characters").max(72, "Password must be at most 72 characters"),
    confirm_password: z.string(),
  })
  .refine((data) => data.password === data.confirm_password, {
    message: "Passwords don't match",
    path: ["confirm_password"],
  })

describe("registerSchema", () => {
  it("accepts valid input", () => {
    const result = registerSchema.safeParse({
      name: "John Doe",
      email: "john@company.com",
      password: "secret123",
      confirm_password: "secret123",
    })
    expect(result.success).toBe(true)
  })

  it("accepts valid input with company name", () => {
    const result = registerSchema.safeParse({
      name: "John Doe",
      email: "john@company.com",
      company_name: "My Company",
      password: "secret123",
      confirm_password: "secret123",
    })
    expect(result.success).toBe(true)
  })

  it("rejects name under 2 characters", () => {
    const result = registerSchema.safeParse({
      name: "J",
      email: "john@company.com",
      password: "secret123",
      confirm_password: "secret123",
    })
    expect(result.success).toBe(false)
  })

  it("rejects invalid email", () => {
    const result = registerSchema.safeParse({
      name: "John Doe",
      email: "invalid",
      password: "secret123",
      confirm_password: "secret123",
    })
    expect(result.success).toBe(false)
  })

  it("rejects short password", () => {
    const result = registerSchema.safeParse({
      name: "John Doe",
      email: "john@company.com",
      password: "short",
      confirm_password: "short",
    })
    expect(result.success).toBe(false)
  })

  it("rejects mismatched passwords", () => {
    const result = registerSchema.safeParse({
      name: "John Doe",
      email: "john@company.com",
      password: "secret123",
      confirm_password: "different",
    })
    expect(result.success).toBe(false)
  })

  it("rejects missing required fields", () => {
    const result = registerSchema.safeParse({})
    expect(result.success).toBe(false)
  })

  it("allows company_name to be omitted", () => {
    const result = registerSchema.safeParse({
      name: "John Doe",
      email: "john@company.com",
      password: "secret123",
      confirm_password: "secret123",
    })
    expect(result.success).toBe(true)
  })

  // ── 72-byte password max length ──────────────────────────────────

  it("accepts password of exactly 72 characters", () => {
    const pw = "a".repeat(72)
    const result = registerSchema.safeParse({
      name: "John Doe",
      email: "john@company.com",
      password: pw,
      confirm_password: pw,
    })
    expect(result.success).toBe(true)
  })

  it("rejects password longer than 72 characters", () => {
    const pw = "a".repeat(73)
    const result = registerSchema.safeParse({
      name: "John Doe",
      email: "john@company.com",
      password: pw,
      confirm_password: pw,
    })
    expect(result.success).toBe(false)
    if (!result.success) {
      const msg = result.error.issues[0].message
      expect(msg.toLowerCase()).toContain("72")
    }
  })

  it("rejects password with 100 characters", () => {
    const pw = "a".repeat(100)
    const result = registerSchema.safeParse({
      name: "John Doe",
      email: "john@company.com",
      password: pw,
      confirm_password: pw,
    })
    expect(result.success).toBe(false)
  })
})
