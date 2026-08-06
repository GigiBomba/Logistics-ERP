import { describe, it, expect } from "vitest"
import { z } from "zod"

// Must match the schema in src/pages/auth/reset-password.tsx
const resetPasswordSchema = z
  .object({
    password: z.string().min(8, "Password must be at least 8 characters").max(72, "Password must be at most 72 characters"),
    confirm_password: z.string(),
  })
  .refine((d) => d.password === d.confirm_password, {
    message: "Passwords don't match",
    path: ["confirm_password"],
  })

describe("resetPasswordSchema", () => {
  it("accepts valid passwords", () => {
    const result = resetPasswordSchema.safeParse({
      password: "new-secret123",
      confirm_password: "new-secret123",
    })
    expect(result.success).toBe(true)
  })

  it("rejects short password", () => {
    const result = resetPasswordSchema.safeParse({
      password: "short",
      confirm_password: "short",
    })
    expect(result.success).toBe(false)
  })

  it("rejects mismatched passwords", () => {
    const result = resetPasswordSchema.safeParse({
      password: "new-secret123",
      confirm_password: "different",
    })
    expect(result.success).toBe(false)
  })

  it("rejects empty passwords", () => {
    const result = resetPasswordSchema.safeParse({
      password: "",
      confirm_password: "",
    })
    expect(result.success).toBe(false)
  })

  it("rejects missing confirm_password", () => {
    const result = resetPasswordSchema.safeParse({ password: "new-secret123" })
    expect(result.success).toBe(false)
  })

  // ── 72-byte password max length ──────────────────────────────────

  it("accepts password of exactly 72 characters", () => {
    const pw = "a".repeat(72)
    const result = resetPasswordSchema.safeParse({
      password: pw,
      confirm_password: pw,
    })
    expect(result.success).toBe(true)
  })

  it("rejects password longer than 72 characters", () => {
    const pw = "a".repeat(73)
    const result = resetPasswordSchema.safeParse({
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
    const result = resetPasswordSchema.safeParse({
      password: pw,
      confirm_password: pw,
    })
    expect(result.success).toBe(false)
  })
})
