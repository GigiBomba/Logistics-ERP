import { describe, it, expect, vi, beforeEach } from "vitest"
import { renderHook, act, render, screen } from "@testing-library/react"
import { LocaleProvider, useLocale } from "@/i18n/locale-context"
import { SUPPORTED_LOCALES, DEFAULT_LOCALE } from "@/i18n/types"
import type { LocaleCode } from "@/i18n/types"
import { type ReactNode } from "react"

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderLocaleHook() {
  return renderHook(() => useLocale(), {
    wrapper: ({ children }: { children: ReactNode }) => (
      <LocaleProvider>{children}</LocaleProvider>
    ),
  })
}

/** A test consumer that exposes current locale and a translated string. */
function TestConsumer() {
  const { locale, setLocale, t } = useLocale()
  return (
    <div>
      <span data-testid="locale">{locale}</span>
      <span data-testid="translation">{t("common.save")}</span>
      <button
        data-testid="set-locale-ro"
        onClick={() => setLocale("ro" satisfies LocaleCode)}
      >
        Set RO
      </button>
      <button
        data-testid="set-locale-de"
        onClick={() => setLocale("de" satisfies LocaleCode)}
      >
        Set DE
      </button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("LocaleProvider", () => {
  beforeEach(() => {
    localStorage.clear()
  })

  // --- Rendering -----------------------------------------------

  it("renders without crashing", () => {
    const { result } = renderLocaleHook()
    expect(result.current).toBeDefined()
  })

  it("renders children inside the provider", () => {
    render(
      <LocaleProvider>
        <div data-testid="child">Hello</div>
      </LocaleProvider>,
    )
    expect(screen.getByTestId("child")).toHaveTextContent("Hello")
  })

  // --- Default locale ------------------------------------------

  it("applies the default locale when no locale is stored", () => {
    const { result } = renderLocaleHook()
    expect(result.current.locale).toBe(DEFAULT_LOCALE)
  })

  it("default locale is 'en'", () => {
    expect(DEFAULT_LOCALE).toBe("en")
  })

  // --- useLocale returns current locale ------------------------

  it("useLocale returns current locale code", () => {
    const { result } = renderLocaleHook()
    expect(result.current.locale).toBe("en")
  })

  it("useLocale returns a setLocale function", () => {
    const { result } = renderLocaleHook()
    expect(typeof result.current.setLocale).toBe("function")
  })

  it("useLocale returns a t function", () => {
    const { result } = renderLocaleHook()
    expect(typeof result.current.t).toBe("function")
  })

  // --- setLocale changes locale --------------------------------

  it("setLocale changes to Romanian", () => {
    const { result } = renderLocaleHook()
    act(() => {
      result.current.setLocale("ro")
    })
    expect(result.current.locale).toBe("ro")
  })

  it("setLocale changes to German", () => {
    const { result } = renderLocaleHook()
    act(() => {
      result.current.setLocale("de")
    })
    expect(result.current.locale).toBe("de")
  })

  it("setLocale changes to French", () => {
    const { result } = renderLocaleHook()
    act(() => {
      result.current.setLocale("fr")
    })
    expect(result.current.locale).toBe("fr")
  })

  it("setLocale changes to Spanish", () => {
    const { result } = renderLocaleHook()
    act(() => {
      result.current.setLocale("es")
    })
    expect(result.current.locale).toBe("es")
  })

  it("setLocale changes to Polish", () => {
    const { result } = renderLocaleHook()
    act(() => {
      result.current.setLocale("pl")
    })
    expect(result.current.locale).toBe("pl")
  })

  // --- Persistence to localStorage -----------------------------

  it("persists locale to localStorage on setLocale", () => {
    const { result } = renderLocaleHook()
    act(() => {
      result.current.setLocale("ro")
    })
    expect(localStorage.getItem("operion-locale")).toBe("ro")
  })

  it("persists each locale change to localStorage", () => {
    const { result } = renderLocaleHook()
    act(() => {
      result.current.setLocale("de")
    })
    expect(localStorage.getItem("operion-locale")).toBe("de")

    act(() => {
      result.current.setLocale("fr")
    })
    expect(localStorage.getItem("operion-locale")).toBe("fr")
  })

  // --- Rehydration from localStorage ---------------------------

  it("rehydrates locale from localStorage on mount", () => {
    localStorage.setItem("operion-locale", "ro")
    const { result } = renderLocaleHook()
    expect(result.current.locale).toBe("ro")
  })

  it("rehydrates German from localStorage", () => {
    localStorage.setItem("operion-locale", "de")
    const { result } = renderLocaleHook()
    expect(result.current.locale).toBe("de")
  })

  it("rehydrates French from localStorage", () => {
    localStorage.setItem("operion-locale", "fr")
    const { result } = renderLocaleHook()
    expect(result.current.locale).toBe("fr")
  })

  // --- Invalid locale fallback ---------------------------------

  it("falls back to default locale when stored locale is invalid", () => {
    localStorage.setItem("operion-locale", "xx")
    const { result } = renderLocaleHook()
    expect(result.current.locale).toBe(DEFAULT_LOCALE)
  })

  it("falls back to default locale with empty string", () => {
    localStorage.setItem("operion-locale", "")
    const { result } = renderLocaleHook()
    expect(result.current.locale).toBe(DEFAULT_LOCALE)
  })

  it("falls back to default locale with garbage value", () => {
    localStorage.setItem("operion-locale", "not-a-locale-at-all")
    const { result } = renderLocaleHook()
    expect(result.current.locale).toBe(DEFAULT_LOCALE)
  })

  it("falls back to default locale with null-like value", () => {
    localStorage.setItem("operion-locale", "null")
    const { result } = renderLocaleHook()
    expect(result.current.locale).toBe(DEFAULT_LOCALE)
  })

  // --- SUPPORTED_LOCALES constants -----------------------------

  it("SUPPORTED_LOCALES has correct number of entries", () => {
    expect(SUPPORTED_LOCALES).toHaveLength(6)
  })

  it("SUPPORTED_LOCALES contains all expected locale codes", () => {
    const codes = SUPPORTED_LOCALES.map((l) => l.code)
    expect(codes).toEqual(["en", "ro", "de", "fr", "es", "pl"])
  })

  it("each SUPPORTED_LOCALES entry has required fields", () => {
    for (const locale of SUPPORTED_LOCALES) {
      expect(locale).toHaveProperty("code")
      expect(locale).toHaveProperty("name")
      expect(locale).toHaveProperty("nativeName")
      expect(locale).toHaveProperty("flag")
      expect(typeof locale.code).toBe("string")
      expect(typeof locale.name).toBe("string")
      expect(typeof locale.nativeName).toBe("string")
      expect(typeof locale.flag).toBe("string")
    }
  })

  it("SUPPORTED_LOCALES English has correct name and nativeName", () => {
    const en = SUPPORTED_LOCALES.find((l) => l.code === "en")!
    expect(en.name).toBe("English")
    expect(en.nativeName).toBe("English")
    expect(en.flag).toBe("🇬🇧")
  })

  it("SUPPORTED_LOCALES Romanian has correct name and nativeName", () => {
    const ro = SUPPORTED_LOCALES.find((l) => l.code === "ro")!
    expect(ro.name).toBe("Romanian")
    expect(ro.nativeName).toBe("Română")
    expect(ro.flag).toBe("🇷🇴")
  })

  it("SUPPORTED_LOCALES German has correct name and nativeName", () => {
    const de = SUPPORTED_LOCALES.find((l) => l.code === "de")!
    expect(de.name).toBe("German")
    expect(de.nativeName).toBe("Deutsch")
    expect(de.flag).toBe("🇩🇪")
  })

  it("SUPPORTED_LOCALES French has correct name and nativeName", () => {
    const fr = SUPPORTED_LOCALES.find((l) => l.code === "fr")!
    expect(fr.name).toBe("French")
    expect(fr.nativeName).toBe("Français")
    expect(fr.flag).toBe("🇫🇷")
  })

  it("SUPPORTED_LOCALES Spanish has correct name and nativeName", () => {
    const es = SUPPORTED_LOCALES.find((l) => l.code === "es")!
    expect(es.name).toBe("Spanish")
    expect(es.nativeName).toBe("Español")
    expect(es.flag).toBe("🇪🇸")
  })

  it("SUPPORTED_LOCALES Polish has correct name and nativeName", () => {
    const pl = SUPPORTED_LOCALES.find((l) => l.code === "pl")!
    expect(pl.name).toBe("Polish")
    expect(pl.nativeName).toBe("Polski")
    expect(pl.flag).toBe("🇵🇱")
  })

  // --- Locale change triggers re-render of consumers -----------

  it("translations update when locale changes via hook", () => {
    const { result } = renderLocaleHook()

    // English default
    expect(result.current.t("common.save")).toBe("Save")

    act(() => {
      result.current.setLocale("ro")
    })
    expect(result.current.t("common.save")).toBe("Salvează")

    act(() => {
      result.current.setLocale("de")
    })
    expect(result.current.t("common.save")).toBe("Speichern")
  })

  it("re-renders component when locale changes via setLocale", () => {
    render(
      <LocaleProvider>
        <TestConsumer />
      </LocaleProvider>,
    )

    // Default English
    expect(screen.getByTestId("locale")).toHaveTextContent("en")
    expect(screen.getByTestId("translation")).toHaveTextContent("Save")

    // Switch to Romanian
    act(() => {
      screen.getByTestId("set-locale-ro").click()
    })
    expect(screen.getByTestId("locale")).toHaveTextContent("ro")
    expect(screen.getByTestId("translation")).toHaveTextContent("Salvează")

    // Switch to German
    act(() => {
      screen.getByTestId("set-locale-de").click()
    })
    expect(screen.getByTestId("locale")).toHaveTextContent("de")
    expect(screen.getByTestId("translation")).toHaveTextContent("Speichern")
  })

  // --- t() function behavior -----------------------------------

  it("t returns correct translation for current locale", () => {
    const { result } = renderLocaleHook()

    act(() => {
      result.current.setLocale("ro")
    })
    expect(result.current.t("common.save")).toBe("Salvează")
    expect(result.current.t("nav.home")).toBe("Acasă")
    expect(result.current.t("common.cancel")).toBe("Anulează")
  })

  it("t returns English translation when key is missing from current locale", () => {
    const { result } = renderLocaleHook()

    act(() => {
      result.current.setLocale("ro")
    })
    // "home.hero.badge" exists in en.json but likely not in ro.json
    const val = result.current.t("home.hero.badge")
    expect(val).toBe("Logistics ERP")
  })

  it("t returns the key itself when translation is missing in all locales", () => {
    const { result } = renderLocaleHook()
    const val = result.current.t("nonexistent.key.ever")
    expect(val).toBe("nonexistent.key.ever")
  })

  // --- Edge cases ----------------------------------------------

  it("handles repeated locale changes correctly", () => {
    const { result } = renderLocaleHook()

    act(() => {
      result.current.setLocale("ro")
    })
    expect(result.current.locale).toBe("ro")

    act(() => {
      result.current.setLocale("de")
    })
    expect(result.current.locale).toBe("de")

    act(() => {
      result.current.setLocale("fr")
    })
    expect(result.current.locale).toBe("fr")

    act(() => {
      result.current.setLocale("en")
    })
    expect(result.current.locale).toBe("en")
  })

  it("setting the same locale does not break", () => {
    const { result } = renderLocaleHook()
    act(() => {
      result.current.setLocale("en")
    })
    expect(result.current.locale).toBe("en")
    expect(result.current.t("common.save")).toBe("Save")
  })

  it("works with empty children", () => {
    const { container } = render(
      <LocaleProvider>
        {/* Intentionally empty */}
      </LocaleProvider>,
    )
    expect(container).toBeDefined()
  })

  // --- useLocale throws outside provider -----------------------

  it("throws when useLocale is used outside LocaleProvider", () => {
    expect(() => {
      renderHook(() => useLocale())
    }).toThrow("useLocale must be used within LocaleProvider")
  })

  // --- localStorage key constant -------------------------------

  it("uses the correct localStorage key", () => {
    const { result } = renderLocaleHook()
    act(() => {
      result.current.setLocale("ro")
    })

    // Verify it's the expected key, not something else
    expect(localStorage.getItem("operion-locale")).toBe("ro")
  })

  // --- t() function with all supported locales -----------------

  it("t function works for every supported locale", () => {
    const { result } = renderLocaleHook()

    const testCases: Array<{ code: LocaleCode; expected: string }> = [
      { code: "en", expected: "Save" },
      { code: "ro", expected: "Salvează" },
      { code: "de", expected: "Speichern" },
      { code: "fr", expected: "Enregistrer" },
      { code: "es", expected: "Guardar" },
      { code: "pl", expected: "Zapisz" },
    ]

    for (const { code, expected } of testCases) {
      act(() => {
        result.current.setLocale(code)
      })
      expect(result.current.t("common.save")).toBe(expected)
    }
  })

  // --- Locale change order independence ------------------------

  it("t function does not mix translations between locales", () => {
    const { result } = renderLocaleHook()

    act(() => { result.current.setLocale("ro") })
    expect(result.current.t("common.save")).toBe("Salvează")
    expect(result.current.t("common.cancel")).toBe("Anulează")

    act(() => { result.current.setLocale("en") })
    expect(result.current.t("common.save")).toBe("Save")
    expect(result.current.t("common.cancel")).toBe("Cancel")

    act(() => { result.current.setLocale("ro") })
    expect(result.current.t("common.save")).toBe("Salvează")
  })
})
