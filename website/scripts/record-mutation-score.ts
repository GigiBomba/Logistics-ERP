#!/usr/bin/env node
// Extract the Stryker mutation score from its JSON report and write it to
// mutation-score.json (committed score file, see blueprint §16.1/§16.8).
//
// Stryker's `json` reporter writes the full report to:
//   reports/mutation/mutation.json   (default reportDirectory)
//
// The report is the mutation-testing-elements schema (v1) and does NOT carry a
// top-level `mutationScore` field, so the metrics are computed from the per-file
// mutant statuses exactly as Stryker's own mutation-testing-metrics package does:
//   detected = Killed + Timeout (+ RuntimeError/CompileError)
//   mutationScore = detected / (totalMutants - Ignored)
//   mutationScoreBasedOnCoveredCode = detected / (totalMutants - NoCoverage - Ignored)
//
// Usage: npx tsx scripts/record-mutation-score.ts
import { readFileSync, writeFileSync, existsSync } from "node:fs"
import { join, dirname } from "node:path"
import { fileURLToPath } from "node:url"

const __dirname = dirname(fileURLToPath(import.meta.url))
const root = join(__dirname, "..")

const reportCandidates = [
  join(root, "reports", "mutation", "mutation.json"),
  join(root, "reports", "mutation", "mutation.json.json"),
]

const reportPath = reportCandidates.find((p) => existsSync(p))

if (!reportPath) {
  console.error("❌ No Stryker JSON report found. Did the mutation run produce reports/mutation/mutation.json?")
  process.exit(1)
}

const report = JSON.parse(readFileSync(reportPath, "utf-8"))

const scoreFile = join(root, "mutation-score.json")
const prev = existsSync(scoreFile) ? JSON.parse(readFileSync(scoreFile, "utf-8")) : {}

// Tally mutant statuses across all files (statuses are the MTE v1 enum).
const DETECTED_STATUSES = new Set(["Killed", "Timeout", "RuntimeError", "CompileError"])
let totalMutants = 0
let detected = 0
let survived = 0
let noCoverage = 0
let ignored = 0

interface MutantEntry {
  status: string
}
interface ReportFile {
  mutants: MutantEntry[]
}
const reportFiles = report.files as Record<string, ReportFile>

for (const file of Object.values(reportFiles)) {
  for (const mutant of file.mutants) {
    totalMutants++
    if (DETECTED_STATUSES.has(mutant.status)) detected++
    else if (mutant.status === "Survived") survived++
    else if (mutant.status === "NoCoverage") noCoverage++
    else if (mutant.status === "Ignored") ignored++
  }
}

const round = (n: number) => Math.round(n * 100) / 100
const denomAll = totalMutants - ignored
const denomCovered = totalMutants - noCoverage - ignored

const score = {
  schemaVersion: report.schemaVersion ?? 1,
  mutationScore: denomAll > 0 ? round((detected / denomAll) * 100) : null,
  mutationScoreBasedOnCoveredCode: denomCovered > 0 ? round((detected / denomCovered) * 100) : null,
  totalMutants,
  totalDetected: detected,
  // Undetected-but-covered only — NoCoverage is a separate status and is tracked
  // under totalNoCoverage (it is neither detected nor survived).
  totalUndetected: survived,
  totalNoCoverage: noCoverage,
  lastRun: new Date().toISOString(),
  breakThreshold: prev.breakThreshold ?? 50,
  previousScore: prev.mutationScore ?? null,
}

writeFileSync(scoreFile, JSON.stringify(score, null, 2) + "\n")

console.log(`✅ mutation-score.json updated: ${score.mutationScore ?? "n/a"}% (covered-code: ${score.mutationScoreBasedOnCoveredCode ?? "n/a"}%)`)
