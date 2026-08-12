#!/usr/bin/env node
import { readdirSync, existsSync } from "node:fs"
import { join, dirname } from "node:path"
import { fileURLToPath } from "node:url"

const __dirname = dirname(fileURLToPath(import.meta.url))
const uiDir = join(__dirname, "..", "src", "components", "ui")
const testDir = join(__dirname, "..", "src", "__tests__", "components", "ui")

const components = readdirSync(uiDir).filter((f) => f.endsWith(".tsx"))
let hasErrors = false

for (const component of components) {
  const testFile = component.replace(".tsx", ".test.tsx")
  const testPath = join(testDir, testFile)

  if (!existsSync(testPath)) {
    console.error(`❌ Missing test: ${testFile} for component ${component}`)
    hasErrors = true
  } else {
    console.log(`✅ ${component} → ${testFile}`)
  }
}

console.log(`\n${components.length} components checked`)
process.exit(hasErrors ? 1 : 0)
