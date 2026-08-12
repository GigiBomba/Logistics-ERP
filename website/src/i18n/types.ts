export type LocaleCode = "en" | "ro" | "de" | "fr" | "es" | "pl"

export interface LocaleInfo {
  code: LocaleCode
  name: string
  nativeName: string
  flag: string
}

export const SUPPORTED_LOCALES: LocaleInfo[] = [
  { code: "en", name: "English", nativeName: "English", flag: "🇬🇧" },
  { code: "ro", name: "Romanian", nativeName: "Română", flag: "🇷🇴" },
  { code: "de", name: "German", nativeName: "Deutsch", flag: "🇩🇪" },
  { code: "fr", name: "French", nativeName: "Français", flag: "🇫🇷" },
  { code: "es", name: "Spanish", nativeName: "Español", flag: "🇪🇸" },
  { code: "pl", name: "Polish", nativeName: "Polski", flag: "🇵🇱" },
]

export const DEFAULT_LOCALE: LocaleCode = "en"
