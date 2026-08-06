import { createContext, useContext, useState, useCallback, useMemo, type ReactNode } from "react"
import type { LocaleCode } from "@/i18n/types"
import { DEFAULT_LOCALE, SUPPORTED_LOCALES } from "@/i18n/types"

import en from "@/i18n/locales/en.json"
import ro from "@/i18n/locales/ro.json"
import de from "@/i18n/locales/de.json"
import fr from "@/i18n/locales/fr.json"
import es from "@/i18n/locales/es.json"
import pl from "@/i18n/locales/pl.json"

function flattenObject(obj: Record<string, unknown>, prefix = ""): Record<string, string> {
  let result: Record<string, string> = {}
  for (const [key, value] of Object.entries(obj)) {
    const flatKey = prefix ? `${prefix}.${key}` : key
    if (value && typeof value === "object" && !Array.isArray(value)) {
      result = { ...result, ...flattenObject(value as Record<string, unknown>, flatKey) }
    } else {
      result[flatKey] = String(value)
    }
  }
  return result
}

const translations: Record<LocaleCode, Record<string, string>> = {
  en: flattenObject(en as Record<string, unknown>),
  ro: flattenObject(ro as Record<string, unknown>),
  de: flattenObject(de as Record<string, unknown>),
  fr: flattenObject(fr as Record<string, unknown>),
  es: flattenObject(es as Record<string, unknown>),
  pl: flattenObject(pl as Record<string, unknown>),
}

interface LocaleContextValue {
  locale: LocaleCode
  setLocale: (locale: LocaleCode) => void
  t: (key: string) => string
}

const LocaleContext = createContext<LocaleContextValue | undefined>(undefined)

function getStoredLocale(): LocaleCode {
  if (typeof window === "undefined") return DEFAULT_LOCALE
  const stored = localStorage.getItem("operion-locale") as LocaleCode | null
  if (stored && SUPPORTED_LOCALES.some((l) => l.code === stored)) {
    return stored
  }
  return DEFAULT_LOCALE
}

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<LocaleCode>(getStoredLocale)

  const setLocale = useCallback((newLocale: LocaleCode) => {
    setLocaleState(newLocale)
    localStorage.setItem("operion-locale", newLocale)
  }, [])

  const t = useCallback(
    (key: string) => {
      return translations[locale][key] ?? translations[DEFAULT_LOCALE][key] ?? key
    },
    [locale]
  )

  const value = useMemo(
    () => ({ locale, setLocale, t }),
    [locale, setLocale, t]
  )

  return (
    <LocaleContext.Provider value={value}>
      {children}
    </LocaleContext.Provider>
  )
}

export function useLocale() {
  const ctx = useContext(LocaleContext)
  if (!ctx) throw new Error("useLocale must be used within LocaleProvider")
  return ctx
}
