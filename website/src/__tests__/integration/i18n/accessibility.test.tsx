import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import React from "react"
import { LocaleProvider, useLocale } from "@/i18n/locale-context"

function Wrapper({ children }: { children: React.ReactNode }) {
  return <LocaleProvider>{children}</LocaleProvider>
}

function Toolbar() {
  const { t } = useLocale()
  return (
    <nav>
      <button aria-label={t("common.openSearch")}>S</button>
      <button aria-label={t("common.toggleTheme")}>T</button>
      <button aria-label={t("common.toggleMenu")}>M</button>
    </nav>
  )
}

describe("i18n accessibility", () => {
  it("aria-labels render in English by default", () => {
    render(<Toolbar />, { wrapper: Wrapper })
    expect(screen.getByLabelText("Open search")).toBeTruthy()
    expect(screen.getByLabelText("Toggle theme")).toBeTruthy()
    expect(screen.getByLabelText("Toggle menu")).toBeTruthy()
  })

  it("no aria-label renders as a raw translation key", () => {
    render(<Toolbar />, { wrapper: Wrapper })
    const buttons = screen.getAllByRole("button")
    for (const btn of buttons) {
      const label = btn.getAttribute("aria-label") || ""
      expect(label).not.toMatch(/^[a-z]+\.[a-z]+/)
    }
  })
})
