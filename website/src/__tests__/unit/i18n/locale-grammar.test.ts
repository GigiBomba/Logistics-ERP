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

interface LocaleEntry {
  key: string
  value: string
}

type GrammarRule = (key: string, enValue: string, translatedValue: string) => string | null

// ─── Helpers ────────────────────────────────────────────────────────────────

function entries(data: Record<string, string>): LocaleEntry[] {
  return Object.entries(data).map(([key, value]) => ({ key, value }))
}

function placeholderVars(s: string): Set<string> {
  const vars = new Set<string>()
  const re = /\{(\w+)\}/g
  let m: RegExpExecArray | null
  while ((m = re.exec(s)) !== null) {
    vars.add(m[1])
  }
  return vars
}

function terminalPunct(s: string): string {
  const trimmed = s.trim()
  if (trimmed.endsWith("...")) return "..."
  if (trimmed.endsWith("…")) return "…"
  const last = trimmed.at(-1) ?? ""
  if (last === "." || last === "!" || last === "?" || last === ":" || last === ";") return last
  return ""
}

/** Check for balanced pairs — returns first unbalanced delimiter or null */
function checkBalanced(s: string): string | null {
  const pairs: [string, string, string][] = [
    ["(", ")", "parenthesis"],
    ["[", "]", "bracket"],
    ["{", "}", "curly brace"],
    ["«", "»", "guillemet"],
  ]
  for (const [open, close, name] of pairs) {
    const opens = (s.match(new RegExp(`\\${open}`, "g")) || []).length
    const closes = (s.match(new RegExp(`\\${close}`, "g")) || []).length
    if (opens !== closes) return `unbalanced ${name}: ${opens}×${open} vs ${closes}×${close}`
  }
  return null
}

/** Guard: skip missing translations without throwing */
function trVal(data: Record<string, string>, key: string): string | undefined {
  return (data as Record<string, string>)[key]
}

// ─── Language-Specific Rule Sets ─────────────────────────────────────────────

const localeRules: Record<string, GrammarRule[]> = {
  pl: [
    // "Operan" or "Operaion" instead of "Operion" — known typos
    (_, __, plVal) => {
      if (/\bOperan\b/i.test(plVal)) return `"Operan" should be "Operion"`
      if (/\bOperaion\b/i.test(plVal)) return `"Operaion" should be "Operion"`
      if (/\bOperację\b/i.test(plVal)) return `"Operację" should be "Operion" (nominative)`
      return null
    },
  ],

  fr: [
    // "de le/les" contraction: flag only when le/les is an article (not a pronoun).
    // Article: followed by noun. Pronoun: followed by verb infinitive.
    (_, _enVal, frVal) => {
      const re = /de (le|les) /gi
      let m: RegExpExecArray | null
      while ((m = re.exec(frVal)) !== null) {
        // Get the next word, stripping trailing punctuation
        const afterMatch = frVal.slice(m.index + m[0].length).match(/^([a-zA-ZÀ-ÖØ-öø-ÿĀ-ž]+)/)
        const after = afterMatch?.[1]
        if (!after) continue
        // If followed by a verb infinitive → it's a pronoun → skip
        if (/(?:er|ir|re|oir)$/i.test(after)) continue
        // If followed by a vowel → already "de l'" → skip
        if (/^[aeiouhAEIOUH]/i.test(after)) continue
        const form = m[1]
        const suggestion = form === "le" ? "du" : "des"
        return `"de ${form}" should be "${suggestion}" (contraction required before noun)`
      }
      return null
    },
    // "le" / "la" before vowel → "l'" — only when "le/la" is a standalone word
    // (not a hyphenated imperative suffix like "Traitez-le")
    (_, __, frVal) => {
      for (let i = 0; i < frVal.length; i++) {
        const word = frVal.slice(i, i + 2)
        if (word !== "le" && word !== "la") continue
        // Must be start of string OR preceded by a space (not a hyphen)
        if (!(i === 0 || frVal[i - 1] === " ")) continue
        // The character immediately after "le"/"la" must not be a letter,
        // confirming it's a standalone word (not start of a longer word like "legal")
        const charAfterWord = frVal[i + 2]
        if (charAfterWord && /[a-zA-ZÀ-ÖØ-öø-ÿĀ-ž]/.test(charAfterWord)) continue
        // Skip spaces to find the next word's first letter
        let j = i + 2
        while (j < frVal.length && frVal[j] === " ") j++
        const nextChar = frVal[j]
        if (nextChar && /[aeiouhAEIOUH]/.test(nextChar)) {
          const afterWord = frVal.slice(j).match(/^([a-zA-ZÀ-ÖØ-öø-ÿĀ-ž]+)/)?.[1] ?? "?"
          return `"${word}" should be "l'" before vowel: "${word} ${afterWord}"`
        }
      }
      return null
    },
  ],

  es: [
    // Spanish requires opening ¿ and ¡
    (_, enVal, esVal) => {
      // Skip untranslated values (still English) — grammar rules don't apply
      if (enVal === esVal) return null
      const trimmed = esVal.trim()
      if (trimmed.endsWith("?") && !trimmed.startsWith("¿")) {
        return `Missing opening ¿ for question ending with ?`
      }
      if (trimmed.endsWith("!") && !trimmed.startsWith("¡")) {
        return `Missing opening ¡ for exclamation ending with !`
      }
      return null
    },
  ],

  ro: [
    // "si" without diacritic should be "și" (the Romanian word for "and")
    // Use Unicode-aware boundaries: flag only when "si" stands alone, not inside
    // words like "găsiți" where diacritic neighbors make JS \b fire incorrectly
    (_, __, roVal) => {
      // Check "si" as a standalone word: surrounded by non-letter chars or edges
      if (/(?<![a-zA-ZăâîșțĂÂÎȘȚ])si(?![a-zA-ZăâîșțĂÂÎȘȚ])/i.test(roVal)) {
        return `"si" should be "și" with diacritic (comma below)`
      }
      return null
    },
  ],
}

// ─── Main test suite ────────────────────────────────────────────────────────

const nonEnLocales: Record<string, Record<string, string>> = { ro: roFlat, de: deFlat, fr: frFlat, es: esFlat, pl: plFlat }
const enEntries = entries(enFlat)

describe("locale-grammar", () => {
  // ── 1. Placeholder variable consistency ────────────────────────────────────
  describe("placeholder variables", () => {
    for (const [name, data] of Object.entries(nonEnLocales)) {
      it(`${name} has all {variables} found in English`, () => {
        const issues: string[] = []
        for (const { key, value: enVal } of enEntries) {
          const translatedVal = trVal(data, key)
          if (translatedVal === undefined) continue
          const enVars = placeholderVars(enVal)
          if (enVars.size === 0) continue
          const trVars = placeholderVars(translatedVal)
          const missing = [...enVars].filter((v) => !trVars.has(v))
          if (missing.length > 0) {
            issues.push(`${key}: missing {${missing.join(", ")}} in "${translatedVal}"`)
          }
        }
        expect(issues, `${name}: ${issues.length} placeholder mismatches`).toEqual([])
      })

      it(`${name} has no {variables} not in English`, () => {
        const issues: string[] = []
        for (const { key, value: enVal } of enEntries) {
          const translatedVal = trVal(data, key)
          if (translatedVal === undefined) continue
          const enVars = placeholderVars(enVal)
          const trVars = placeholderVars(translatedVal)
          const extra = [...trVars].filter((v) => !enVars.has(v))
          if (extra.length > 0) {
            issues.push(`${key}: unexpected {${extra.join(", ")}} in "${translatedVal}"`)
          }
        }
        expect(issues, `${name}: ${issues.length} unexpected placeholders`).toEqual([])
      })
    }
  })

  // ── 2. Punctuation consistency ─────────────────────────────────────────────
  describe("punctuation consistency", () => {
    for (const [name, data] of Object.entries(nonEnLocales)) {
      it(`${name} matches English terminal punctuation`, () => {
        const issues: string[] = []
        for (const { key, value: enVal } of enEntries) {
          const translatedVal = trVal(data, key)
          if (translatedVal === undefined) continue
          const enPunct = terminalPunct(enVal)
          const trPunct = terminalPunct(translatedVal)

          // Only flag if English has strong terminal punctuation (. ! ?)
          if (enPunct === "." && trPunct !== "." && trPunct !== "…" && trPunct !== "...") {
            issues.push(`${key}: English ends with "." but translation ends with "${trPunct || "none"}" — "${translatedVal}"`)
          } else if (enPunct === "!" && trPunct !== "!") {
            issues.push(`${key}: English ends with "!" but translation ends with "${trPunct || "none"}" — "${translatedVal}"`)
          } else if (enPunct === "?" && trPunct !== "?") {
            issues.push(`${key}: English ends with "?" but translation ends with "${trPunct || "none"}" — "${translatedVal}"`)
          } else if (enPunct === "..." && trPunct !== "..." && trPunct !== "…") {
            issues.push(`${key}: English ends with "..." but translation ends with "${trPunct || "none"}" — "${translatedVal}"`)
          }
        }
        expect(issues, `${name}: ${issues.length} punctuation mismatches`).toEqual([])
      })
    }
  })

  // ── 3. Whitespace & formatting hygiene ─────────────────────────────────────
  describe("whitespace and formatting", () => {
    for (const [name, data] of Object.entries(nonEnLocales)) {
      it(`${name} has no double spaces (two or more consecutive space characters)`, () => {
        const issues: string[] = []
        for (const { key, value } of entries(data as Record<string, string>)) {
          if (/  /.test(value)) {
            issues.push(`${key}: "${value}"`)
          }
        }
        expect(issues, `${name}: ${issues.length} double-space issues`).toEqual([])
      })

      it(`${name} has no leading or trailing whitespace`, () => {
        const issues: string[] = []
        for (const { key, value } of entries(data as Record<string, string>)) {
          if (value !== value.trim()) {
            issues.push(`${key}: "${value}"`)
          }
        }
        expect(issues, `${name}: ${issues.length} whitespace edge issues`).toEqual([])
      })

      it(`${name} has no empty values`, () => {
        const issues: string[] = []
        for (const { key, value } of entries(data as Record<string, string>)) {
          if (value.trim() === "") {
            issues.push(`${key}: is empty`)
          }
        }
        expect(issues, `${name}: ${issues.length} empty values`).toEqual([])
      })
    }
  })

  // ── 4. Balanced delimiters ─────────────────────────────────────────────────
  describe("balanced delimiters", () => {
    for (const [name, data] of Object.entries(nonEnLocales)) {
      it(`${name} has balanced parentheses, brackets, and quotes`, () => {
        const issues: string[] = []
        for (const { key, value } of entries(data as Record<string, string>)) {
          const result = checkBalanced(value)
          if (result) issues.push(`${key}: ${result} in "${value}"`)
        }
        expect(issues, `${name}: ${issues.length} unbalanced delimiter issues`).toEqual([])
      })
    }
  })

  // ── 5. Capitalization consistency for button/action keys ────────────────────
  describe("capitalization consistency", () => {
    const buttonPatterns = [
      /\.(save|submit|cancel|delete|create|send|download|publish|edit|close|back|next|previous)$/,
      /\.(signIn|signUp|signOut|viewAll|learnMore|getStarted|tryAgain|readMore|seeAll|showMore|showLess)$/,
    ]

    for (const [name, data] of Object.entries(nonEnLocales)) {
      it(`${name} matches English capitalization for action labels`, () => {
        const issues: string[] = []
        for (const { key, value: enVal } of enEntries) {
          if (!buttonPatterns.some((p) => p.test(key))) continue
          const translatedVal = trVal(data, key)
          if (translatedVal === undefined) continue
          const enStartUpper = /^[A-Z]/.test(enVal)
          const trStartUpper = /^[A-Z\u00C0-\u017F]/.test(translatedVal)
          if (enStartUpper && !trStartUpper) {
            issues.push(`${key}: English starts uppercase "${enVal}" but translation starts lowercase "${translatedVal}"`)
          }
          if (!enStartUpper && trStartUpper) {
            issues.push(`${key}: English starts lowercase "${enVal}" but translation starts uppercase "${translatedVal}"`)
          }
        }
        // Allow some false positives — flag if too many
        expect(issues.length, `${name}: ${issues.length} capitalization differences (first 5 shown: ${issues.slice(0, 5).join(" | ")})`).toBeLessThan(10)
      })
    }
  })

  // ── 6. Language-specific grammar rules ─────────────────────────────────────
  describe("language-specific grammar", () => {
    for (const [name, data] of Object.entries(nonEnLocales)) {
      const rules = localeRules[name]
      if (!rules || rules.length === 0) continue

      it(`${name}: no grammar rule violations`, () => {
        const issues: string[] = []
        for (const { key, value: enVal } of enEntries) {
          const translatedVal = trVal(data, key)
          if (translatedVal === undefined) continue
          for (const rule of rules) {
            const result = rule(key, enVal, translatedVal)
            if (result) issues.push(`${key}: ${result}`)
          }
        }
        expect(issues, `${name}: ${issues.length} grammar issues`).toEqual([])
      })
    }
  })

  // ── 7. English self-check (source language sanity) ─────────────────────────
  describe("English source quality", () => {
    it("has no double spaces (two consecutive spaces)", () => {
      const issues = enEntries
        .filter(({ value }) => /  /.test(value))
        .map(({ key }) => key)
      expect(issues).toEqual([])
    })

    it("has no leading/trailing whitespace", () => {
      const issues = enEntries
        .filter(({ value }) => value !== value.trim())
        .map(({ key, value }) => `${key}: "${value}"`)
      expect(issues).toEqual([])
    })
  })
})
