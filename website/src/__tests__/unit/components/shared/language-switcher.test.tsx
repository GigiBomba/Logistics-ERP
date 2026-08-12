import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@/test-utils"
import { LanguageSwitcher } from "@/components/shared/language-switcher"

vi.mock("motion/react", () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

const mockSetLocale = vi.fn()

vi.mock("@/i18n/locale-context", async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    useLocale: () => ({
      locale: "en",
      setLocale: mockSetLocale,
      t: (key: string) => key,
    }),
  }
})

import { SUPPORTED_LOCALES } from "@/i18n/types"

describe("LanguageSwitcher", () => {
  beforeEach(() => {
    mockSetLocale.mockClear()
  })

  it("renders the trigger button with the current locale flag", () => {
    render(<LanguageSwitcher />)
    const button = screen.getByRole("button", { name: /change language/i })
    expect(button).toBeInTheDocument()
    expect(button).toHaveTextContent("🇬🇧")
  })

  it("shows dropdown with all supported languages when trigger is clicked", () => {
    render(<LanguageSwitcher />)
    const button = screen.getByRole("button", { name: /change language/i })
    fireEvent.click(button)

    // All supported languages should be visible in the dropdown
    for (const lang of SUPPORTED_LOCALES) {
      expect(screen.getByText(lang.nativeName)).toBeInTheDocument()
    }
  })

  it("does not show dropdown by default", () => {
    render(<LanguageSwitcher />)
    for (const lang of SUPPORTED_LOCALES) {
      expect(screen.queryByText(lang.nativeName)).not.toBeInTheDocument()
    }
  })

  it("highlights the current language with background styling", () => {
    render(<LanguageSwitcher />)
    fireEvent.click(screen.getByRole("button", { name: /change language/i }))

    // There are two buttons with "English" — the trigger and the dropdown item.
    // Pick the dropdown item by finding the one that has the flag span inside it.
    const allEnglishButtons = screen.getAllByRole("button", { name: /english/i })
    const dropdownButton = allEnglishButtons.find(
      (btn) => btn.querySelector("span") && btn.closest('[class*="rounded-lg"]')
    )!
    expect(dropdownButton.className).toContain("bg-accent")
    expect(dropdownButton.className).toContain("font-medium")
  })

  it("does not apply highlight class to non-current languages", () => {
    render(<LanguageSwitcher />)
    fireEvent.click(screen.getByRole("button", { name: /change language/i }))

    // Romanian is not the current locale (en)
    const roButton = screen.getByText("Română").closest("button")!
    expect(roButton.className).not.toContain("font-medium")
    // The button has hover:bg-accent but not the standalone bg-accent class
    expect(roButton.classList.contains("bg-accent")).toBe(false)
  })

  it("calls setLocale with the correct code when a language is clicked", () => {
    render(<LanguageSwitcher />)
    fireEvent.click(screen.getByRole("button", { name: /change language/i }))

    fireEvent.click(screen.getByText("Română"))
    expect(mockSetLocale).toHaveBeenCalledWith("ro")
  })

  it("closes the dropdown after selecting a language", () => {
    render(<LanguageSwitcher />)
    fireEvent.click(screen.getByRole("button", { name: /change language/i }))

    // Dropdown is open
    expect(screen.getByText("Română")).toBeInTheDocument()

    // Select a language
    fireEvent.click(screen.getByText("Deutsch"))
    expect(mockSetLocale).toHaveBeenCalledWith("de")

    // Dropdown should close
    expect(screen.queryByText("Română")).not.toBeInTheDocument()
  })

  it("closes the dropdown when the overlay backdrop is clicked", () => {
    render(<LanguageSwitcher />)
    fireEvent.click(screen.getByRole("button", { name: /change language/i }))

    // Dropdown is open — all languages visible
    expect(screen.getByText("Română")).toBeInTheDocument()

    // Click the overlay (the fixed inset-0 div)
    const overlay = document.querySelector(".fixed.inset-0")
    expect(overlay).toBeInTheDocument()
    fireEvent.click(overlay!)

    // Dropdown closes
    expect(screen.queryByText("Română")).not.toBeInTheDocument()
  })

  it("closes the dropdown when the trigger button is clicked again", () => {
    render(<LanguageSwitcher />)
    const button = screen.getByRole("button", { name: /change language/i })

    // Open the dropdown
    fireEvent.click(button)
    expect(screen.getByText("Română")).toBeInTheDocument()

    // Click the trigger again to close
    fireEvent.click(button)
    expect(screen.queryByText("Română")).not.toBeInTheDocument()
  })

  it("renders a flag and native name for each supported locale", () => {
    render(<LanguageSwitcher />)
    fireEvent.click(screen.getByRole("button", { name: /change language/i }))

    for (const lang of SUPPORTED_LOCALES) {
      const button = screen.getByText(lang.nativeName).closest("button")!
      expect(button).toHaveTextContent(lang.flag)
      expect(button).toHaveTextContent(lang.nativeName)
    }
  })

  it("sets the aria-label on the trigger button dynamically based on current locale", () => {
    render(<LanguageSwitcher />)
    const button = screen.getByRole("button", { name: /change language \(current: english\)/i })
    expect(button).toBeInTheDocument()
  })

  it("renders all locale buttons inside a popover-style container when open", () => {
    render(<LanguageSwitcher />)
    fireEvent.click(screen.getByRole("button", { name: /change language/i }))

    const dropdown = document.querySelector(".rounded-lg.border")
    expect(dropdown).toBeInTheDocument()
    expect(dropdown!.className).toContain("shadow-lg")
  })
})
