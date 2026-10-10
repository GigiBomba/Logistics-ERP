import { vi } from "vitest"

/**
 * Shared factory for tests that mock `@/i18n/locale-context` with an identity
 * translator: every `t("some.key")` call returns the key itself, while the rest
 * of the real module (LocaleProvider, …) is preserved.
 *
 * Use it from a test file with a *lazy* dynamic import so the hoisted
 * `vi.mock` call never touches an uninitialized binding:
 *
 * ```ts
 * vi.mock("@/i18n/locale-context", () =>
 *   import("@/__tests__/mocks/locale-context").then((m) => m.identityLocaleMock()),
 * )
 * ```
 *
 * Tests that need real translations (or a spy on `setLocale`) keep their own
 * bespoke factory — do not force them through this helper.
 */
export async function identityLocaleMock() {
  const actual = await vi.importActual<typeof import("@/i18n/locale-context")>("@/i18n/locale-context")
  return {
    ...actual,
    useLocale: () => ({
      t: (key: string) => key,
    }),
  }
}
