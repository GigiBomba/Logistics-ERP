import { defineConfig } from "vitest/config"
import base from "../../../vite.config"

// Stryker-scoped vitest config: identical to the app's vite.config.ts test
// config, EXCEPT the DryRun scope is pinned to the test files that exercise
// the REAL (non-mocked) mutated modules: src/lib/*, services/queries.ts,
// contexts/auth-provider, contexts/theme-provider.
//
// Stryker's `related` mode was disabled (stryker.conf.json vitest.related =
// false) because its module-graph resolution silently dropped direct unit
// tests for src/lib (utils/consent/permissions/trial/sw-register) and the
// theme-provider integration test, producing a bogus 0.00 score. Pinning
// `include` gives the DryRun a complete, deterministic coverage set.
//
// All other test files either mock the mutated modules (contributing no
// mutation coverage) or are unrelated to the mutated files, so excluding them
// does not change the mutation score.
const baseCfg = base as { test?: Record<string, unknown> }

const MUTATION_SCOPE = [
  "src/__tests__/unit/lib/consent.test.ts",
  "src/__tests__/unit/lib/permissions.test.ts",
  "src/__tests__/unit/lib/sw-register.test.ts",
  "src/__tests__/unit/lib/trial.test.ts",
  "src/__tests__/unit/lib/utils.test.ts",
  "src/__tests__/integration/components/shared/cookie-consent-banner.test.tsx",
  "src/__tests__/integration/services/queries.test.tsx",
  "src/__tests__/integration/auth-provider.test.tsx",
  "src/__tests__/integration/theme-provider.test.tsx",
  "src/__tests__/integration/admin/blog-mutations.test.tsx",
  "src/__tests__/components/shared/trial-banner.test.tsx",
]

export default defineConfig({
  ...baseCfg,
  test: {
    ...(baseCfg.test ?? {}),
    include: [...MUTATION_SCOPE],
    exclude: [...((baseCfg.test?.exclude as string[]) ?? [])],
  },
})
