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