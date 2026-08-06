import "@testing-library/jest-dom"
import { beforeAll, afterEach, afterAll, vi } from "vitest"
import { server } from "@/mocks/server"

const localStorageStore: Record<string, string> = {}

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
