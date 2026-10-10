import "@testing-library/jest-dom"
import { beforeAll, afterEach, afterAll, vi } from "vitest"
import { server } from "@/mocks/server"

const localStorageStore: Record<string, string> = {}

// ─── Canonical motion/react mock (shared across the suite) ───────────────────
// Renders the real element for any `motion.<tag>` (props passed through),
// passes children straight through AnimatePresence, and returns `true` from
// useInView. Test files may still override it with their own
// `vi.mock("motion/react", …)` — the test-file mock wins over this one.
// NOTE: this file is .ts (no JSX), so the factory uses createElement.
// IMPORTANT: components are cached per tag — returning a fresh component on
// every `motion.x` access would make React unmount/remount the subtree on each
// render (stale DOM refs, lost local state, broken fireEvent/userEvent flows).
vi.mock("motion/react", async () => {
  const { createElement, Fragment } = await import("react")
  const cache = new Map<string, (props: Record<string, unknown>) => unknown>()
  const componentFor = (tag: string): ((props: Record<string, unknown>) => unknown) => {
    let component = cache.get(tag)
    if (!component) {
      const Tag = tag
      component = (props: Record<string, unknown> = {}) => createElement(Tag, props, props.children)
      cache.set(tag, component)
    }
    return component
  }
  return {
    motion: new Proxy(
      {},
      {
        get: (_target, tag) => (typeof tag === "symbol" ? undefined : componentFor(String(tag))),
      }
    ),
    AnimatePresence: ({ children }: { children?: unknown }) => createElement(Fragment, null, children),
    useInView: () => true,
  }
})

beforeAll(() => {
  server.listen({ onUnhandledRequest: "warn" })

  // Mock matchMedia
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  })

  // Mock IntersectionObserver (must be a constructor)
  class MockIntersectionObserver {
    constructor() {}
    observe = vi.fn()
    unobserve = vi.fn()
    disconnect = vi.fn()
  }
  Object.defineProperty(window, "IntersectionObserver", {
    writable: true,
    value: MockIntersectionObserver,
  })

  // Mock scrollIntoView
  Element.prototype.scrollIntoView = vi.fn()

  // Mock localStorage
  vi.stubGlobal("localStorage", {
    getItem: vi.fn((key: string) => localStorageStore[key] ?? null),
    setItem: vi.fn((key: string, value: string) => {
      localStorageStore[key] = value
    }),
    removeItem: vi.fn((key: string) => {
      delete localStorageStore[key]
    }),
    clear: vi.fn(() => {
      Object.keys(localStorageStore).forEach((k) => delete localStorageStore[k])
    }),
    get length() {
      return Object.keys(localStorageStore).length
    },
    key: vi.fn((index: number) => Object.keys(localStorageStore)[index] ?? null),
  })

  // Mock console.error to suppress act() warnings in tests
  vi.spyOn(console, "error").mockImplementation(() => {})
})

afterEach(() => server.resetHandlers())
afterAll(() => server.close())
