import { describe, it, expect } from "vitest"
import { z } from "zod"

describe("forgotPasswordSchema", () => {
  const schema = z.object({
    email: z.string().email("Please enter a valid email"),
  })

  it("accepts valid email", () => {
    const result = schema.safeParse({ email: "user@company.com" })
    expect(result.success).toBe(true)
  })

  it("rejects empty email", () => {
    const result = schema.safeParse({ email: "" })
    expect(result.success).toBe(false)
  })

  it("rejects invalid email", () => {
    const result = schema.safeParse({ email: "not-email" })
    expect(result.success).toBe(false)
  })

  it("rejects missing email", () => {
    const result = schema.safeParse({})
    expect(result.success).toBe(false)
  })
})
