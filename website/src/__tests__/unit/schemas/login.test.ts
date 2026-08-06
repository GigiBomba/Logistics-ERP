import { describe, it, expect } from "vitest"
import { z } from "zod"

// Must match the schema in src/pages/auth/login.tsx
const loginSchema = z.object({
  email: z.string().email("Please enter a valid email"),
  password: z.string().min(1, "Password is required").max(72, "Password must be at most 72 characters"),
})

describe("loginSchema", () => {
  it("accepts valid input", () => {
    const result = loginSchema.safeParse({ email: "user@company.com", password: "secret123" })
    expect(result.success).toBe(true)
  })

  it("rejects empty email", () => {
    const result = loginSchema.safeParse({ email: "", password: "secret123" })
    expect(result.success).toBe(false)
  })

  it("rejects invalid email format", () => {
    const result = loginSchema.safeParse({ email: "not-an-email", password: "secret123" })
    expect(result.success).toBe(false)
  })

  it("rejects empty password", () => {
    const result = loginSchema.safeParse({ email: "user@company.com", password: "" })
    expect(result.success).toBe(false)
  })

  it("rejects missing fields", () => {
    const result = loginSchema.safeParse({})
    expect(result.success).toBe(false)
  })

  // ── 72-byte password max length ──────────────────────────────────

  it("accepts password of exactly 72 characters", () => {
    const pw = "a".repeat(72)
    const result = loginSchema.safeParse({ email: "user@company.com", password: pw })
    expect(result.success).toBe(true)
  })

  it("rejects password longer than 72 characters", () => {
    const pw = "a".repeat(73)
    const result = loginSchema.safeParse({ email: "user@company.com", password: pw })
    expect(result.success).toBe(false)
    if (!result.success) {
      const msg = result.error.issues[0].message
      expect(msg.toLowerCase()).toContain("72")
    }
  })

  it("rejects very long password (100 chars)", () => {
    const pw = "a".repeat(100)
    const result = loginSchema.safeParse({ email: "user@company.com", password: pw })
    expect(result.success).toBe(false)
  })

  it("accepts 72 multi-byte UTF-8 characters", () => {
    // Each 'é' is 2 bytes, but Zod counts string characters, not bytes
    // The Zod schema uses .max(72) which checks string length, not byte length
    const pw = "é".repeat(72)
    const result = loginSchema.safeParse({ email: "user@company.com", password: pw })
    expect(result.success).toBe(true)
  })
})
