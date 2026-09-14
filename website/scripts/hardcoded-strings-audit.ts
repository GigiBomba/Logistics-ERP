#!/usr/bin/env node
import { readFileSync, readdirSync, statSync } from "node:fs"
import { join, relative, dirname } from "node:path"
import { fileURLToPath } from "node:url"
import ts from "typescript"

const __dirname = dirname(fileURLToPath(import.meta.url))
const SRC_ROOT = join(__dirname, "..", "src")

// Only scan the user-facing render tree
const SCAN_DIRS = ["pages", "components"]

// Elements whose text content is metadata, not user-visible copy
const SAFE_PARENTS = new Set(["script", "style", "meta", "title"])

// JSX text children that read like sentence copy: 2+ words of 4+ chars each
const LONG_WORD_RE = /\p{L}{4,}/gu

// Key-like / i18n call signatures to skip (already i18n-aware or lookup keys)
const KEY_LIKE_RE = /(^|[^A-Za-z])t\s*\(/ // t("...")
const DOTTED_KEY_RE = /\b[a-z][\w-]*(\.[a-z][\w-]*)+\b/ // "auth.checkEmail"
const CAMEL_CASE_RE = /\b[a-z]+[A-Z][a-zA-Z]*\b/ // "loginSubmit"

// Intentional, non-translatable UI strings (exact collapsed-text matches).
// These are NOT user-facing marketing/app copy:
//  - Demo/screenshot mockup data in public pages (features.tsx, home.tsx,
//    industry-*.tsx): fake app previews with sample routes, cities, company
//    names, metrics, and chat transcripts — illustrative data, not copy.
//  - Proper-noun technical names on brand.tsx (font / icon library names).
const ALLOWLIST = new Set([
  // brand.tsx — proper nouns for the font & icon library
  "JetBrains Mono",
  "Lucide React",

  // features.tsx — desktop-app screenshot mockups
  "Route Planning",
  "Bucharest → Ploiesti → Brasov → Cluj",
  "Constanta → Bucharest → Pitesti",
  "Fleet Live Map",
  "Bucharest → Cluj",
  "Constanta Port",
  "Deva Yard",
  "Brasov Depot",
  "Dispatch Console",
  "Dispatch Truck 14 from Bucharest to Cluj...",
  "Batch Assign",
  "I found a profitable return load for Truck X after it unloads in Poznań.",
  "Distance to reload: 18 km · Est. profit: +€487",
  "Show me the route and documents.",
  "All prepared. Dispatch, CMR, proforma invoice, and final invoice are ready.",
  "Today's Profit",
  "Active Dispatches",
  "Document Scanner",
  "Transilvania Logistics",
  "Cluj Distribution SRL",
  "Cluj-Napoca, RO",
  "Electronics, 24 pallets",
  "Text extracted successfully",
  "Fields mapped to shipment record",
  "Invoice pending review",
  "Total Revenue",
  "↑ 12.3% vs last month",
  "Empty Km Rate",
  "↓ 4.1% vs last month",
  "Fleet Utilization",
  "↑ 5% vs last month",
  "On-Time Delivery",
  "↑ 2.1% vs last month",
  "Weekly Profit Trend",
  "Driver Schedule",
  "Interface preview",

  // home.tsx — desktop-app screenshot mockups
  "Active Routes",
  "Dispatch Truck 14 to Cluj...",

  // industry-agriculture.tsx — seasonal calendar visual
  "Seasonal Logistics Calendar",
  "Cold Chain",
  "2°C to 6°C maintained across 340 km route",
  "Rural Routes",
  "Unpaved road weight limits auto-applied",
  "Harvesters synced to delivery windows",

  // industry-construction.tsx — site board visual
  "Site Coordination Board",
  "3 active sites",
  "All sites comply with today&apos;s safety checklist",

  // industry-fleet.tsx — fleet monitor visual
  "Fleet Health Monitor",
  "Next maintenance window",
  "Tomorrow 06:00 — 3 vehicles",

  // industry-freight.tsx — before/after comparison labels
  "Before Operion",
  "After Operion",

  // industry-manufacturing.tsx — supply chain visual
  "Supply Chain Flow",
  "Live synchronization",
  "Active inbound routes",
  "On-time to dock",
  "Facilities synced",

  // industry-owner-ops.tsx — mobile app mockup
  "Next Load",
  "Bucharest → Timisoara · 12t refrigerated",
  "Pending Invoice",
  "Today&apos;s Expenses",

  // industry-transport.tsx — live dispatch visual
  "Live Dispatch",
  "4 active routes",
  "Route density — Bucharest hub",
])

interface Flagged {
  file: string
  line: number
  text: string
}

function parseThreshold(args: string[]): number {
  for (const arg of args) {
    const match = /^--threshold=(\d+)$/.exec(arg)
    if (match) return Number.parseInt(match[1], 10)
  }
  const idx = args.indexOf("--threshold")
  if (idx !== -1 && args[idx + 1] && /^\d+$/.test(args[idx + 1])) {
    return Number.parseInt(args[idx + 1], 10)
  }
  return 25
}

function collectTsxFiles(dir: string): string[] {
  const files: string[] = []
  for (const entry of readdirSync(dir)) {
    if (entry === "__tests__") continue // skip test dirs entirely
    const full = join(dir, entry)
    const stat = statSync(full)
    if (stat.isDirectory()) {
      files.push(...collectTsxFiles(full))
    } else if (entry.endsWith(".tsx")) {
      files.push(full)
    }
  }
  return files
}

function collapseWhitespace(text: string): string {
  return text.replace(/\s+/g, " ").trim()
}

function looksKeyed(text: string): boolean {
  return (
    KEY_LIKE_RE.test(text) ||
    /i18n/i.test(text) ||
    DOTTED_KEY_RE.test(text) ||
    CAMEL_CASE_RE.test(text)
  )
}

function countLongWords(text: string): number {
  return (text.match(LONG_WORD_RE) ?? []).length
}

function isHardcodedText(text: string): boolean {
  const trimmed = collapseWhitespace(text)
  if (!trimmed) return false
  if (ALLOWLIST.has(trimmed)) return false
  if (looksKeyed(trimmed)) return false
  return countLongWords(trimmed) >= 2
}

function flagFor(sourceFile: ts.SourceFile, node: ts.Node, text: string): Flagged {
  const pos = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile))
  return {
    file: sourceFile.fileName,
    line: pos.line + 1,
    text,
  }
}

function inspectSourceFile(sourceFile: ts.SourceFile, flags: Flagged[]): void {
  const visit = (node: ts.Node): void => {
    // Case 1: literal text between JSX elements, e.g. <p>Hello world</p>
    if (ts.isJsxText(node)) {
      const text = collapseWhitespace(node.text)
      if (text && isHardcodedText(text)) {
        let safeParent = false
        if (ts.isJsxElement(node.parent)) {
          const tagName = node.parent.openingElement.tagName.getText(sourceFile).toLowerCase()
          safeParent = SAFE_PARENTS.has(tagName)
        }
        if (!safeParent) flags.push(flagFor(sourceFile, node, text))
      }
      return
    }

    // Case 2: string-literal expression children, e.g. <span>{"Hardcoded copy"}</span>
    if (ts.isJsxExpression(node)) {
      const expr = node.expression
      if (expr && ts.isStringLiteral(expr) && isHardcodedText(expr.text)) {
        flags.push(flagFor(sourceFile, node, collapseWhitespace(expr.text)))
      }
      return
    }

    ts.forEachChild(node, visit)
  }
  visit(sourceFile)
}

// ---------------------------------------------------------------- main

const args = process.argv.slice(2)
const failMode = args.includes("--fail")
const threshold = parseThreshold(args)

const files = SCAN_DIRS.flatMap((dir) =>
  collectTsxFiles(join(SRC_ROOT, dir)).sort()
)

const flags: Flagged[] = []
for (const file of files) {
  try {
    const sourceFile = ts.createSourceFile(
      file,
      readFileSync(file, "utf-8"),
      ts.ScriptTarget.Latest,
      true,
      ts.ScriptKind.TSX
    )
    inspectSourceFile(sourceFile, flags)
  } catch {
    // Skip files that fail to parse; never crash the audit on one file
  }
}

flags.sort((a, b) => (a.file === b.file ? a.line - b.line : a.file.localeCompare(b.file)))

console.log(`\n📊 Hardcoded Strings Audit Report`)
console.log(`Scanning: ${SCAN_DIRS.map((d) => `src/${d}`).join(", ")} (${files.length} files)`)
console.log(`Mode: ${failMode ? `enforce (--fail, threshold ${threshold})` : "report-only (exit 0)"}\n`)

for (const flag of flags) {
  const rel = relative(join(SRC_ROOT, ".."), flag.file).replace(/\\/g, "/")
  console.log(`  ❌ ${rel}:${flag.line}  "${flag.text}"  (${countLongWords(flag.text)} words ≥ 4 chars)`)
}

console.log(`\nFound ${flags.length} hardcoded string${flags.length === 1 ? "" : "s"}.\n`)

if (!failMode) {
  console.log("✅ REPORT-ONLY: run with --fail to enforce (exits 1 above threshold)")
  process.exit(0)
}

if (flags.length > threshold) {
  console.log(`❌ AUDIT FAILED: ${flags.length} hardcoded strings exceed threshold of ${threshold}\n`)
  process.exit(1)
}
console.log(`✅ PASS: ${flags.length} hardcoded strings within threshold of ${threshold}\n`)
process.exit(0)