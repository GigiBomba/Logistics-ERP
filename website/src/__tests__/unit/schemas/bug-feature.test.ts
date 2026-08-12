import { describe, it, expect } from "vitest"
import { z } from "zod"

describe("bugSchema", () => {
  const schema = z.object({
    title: z.string().min(5, "Title must be at least 5 characters"),
    description: z.string().min(20, "Please provide a detailed description"),
    steps: z.string().optional(),
  })

  it("accepts valid bug report with all fields", () => {
    const result = schema.safeParse({
      title: "Application crash on login",
      description: "When I click the login button, the application crashes immediately.",
      steps: "1. Open app\n2. Enter credentials\n3. Click Sign In",
    })
    expect(result.success).toBe(true)
  })

  it("accepts valid bug report without steps", () => {
    const result = schema.safeParse({
      title: "Button alignment issue",
      description: "The save button is misaligned on smaller screens.",
    })
    expect(result.success).toBe(true)
  })

  it("rejects short title", () => {
    const result = schema.safeParse({ title: "Bug", description: "This is a description that is long enough to pass." })
    expect(result.success).toBe(false)
  })

  it("rejects short description", () => {
    const result = schema.safeParse({ title: "Application crash", description: "Too short" })
    expect(result.success).toBe(false)
  })

  it("rejects empty title", () => {
    const result = schema.safeParse({ title: "", description: "This is a description that is long enough to pass." })
    expect(result.success).toBe(false)
  })
})

describe("featureSchema", () => {
  const schema = z.object({
    title: z.string().min(5, "Title must be at least 5 characters"),
    description: z.string().min(20, "Please describe the feature you'd like"),
    use_case: z.string().optional(),
  })

  it("accepts valid feature request", () => {
    const result = schema.safeParse({
      title: "Export to PDF",
      description: "It would be great to export invoices and reports to PDF format.",
      use_case: "We need to share reports with clients who don't have Operion access.",
    })
    expect(result.success).toBe(true)
  })

  it("accepts valid request without use_case", () => {
    const result = schema.safeParse({
      title: "Dark mode toggle",
      description: "I would like a dark mode option in the settings page.",
    })
    expect(result.success).toBe(true)
  })

  it("rejects short title", () => {
    const result = schema.safeParse({ title: "Hi", description: "This is a description that is long enough to pass." })
    expect(result.success).toBe(false)
  })

  it("rejects short description", () => {
    const result = schema.safeParse({ title: "Feature idea", description: "Short desc" })
    expect(result.success).toBe(false)
  })
})
