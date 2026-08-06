import { describe, it, expect } from "vitest"
import { cn, formatDate, formatCurrency, getInitials } from "@/lib/utils"

describe("cn()", () => {
  it("merges class names", () => {
    expect(cn("px-4", "py-2")).toBe("px-4 py-2")
  })

  it("resolves Tailwind conflicts (last wins)", () => {
    expect(cn("p-4", "p-6")).toBe("p-6")
  })

  it("handles conditional arguments", () => {
    expect(cn("base", false && "hidden", undefined, "extra")).toBe("base extra")
  })

  it("handles empty inputs", () => {
    expect(cn("", null, undefined)).toBe("")
  })

  it("resolves conflicting padding", () => {
    expect(cn("px-4 py-2", "p-6")).toBe("p-6")
  })

  it("resolves margin conflicts", () => {
    expect(cn("mx-2", "m-4")).toBe("m-4")
  })
})

describe("formatDate()", () => {
  it("formats ISO date string", () => {
    const result = formatDate("2026-09-01T00:00:00Z")
    expect(result).toBe("September 1, 2026")
  })

  it("formats Date object", () => {
    const result = formatDate(new Date("2026-01-15T00:00:00Z"))
    expect(result).toBe("January 15, 2026")
  })

  it("formats another ISO string", () => {
    const result = formatDate("2025-12-25T00:00:00Z")
    expect(result).toBe("December 25, 2025")
  })

  it("throws RangeError for bad input", () => {
    expect(() => formatDate("not-a-date")).toThrow(RangeError)
  })

  it("throws RangeError for empty string", () => {
    expect(() => formatDate("")).toThrow(RangeError)
  })
})

describe("formatCurrency()", () => {
  it("formats EUR by default", () => {
    const result = formatCurrency(99, "EUR")
    expect(result).toContain("99")
    expect(result).toContain("€")
  })

  it("formats USD correctly", () => {
    const result = formatCurrency(49.99, "USD")
    expect(result).toContain("49")
    expect(result).toContain("$")
  })

  it("formats large amounts", () => {
    const result = formatCurrency(1000000, "EUR")
    expect(result).toMatch(/(1[.,]000[.,]000)/)
  })

  it("formats zero", () => {
    const result = formatCurrency(0, "EUR")
    expect(result).toContain("0")
  })

  it("formats decimal amounts", () => {
    const result = formatCurrency(29.5, "EUR")
    expect(result).toContain("29")
  })
})

describe("getInitials()", () => {
  it("returns the first letters of the first two words", () => {
    expect(getInitials("Test User")).toBe("TU")
  })

  it("uppercases the result", () => {
    expect(getInitials("john doe")).toBe("JD")
  })

  it("handles a single word", () => {
    expect(getInitials("Operion")).toBe("O")
  })

  it("handles non-Latin / diacritic names", () => {
    expect(getInitials("Ștefan Popescu")).toBe("ȘP")
    expect(getInitials("Ăgnes Müller")).toBe("ĂM")
    expect(getInitials("Björk Guðmundsdóttir")).toBe("BG")
  })

  it("returns '?' for empty input", () => {
    expect(getInitials("")).toBe("?")
    expect(getInitials("   ")).toBe("?")
    expect(getInitials(null as unknown as string)).toBe("?")
    expect(getInitials(undefined as unknown as string)).toBe("?")
  })

  it("collapses extra whitespace between words", () => {
    expect(getInitials("  Ana    Maria  ")).toBe("AM")
  })
})
