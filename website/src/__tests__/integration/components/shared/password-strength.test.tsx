import { describe, it, expect } from "vitest"
import { render, screen } from "@/test-utils"
import { PasswordStrength } from "@/components/shared/password-strength"

describe("PasswordStrength", () => {
  it("renders nothing for an empty password", () => {
    const { container } = render(<PasswordStrength password="" />)
    expect(container.firstChild).toBeNull()
  })

  it("shows Weak for a short password (score 0)", () => {
    render(<PasswordStrength password="short" />)
    const bar = screen.getByRole("progressbar")
    expect(bar).toHaveAttribute("aria-valuenow", "0")
    expect(bar).toHaveAttribute("aria-label", "Password strength: Weak")
    expect(screen.getByText("Weak")).toBeInTheDocument()
  })

  it("shows Weak for a length-8 password with no other criteria (score 1)", () => {
    render(<PasswordStrength password="abcdefgh" />)
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "1")
    expect(screen.getByText("Weak")).toBeInTheDocument()
  })

  it("shows Fair for length + number (score 2)", () => {
    render(<PasswordStrength password="abcdefgh1" />)
    const bar = screen.getByRole("progressbar")
    expect(bar).toHaveAttribute("aria-valuenow", "2")
    expect(bar).toHaveAttribute("aria-label", "Password strength: Fair")
    expect(screen.getByText("Fair")).toBeInTheDocument()
  })

  it("shows Good for length + number + symbol (score 3)", () => {
    render(<PasswordStrength password="abcdefgh1!" />)
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "3")
    expect(screen.getByText("Good")).toBeInTheDocument()
  })

  it("shows Strong when all criteria are met (score 4)", () => {
    render(<PasswordStrength password="Abcdefgh1!" />)
    const bar = screen.getByRole("progressbar")
    expect(bar).toHaveAttribute("aria-valuenow", "4")
    expect(bar).toHaveAttribute("aria-label", "Password strength: Strong")
    expect(screen.getByText("Strong")).toBeInTheDocument()
  })

  it("awarding an extra point for 12+ characters (score 5 still renders Strong)", () => {
    render(<PasswordStrength password="Abcdefghijk1!" />)
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "5")
    expect(screen.getByText("Strong")).toBeInTheDocument()
  })

  it("toggles the criteria checklist based on the password", () => {
    render(<PasswordStrength password="short" />)
    expect(screen.getByText("○ 8+ characters")).toBeInTheDocument()
    expect(screen.getByText("○ Number")).toBeInTheDocument()

    render(<PasswordStrength password="Abcdefgh1!" />)
    expect(screen.getByText("✓ 8+ characters")).toBeInTheDocument()
    expect(screen.getByText("✓ Number")).toBeInTheDocument()
    expect(screen.getByText("✓ Symbol")).toBeInTheDocument()
    expect(screen.getByText("✓ Uppercase letter")).toBeInTheDocument()
  })
})
