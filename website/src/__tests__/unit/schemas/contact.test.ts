import { describe, it, expect } from "vitest"
import { z } from "zod"

describe("contactSchema", () => {
  const schema = z.object({
    name: z.string().min(2, "Name must be at least 2 characters"),
    email: z.string().email("Please enter a valid email"),
    subject: z.string().min(5, "Subject must be at least 5 characters"),
    message: z.string().min(10, "Message must be at least 10 characters"),
  })

  it("accepts valid contact form", () => {
    const result = schema.safeParse({
      name: "John Doe",
      email: "john@company.com",
      subject: "Question about pricing",
      message: "I would like to know more about your enterprise plan pricing.",
    })
    expect(result.success).toBe(true)
  })

  it("rejects short name", () => {
    const result = schema.safeParse({
      name: "J",
      email: "j@c.com",
      subject: "A valid subject",
      message: "A valid message that's long enough",
    })
    expect(result.success).toBe(false)
  })

  it("rejects invalid email", () => {
    const result = schema.safeParse({
      name: "John",
      email: "bad",
      subject: "A valid subject",
      message: "A valid message that's long enough",
    })
    expect(result.success).toBe(false)
  })

  it("rejects short subject", () => {
    const result = schema.safeParse({
      name: "John",
      email: "j@c.com",
      subject: "Hi",
      message: "A valid message that's long enough",
    })
    expect(result.success).toBe(false)
  })

  it("rejects short message", () => {
    const result = schema.safeParse({
      name: "John",
      email: "j@c.com",
      subject: "A valid subject",
      message: "Short",
    })
    expect(result.success).toBe(false)
  })

  it("rejects missing all fields", () => {
    const result = schema.safeParse({})
    expect(result.success).toBe(false)
  })
})
