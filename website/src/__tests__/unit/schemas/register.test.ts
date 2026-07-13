import { describe, it, expect } from "vitest"
import { z } from "zod"

const registerSchema = z.object({
  name: z.string().min(2, "Name must be at least 2 characters"),
  email: z.string().email("Please enter a valid email"),
  company_name: z.string().optional(),
  password: z.string().min(8, "Password must be at least 8 characters"),
  confirm_password: z.string(),
}).refine((data) => data.password === data.confirm_password, {
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
      name: "Jane",
      email: "jane@co.com",
      company_name: "My Company",
      password: "longenough",
      confirm_password: "longenough",
    })
    expect(result.success).toBe(true)
  })

  it("rejects name under 2 characters", () => {
    const result = registerSchema.safeParse({
      name: "A",
      email: "a@b.com",
      password: "longenough",
      confirm_password: "longenough",
    })
    expect(result.success).toBe(false)
  })

  it("rejects invalid email", () => {
    const result = registerSchema.safeParse({
      name: "John",
      email: "bad",
      password: "longenough",
      confirm_password: "longenough",
    })
    expect(result.success).toBe(false)
  })

  it("rejects short password", () => {
    const result = registerSchema.safeParse({
      name: "John",
      email: "j@c.com",
      password: "short",
      confirm_password: "short",
    })
    expect(result.success).toBe(false)
  })

  it("rejects mismatched passwords", () => {
    const result = registerSchema.safeParse({
      name: "John",
      email: "j@c.com",
      password: "longenough",
      confirm_password: "different",
    })
    expect(result.success).toBe(false)
  })

  it("rejects missing required fields", () => {
    const result = registerSchema.safeParse({ email: "j@c.com" })
    expect(result.success).toBe(false)
  })

  it("allows company_name to be omitted", () => {
    const result = registerSchema.safeParse({
      name: "John",
      email: "j@c.com",
      password: "longenough",
      confirm_password: "longenough",
    })
    expect(result.success).toBe(true)
  })
})
