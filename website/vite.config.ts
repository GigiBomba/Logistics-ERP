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
  build: {
    // Production bundles ship without sourcemaps (explicit; matches the
    // default and keeps the shipped payload lean).
    sourcemap: false,
    // Vite 8 / Rolldown: split stable third-party vendors into dedicated
    // chunks so they can be cached independently and don't bloat the shared
    // app chunk.
    //
    // NOTE: Vite 8 silently discards `build.rollupOptions.output.manualChunks`
    // return values (vitejs/vite#23153), so we use the Rolldown-native
    // `codeSplitting.groups` mechanism, which is what Vite 8's migration guide
    // (and Vike's build plugin) reads. `[\\/]` matches the path separator on
    // both POSIX and Windows (module ids arrive with forward slashes).
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            {
              name: 'vendor-react',
              test: /node_modules[\\/](react|react-dom|react-router|react-router-dom|scheduler)[\\/]/,
              priority: 30,
            },
            {
              name: 'vendor-query',
              test: /node_modules[\\/]@tanstack[\\/]/,
              priority: 20,
            },
            {
              name: 'vendor-motion',
              test: /node_modules[\\/]motion[\\/]/,
              priority: 20,
            },
            {
              name: 'vendor-axios',
              test: /node_modules[\\/]axios[\\/]/,
              priority: 20,
            },
          ],
        },
      },
    },
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
