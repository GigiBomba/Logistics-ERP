import { type ReactElement } from "react"
import { MemoryRouter, type MemoryRouterProps } from "react-router"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, type RenderOptions } from "@testing-library/react"
import { HelmetProvider } from "react-helmet-async"
import type { ReactNode } from "react"
import { LocaleProvider } from "@/i18n/locale-context"

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0 },
      mutations: { retry: false },
    },
  })
}

interface WrapperOptions {
  initialEntries?: MemoryRouterProps["initialEntries"]
  queryClient?: QueryClient
  withLocale?: boolean
}

/** Minimal wrapper — add ThemeProvider/AuthProvider per-test via mock wrappers. */
export function createWrapper({ initialEntries = ["/"], queryClient, withLocale = true }: WrapperOptions = {}) {
  const qc = queryClient ?? createTestQueryClient()

  function TestWrapper({ children }: { children: ReactNode }) {
    let content = children
    if (withLocale) {
      content = <LocaleProvider>{content}</LocaleProvider>
    }
    return (
      <HelmetProvider>
        <QueryClientProvider client={qc}>
          <MemoryRouter initialEntries={initialEntries}>
            {content}
          </MemoryRouter>
        </QueryClientProvider>
      </HelmetProvider>
    )
  }

  return { wrapper: TestWrapper, queryClient: qc }
}

export function renderWithProviders(
  ui: ReactElement,
  options?: WrapperOptions & Omit<RenderOptions, "wrapper">
) {
  const { wrapper, queryClient } = createWrapper(options)
  return { ...render(ui, { wrapper, ...options }), queryClient }
}

export function createMockAuthUser(overrides = {}) {
  return {
    id: "user-1",
    email: "test@operion.com",
    role: "dispatcher" as const,
    is_admin: false,
    company_id: 1,
    display_name: "Test User",
    name: "Test User",
    subscription_tier: "starter" as const,
    email_verified: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-06-01T00:00:00Z",
    ...overrides,
  }
}

export function createMockAuthContext(overrides = {}) {
  return {
    user: null,
    isLoading: false,
    isAuthenticated: false,
    isAdmin: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    refreshUser: vi.fn(),
    updateUser: vi.fn(),
    ...overrides,
  }
}

export function createMockThemeContext(overrides = {}) {
  return {
    theme: "light" as const,
    resolvedTheme: "light" as const,
    setTheme: vi.fn(),
    ...overrides,
  }
}

export * from "@testing-library/react"
export { renderWithProviders as render }
