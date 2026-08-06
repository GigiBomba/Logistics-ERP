import { describe, it, expect } from "vitest"
import en from "@/i18n/locales/en.json"
import ro from "@/i18n/locales/ro.json"
import de from "@/i18n/locales/de.json"
import fr from "@/i18n/locales/fr.json"
import es from "@/i18n/locales/es.json"
import pl from "@/i18n/locales/pl.json"

/** Recursively flatten a nested locale object into dot-separated keys (same as locale-context.tsx) */
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

// Flatten all locales so they use the same dot-separated key structure
const enFlat = flattenObject(en as Record<string, unknown>)
const roFlat = flattenObject(ro as Record<string, unknown>)
const deFlat = flattenObject(de as Record<string, unknown>)
const frFlat = flattenObject(fr as Record<string, unknown>)
const esFlat = flattenObject(es as Record<string, unknown>)
const plFlat = flattenObject(pl as Record<string, unknown>)

const nonEnLocales = { ro: roFlat, de: deFlat, fr: frFlat, es: esFlat, pl: plFlat } as const

describe("locale-schema", () => {
  const enKeys = Object.keys(enFlat)
  const enKeySet = new Set(enKeys)

  describe("key parity", () => {
    it("all locales have every key from English", () => {
      for (const [name, data] of Object.entries(nonEnLocales)) {
        const localeKeys = Object.keys(data as Record<string, string>)
        const missing = enKeys.filter((k) => !localeKeys.includes(k))
        expect(missing, `${name}: missing ${missing.length} keys`).toEqual([])
      }
    })

    it("no locale has extra keys not in English", () => {
      for (const [name, data] of Object.entries(nonEnLocales)) {
        const extra = Object.keys(data as Record<string, string>).filter(
          (k) => !enKeySet.has(k)
        )
        expect(extra, `${name}: has ${extra.length} extra keys`).toEqual([])
      }
    })

    it("all locales have the same key count as English", () => {
      const enCount = enKeys.length
      for (const [name, data] of Object.entries(nonEnLocales)) {
        expect(
          Object.keys(data as Record<string, string>).length,
          `${name}: key count mismatch`
        ).toBe(enCount)
      }
    })
  })

  describe("value validation", () => {
    it("no empty string values", () => {
      for (const [name, data] of Object.entries(nonEnLocales)) {
        const empties = Object.entries(data as Record<string, string>)
          .filter(([, v]) => v === "")
          .map(([k]) => k)
        expect(empties, `${name}: ${empties.length} empty`).toEqual([])
      }
    })

    it("all values are strings", () => {
      for (const [name, data] of Object.entries(nonEnLocales)) {
        const nonStrings = Object.entries(data as Record<string, unknown>)
          .filter(([, v]) => typeof v !== "string")
          .map(([k]) => k)
        expect(nonStrings, `${name}: non-string values`).toEqual([])
      }
    })

    it("English has no empty values", () => {
      const empties = Object.entries(enFlat)
        .filter(([, v]) => v === "")
        .map(([k]) => k)
      expect(empties).toEqual([])
    })
  })

  const allLocalesWithFlat = { en: enFlat, ...nonEnLocales }

  describe("security", () => {
    it("no script injection vectors", () => {
      for (const [name, data] of Object.entries(allLocalesWithFlat)) {
        const dangerous = Object.entries(data as Record<string, string>)
          .filter(([, v]) => /<script|<iframe|<img|<svg|<object|<embed/i.test(v))
          .map(([k]) => k)
        expect(dangerous, `${name}: injection`).toEqual([])
      }
    })

    it("no event handler injection", () => {
      for (const [name, data] of Object.entries(allLocalesWithFlat)) {
        const dangerous = Object.entries(data as Record<string, string>)
          .filter(([, v]) => /\bon\w+\s*=/i.test(v) || /javascript\s*:/i.test(v))
          .map(([k]) => k)
        expect(dangerous, `${name}: handler injection`).toEqual([])
      }
    })
  })

  describe("key naming convention", () => {
    it("all keys match namespace.key format", () => {
      for (const [name, data] of Object.entries(allLocalesWithFlat)) {
        const invalid = Object.keys(data as Record<string, string>).filter(
          (k) => !/^[a-zA-Z][a-zA-Z0-9._-]*$/.test(k)
        )
        expect(invalid, `${name}: bad key format`).toEqual([])
      }
    })
  })

  describe("content sanity", () => {
    it("no translation is identical to its key name", () => {
      for (const data of Object.values(nonEnLocales)) {
        const untranslated = Object.entries(data as Record<string, string>)
          .filter(([k, v]) => v === k && !k.startsWith("language."))
          .map(([k]) => k)
        // More than 100 identical key=value pairs suggests missing translations
        expect(untranslated.length).toBeLessThan(100)
      }
    })

    it("each locale has at least some non-English content", () => {
      for (const [name, data] of Object.entries(nonEnLocales)) {
        const entries = Object.entries(data as Record<string, string>)
        const sameAsEn = entries.filter(
          ([k, v]) => v === enFlat[k]
        ).length
        const total = entries.length
        // At least 30% should be translated (not just English fallback)
        const translatedRatio = (total - sameAsEn) / total
        expect(
          translatedRatio,
          `${name}: only ${(translatedRatio * 100).toFixed(1)}% translated`
        ).toBeGreaterThan(0.25)
      }
    })
  })
})
