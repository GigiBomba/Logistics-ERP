import { describe, it, expect } from "vitest"
import { z } from "zod"

const loginSchema = z.object({
  email: z.string().email("Please enter a valid email"),
  password: z.string().min(1, "Password is required"),
})

describe("loginSchema", () => {
  it("accepts valid input", () => {
    const result = loginSchema.safeParse({ email: "user@company.com", password: "secret123" })
    expect(result.success).toBe(true)
  })

  it("rejects empty email", () => {
    const result = loginSchema.safeParse({ email: "", password: "secret" })
    expect(result.success).toBe(false)
  })

  it("rejects invalid email format", () => {
    const result = loginSchema.safeParse({ email: "not-an-email", password: "secret" })
    expect(result.success).toBe(false)
  })

  it("rejects empty password", () => {
    const result = loginSchema.safeParse({ email: "user@c.com", password: "" })
    expect(result.success).toBe(false)
  })

  it("rejects missing fields", () => {
    const result = loginSchema.safeParse({ email: "user@c.com" })
    expect(result.success).toBe(false)
  })
})
