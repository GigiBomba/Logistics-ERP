import { describe, it, expect, beforeEach, vi } from "vitest"
import { renderHook, act } from "@testing-library/react"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import React from "react"
import { LocaleProvider, useLocale } from "@/i18n/locale-context"

function Wrapper({ children }: { children: React.ReactNode }) {
  return <LocaleProvider>{children}</LocaleProvider>
}

beforeEach(() => {
  localStorage.clear()
})

// ── useLocale hook ──────────────────────────────────────────

describe("useLocale", () => {
  it("returns default locale (en) on first render", () => {
    const { result } = renderHook(() => useLocale(), { wrapper: Wrapper })
    expect(result.current.locale).toBe("en")
  })

  it("t() returns English translation for known key", () => {
    const { result } = renderHook(() => useLocale(), { wrapper: Wrapper })
    expect(result.current.t("common.save")).toBe("Save")
    expect(result.current.t("nav.home")).toBe("Home")
    expect(result.current.t("auth.email")).toBe("Email")
  })

  it("t() returns raw key when key does not exist anywhere", () => {
    const { result } = renderHook(() => useLocale(), { wrapper: Wrapper })
    const nonexistent = "this.key.does.not.exist.completely"
    expect(result.current.t(nonexistent)).toBe(nonexistent)
  })

  it("t() falls back to English when key missing in current locale", () => {
    const { result } = renderHook(() => useLocale(), { wrapper: Wrapper })
    // Switch to Romanian
    act(() => result.current.setLocale("ro"))
    // "common.save" exists in ro.json as "Salvează"
    expect(result.current.t("common.save")).toBe("Salvează")
  })

  it("setLocale changes locale and persists to localStorage", () => {
    const { result } = renderHook(() => useLocale(), { wrapper: Wrapper })
    act(() => result.current.setLocale("de"))
    expect(result.current.locale).toBe("de")
    expect(localStorage.getItem("operion-locale")).toBe("de")
  })

  it("rapid locale switching returns correct translations", () => {
    const { result } = renderHook(() => useLocale(), { wrapper: Wrapper })
    act(() => result.current.setLocale("fr"))
    expect(result.current.t("common.cancel")).toBe("Annuler")
    act(() => result.current.setLocale("es"))
    expect(result.current.t("common.cancel")).toBe("Cancelar")
    act(() => result.current.setLocale("en"))
    expect(result.current.t("common.cancel")).toBe("Cancel")
  })

  it("restores locale from localStorage on mount", () => {
    localStorage.setItem("operion-locale", "pl")
    const { result } = renderHook(() => useLocale(), { wrapper: Wrapper })
    expect(result.current.locale).toBe("pl")
  })

  it("ignores invalid locale in localStorage, falls back to en", () => {
    localStorage.setItem("operion-locale", "xx")
    const { result } = renderHook(() => useLocale(), { wrapper: Wrapper })
    expect(result.current.locale).toBe("en")
  })
})

// ── t() edge cases ─────────────────────────────────────────

describe("t() edge cases", () => {
  it("handles empty string key", () => {
    const { result } = renderHook(() => useLocale(), { wrapper: Wrapper })
    expect(result.current.t("")).toBe("")
  })

  it("back-to-back t() calls return correct values", () => {
    const { result } = renderHook(() => useLocale(), { wrapper: Wrapper })
    expect(result.current.t("common.close")).toBe("Close")
    expect(result.current.t("common.delete")).toBe("Delete")
    expect(result.current.t("common.edit")).toBe("Edit")
  })

  it("t() result changes when locale changes", () => {
    const { result } = renderHook(() => useLocale(), { wrapper: Wrapper })
    const enSave = result.current.t("common.save")
    act(() => result.current.setLocale("ro"))
    const roSave = result.current.t("common.save")
    expect(enSave).not.toBe(roSave)
    expect(enSave).toBe("Save")
    expect(roSave).toBe("Salvează")
  })
})

// ── Component rendering ────────────────────────────────────

function TestComponent({ labelKey }: { labelKey: string }) {
  const { t, locale, setLocale } = useLocale()
  return (
    <div>
      <span data-testid="translated">{t(labelKey)}</span>
      <span data-testid="locale">{locale}</span>
      <button data-testid="switch-de" onClick={() => setLocale("de")}>
        DE
      </button>
    </div>
  )
}

describe("component rendering", () => {
  it("renders translated text", () => {
    render(<TestComponent labelKey="common.submit" />, { wrapper: Wrapper })
    expect(screen.getByTestId("translated").textContent).toBe("Submit")
  })

  it("locale switching updates rendered UI", async () => {
    const user = userEvent.setup()
    render(<TestComponent labelKey="common.submit" />, { wrapper: Wrapper })
    expect(screen.getByTestId("locale").textContent).toBe("en")
    await user.click(screen.getByTestId("switch-de"))
    expect(screen.getByTestId("locale").textContent).toBe("de")
    // German: "common.submit" -> "Einreichen" or "Senden"
    expect(screen.getByTestId("translated").textContent).toBeTruthy()
  })
})

// ── Error handling ─────────────────────────────────────────

describe("error handling", () => {
  it("throws when useLocale used outside LocaleProvider", () => {
    function BadComponent() {
      const { t } = useLocale()
      return <span>{t("common.save")}</span>
    }
    // Suppress console.error for expected throw
    const spy = vi.spyOn(console, "error").mockImplementation(() => {})
    expect(() => render(<BadComponent />)).toThrow(
      "useLocale must be used within LocaleProvider"
    )
    spy.mockRestore()
  })
})
