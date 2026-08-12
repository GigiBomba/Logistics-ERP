import { describe, it, expect } from "vitest"
import { z } from "zod"

describe("profileSchema", () => {
  const schema = z.object({
    name: z.string().min(2, "Name must be at least 2 characters"),
    email: z.string().email("Please enter a valid email"),
  })

  it("accepts valid input", () => {
    const result = schema.safeParse({ name: "John Doe", email: "john@c.com" })
    expect(result.success).toBe(true)
  })

  it("rejects short name", () => {
    const result = schema.safeParse({ name: "J", email: "j@c.com" })
    expect(result.success).toBe(false)
  })

  it("rejects invalid email", () => {
    const result = schema.safeParse({ name: "John", email: "bad" })
    expect(result.success).toBe(false)
  })

  it("rejects empty fields", () => {
    const result = schema.safeParse({ name: "", email: "" })
    expect(result.success).toBe(false)
  })
})

describe("passwordChangeSchema", () => {
  const schema = z.object({
    current_password: z.string().min(1, "Current password is required"),
    new_password: z.string().min(8, "Password must be at least 8 characters"),
    confirm_password: z.string(),
  }).refine((d) => d.new_password === d.confirm_password, {
    message: "Passwords don't match",
    path: ["confirm_password"],
  })

  it("accepts valid passwords", () => {
    const result = schema.safeParse({
      current_password: "oldpass",
      new_password: "newpass123",
      confirm_password: "newpass123",
    })
    expect(result.success).toBe(true)
  })

  it("rejects empty current password", () => {
    const result = schema.safeParse({
      current_password: "",
      new_password: "newpass123",
      confirm_password: "newpass123",
    })
    expect(result.success).toBe(false)
  })

  it("rejects short new password", () => {
    const result = schema.safeParse({
      current_password: "oldpass",
      new_password: "short",
      confirm_password: "short",
    })
    expect(result.success).toBe(false)
  })

  it("rejects mismatched new passwords", () => {
    const result = schema.safeParse({
      current_password: "oldpass",
      new_password: "newpass123",
      confirm_password: "different",
    })
    expect(result.success).toBe(false)
  })
})
