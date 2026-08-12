#!/usr/bin/env node
/**
 * i18n sync script — adds missing keys from en.json to all other locales
 * using English fallback values.
 *
 * Usage: npx tsx scripts/i18n-sync.ts
 */
import { readFileSync, writeFileSync, readdirSync } from "node:fs"
import { join, dirname } from "node:path"
import { fileURLToPath } from "node:url"

const __dirname = dirname(fileURLToPath(import.meta.url))
const localesDir = join(__dirname, "..", "src", "i18n", "locales")

function flattenKeysWithValues(
  obj: Record<string, unknown>,
  prefix = ""
): Array<{ key: string; value: unknown }> {
  const entries: Array<{ key: string; value: unknown }> = []
  for (const [key, value] of Object.entries(obj)) {
    const fullKey = prefix ? `${prefix}.${key}` : key
    if (value && typeof value === "object" && !Array.isArray(value)) {
      entries.push(...flattenKeysWithValues(value as Record<string, unknown>, fullKey))
    } else {
      entries.push({ key: fullKey, value })
    }
  }
  return entries
}

function setNestedValue(obj: Record<string, unknown>, keyPath: string, value: unknown): void {
  const parts = keyPath.split(".")
  let current = obj
  for (let i = 0; i < parts.length - 1; i++) {
    if (!current[parts[i]] || typeof current[parts[i]] !== "object") {
      current[parts[i]] = {}
    }
    current = current[parts[i]] as Record<string, unknown>
  }
  current[parts[parts.length - 1]] = value
}

function sortKeys(obj: Record<string, unknown>): Record<string, unknown> {
  const sorted: Record<string, unknown> = {}
  for (const key of Object.keys(obj).sort()) {
    const val = obj[key]
    if (val && typeof val === "object" && !Array.isArray(val)) {
      sorted[key] = sortKeys(val as Record<string, unknown>)
    } else {
      sorted[key] = val
    }
  }
  return sorted
}

// Read en.json as source of truth
const enPath = join(localesDir, "en.json")
const enData = JSON.parse(readFileSync(enPath, "utf-8")) as Record<string, unknown>
const enEntries = flattenKeysWithValues(enData)
const enKeys = enEntries.map((e) => e.key)

// Process each locale
for (const file of readdirSync(localesDir).sort()) {
  if (file === "en.json") continue
  if (!file.endsWith(".json")) continue

  const localePath = join(localesDir, file)
  const localeData = JSON.parse(readFileSync(localePath, "utf-8")) as Record<string, unknown>

  // Find missing keys
  const localeEntries = flattenKeysWithValues(localeData)
  const localeKeys = localeEntries.map((e) => e.key)
  const missingEntries = enEntries.filter((e) => !localeKeys.includes(e.key))

  if (missingEntries.length === 0) {
    console.log(`✓ ${file} is up to date`)
    continue
  }

  // Add missing keys with English values as fallback
  for (const { key, value } of missingEntries) {
    setNestedValue(localeData, key, value)
  }

  // Sort keys and write
  const sorted = sortKeys(localeData)
  writeFileSync(localePath, JSON.stringify(sorted, null, 2) + "\n")
  console.log(`✎ ${file}: added ${missingEntries.length} missing keys (English fallback)`)
}

console.log("\n✅ i18n sync complete — all locales now match en.json")
