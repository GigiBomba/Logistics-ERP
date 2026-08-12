import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import React from "react"
import { LocaleProvider, useLocale } from "@/i18n/locale-context"

function Wrapper({ children }: { children: React.ReactNode }) {
  return <LocaleProvider>{children}</LocaleProvider>
}

function TranslatableCard() {
  const { t } = useLocale()
  return (
    <div>
      <h1 data-testid="heading">{t("features.title")}</h1>
      <p data-testid="subtitle">{t("features.subtitle")}</p>
      <button data-testid="cta">{t("common.getStarted")}</button>
    </div>
  )
}

describe("i18n integration", () => {
  it("renders English translations by default", () => {
    render(<TranslatableCard />, { wrapper: Wrapper })
    expect(screen.getByTestId("heading")).toHaveTextContent(
      "Autonomous Logistics Workflows, Not Feature Lists"
    )
    expect(screen.getByTestId("cta")).toHaveTextContent("Get Started")
  })

  it("renders translated content without raw key strings", () => {
    render(<TranslatableCard />, { wrapper: Wrapper })
    const heading = screen.getByTestId("heading").textContent || ""
    const subtitle = screen.getByTestId("subtitle").textContent || ""
    // Should not render as raw key like "features.title"
    expect(heading).not.toBe("features.title")
    expect(subtitle).not.toBe("features.subtitle")
  })

  it("all translation keys used in the component exist", () => {
    render(<TranslatableCard />, { wrapper: Wrapper })
    const heading = screen.getByTestId("heading").textContent
    const subtitle = screen.getByTestId("subtitle").textContent
    // Keys should resolve to actual text, not fall back to the key itself
    expect(heading).toBeTruthy()
    expect(subtitle).toBeTruthy()
    expect(heading).not.toMatch(/^features\./)
  })
})
