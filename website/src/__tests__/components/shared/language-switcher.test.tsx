import { describe, it, expect, beforeEach, vi } from "vitest"
import { render, screen } from "@/test-utils"
import userEvent from "@testing-library/user-event"
import { LanguageSwitcher } from "@/components/shared/language-switcher"
import { SUPPORTED_LOCALES } from "@/i18n/types"

describe("LanguageSwitcher", () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it("shows the current locale code on the trigger button", () => {
    render(<LanguageSwitcher />)
    const button = screen.getByRole("button", { name: /change language/i })
    expect(button).toHaveTextContent("EN")
    expect(button).toHaveAttribute("aria-expanded", "false")
  })

  it("opens and closes the language menu", async () => {
    render(<LanguageSwitcher />)
    const button = screen.getByRole("button", { name: /change language/i })

    await userEvent.click(button)
    expect(button).toHaveAttribute("aria-expanded", "true")
    expect(screen.getByRole("listbox")).toBeInTheDocument()

    await userEvent.click(button)
    await vi.waitFor(() => {
      expect(button).toHaveAttribute("aria-expanded", "false")
    })
  })

  it("lists every supported locale as an option", async () => {
    render(<LanguageSwitcher />)
    await userEvent.click(screen.getByRole("button", { name: /change language/i }))

    const options = screen.getAllByRole("option")
    expect(options).toHaveLength(SUPPORTED_LOCALES.length)
    for (const lang of SUPPORTED_LOCALES) {
      expect(screen.getByRole("option", { name: new RegExp(lang.nativeName) })).toBeInTheDocument()
    }
  })

  it("switching a locale updates the button label and closes the menu", async () => {
    render(<LanguageSwitcher />)
    await userEvent.click(screen.getByRole("button", { name: /change language/i }))

    const de = SUPPORTED_LOCALES.find((l) => l.code === "de")
    await userEvent.click(screen.getByRole("option", { name: new RegExp(de!.nativeName) }))

    await vi.waitFor(() => {
      expect(screen.getByRole("button", { name: /change language/i })).toHaveTextContent("DE")
    })
    await vi.waitFor(() => {
      expect(screen.queryByRole("listbox")).not.toBeInTheDocument()
    })
    expect(localStorage.getItem("operion-locale")).toBe("de")
  })

  it("marks the active locale option as selected", async () => {
    render(<LanguageSwitcher />)
    await userEvent.click(screen.getByRole("button", { name: /change language/i }))

    const english = screen.getByRole("option", { name: /English/ })
    expect(english).toHaveAttribute("aria-selected", "true")
  })
})
