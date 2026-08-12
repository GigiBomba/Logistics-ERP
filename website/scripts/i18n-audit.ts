#!/usr/bin/env node
import { readFileSync, readdirSync } from "node:fs"
import { join, dirname } from "node:path"
import { fileURLToPath } from "node:url"

const __dirname = dirname(fileURLToPath(import.meta.url))
const localesDir = join(__dirname, "..", "src", "i18n", "locales")

function flattenKeys(obj: Record<string, unknown>, prefix = ""): string[] {
  const keys: string[] = []
  for (const [key, value] of Object.entries(obj)) {
    const fullKey = prefix ? `${prefix}.${key}` : key
    if (value && typeof value === "object" && !Array.isArray(value)) {
      keys.push(...flattenKeys(value as Record<string, unknown>, fullKey))
    } else {
      keys.push(fullKey)
    }
  }
  return keys
}

// Read en.json as source of truth
const enPath = join(localesDir, "en.json")
const enKeys = flattenKeys(JSON.parse(readFileSync(enPath, "utf-8")))

console.log(`\n📊 i18n Audit Report`)
console.log(`Source: en.json (${enKeys.length} keys)\n`)

let hasErrors = false

// Check each locale
for (const file of readdirSync(localesDir).sort()) {
  if (file === "en.json") continue
  if (!file.endsWith(".json")) continue

  const localePath = join(localesDir, file)
  const localeData = JSON.parse(readFileSync(localePath, "utf-8"))
  const localeKeys = flattenKeys(localeData)
  const localeName = file.replace(".json", "").toUpperCase()

  const missingKeys = enKeys.filter((k) => !localeKeys.includes(k))
  const extraKeys = localeKeys.filter((k) => !enKeys.includes(k))
  const pct = ((localeKeys.length / enKeys.length) * 100).toFixed(1)

  console.log(`\n${localeName}: ${localeKeys.length}/${enKeys.length} keys (${pct}%)`)

  if (missingKeys.length > 0) {
    console.log(`  ❌ Missing: ${missingKeys.length} keys`)
    missingKeys.slice(0, 10).forEach((k) => console.log(`    - ${k}`))
    if (missingKeys.length > 10) {
      console.log(`    ... and ${missingKeys.length - 10} more`)
    }
  }
  if (extraKeys.length > 0) {
    console.log(`  ⚠️  Extra (not in en.json): ${extraKeys.length}`)
    extraKeys.slice(0, 5).forEach((k) => console.log(`    - ${k}`))
  }

  if (Number.parseFloat(pct) < 95) {
    hasErrors = true
    console.log(`  ❌ FAIL: Below 95% threshold`)
  } else {
    console.log(`  ✅ PASS`)
  }
}

console.log(`\n${hasErrors ? "❌ AUDIT FAILED" : "✅ ALL LOCALES PASS"}\n`)
process.exit(hasErrors ? 1 : 0)
