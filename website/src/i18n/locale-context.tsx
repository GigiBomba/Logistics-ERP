import { createContext, useContext, useState, useCallback, useMemo, type ReactNode } from "react"
import type { LocaleCode } from "@/i18n/types"
import { DEFAULT_LOCALE, SUPPORTED_LOCALES } from "@/i18n/types"

import en from "@/i18n/locales/en.json"
import ro from "@/i18n/locales/ro.json"
import de from "@/i18n/locales/de.json"
import fr from "@/i18n/locales/fr.json"
import es from "@/i18n/locales/es.json"
import pl from "@/i18n/locales/pl.json"

const translations: Record<LocaleCode, Record<string, string>> = {
  en: en as Record<string, string>,
  ro: ro as Record<string, string>,
  de: de as Record<string, string>,
  fr: fr as Record<string, string>,
  es: es as Record<string, string>,
  pl: pl as Record<string, string>,
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
