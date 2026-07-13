import { describe, it, expect } from "vitest"
import { z } from "zod"

describe("resetPasswordSchema", () => {
  const schema = z.object({
    password: z.string().min(8, "Password must be at least 8 characters"),
    confirm_password: z.string(),
  }).refine((d) => d.password === d.confirm_password, {
    message: "Passwords don't match",
    path: ["confirm_password"],
  })

  it("accepts valid passwords", () => {
    const result = schema.safeParse({ password: "newsecret123", confirm_password: "newsecret123" })
    expect(result.success).toBe(true)
  })

  it("rejects short password", () => {
    const result = schema.safeParse({ password: "short", confirm_password: "short" })
    expect(result.success).toBe(false)
  })

  it("rejects mismatched passwords", () => {
    const result = schema.safeParse({ password: "longenough", confirm_password: "different" })
    expect(result.success).toBe(false)
  })

  it("rejects empty passwords", () => {
    const result = schema.safeParse({ password: "", confirm_password: "" })
    expect(result.success).toBe(false)
  })

  it("rejects missing confirm_password", () => {
    const result = schema.safeParse({ password: "longenough" })
    expect(result.success).toBe(false)
  })
})
