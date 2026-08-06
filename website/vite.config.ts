/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import vike from 'vike/plugin'
import path from 'node:path'

export default defineConfig({
  plugins: [react(), tailwindcss(), vike()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    open: true,
    proxy: {
      '/api': {
        target: 'https://api.operionerp.xyz',
        changeOrigin: true,
        secure: true,
      },
    },
  },
  // `vite preview` defaults to :4173 — pin it to :3000 so Playwright's
  // baseURL matches the production-build webServer.
  preview: {
    port: 3000,
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/__tests__/setup.ts', './src/test-setup.ts'],
    css: true,
    exclude: ['e2e/**', 'node_modules/**', 'Calculator logistica/**', '**/node_modules/**'],
    coverage: {
      provider: 'v8',
      // Thresholds per S-Grade blueprint §16.1. NOTE: as of the 2026-08-02 audit run the
      // repo sits at ~56% statements / ~41% branches overall, so `npm run test:coverage`
      // is expected to FAIL (also currently red from parallel-lane WIP). These are the
      // target gates — tighten coverage, do NOT loosen thresholds to make CI green.
      thresholds: {
        statements: 80,
        branches: 75,
        functions: 80,
        lines: 80,
        // Per-directory overrides for the higher-stakes layers (blueprint §16.1)
        'src/lib/**': { statements: 90, branches: 85 },
        'src/services/queries.ts': { statements: 85 },
        'src/contexts/auth-provider.tsx': { statements: 90, branches: 85 },
      },
    },
  },
})
