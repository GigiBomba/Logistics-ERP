import { type ReactElement } from "react"
import { MemoryRouter, type MemoryRouterProps } from "react-router"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, type RenderOptions } from "@testing-library/react"
import { HelmetProvider } from "react-helmet-async"
import { LocaleProvider } from "@/i18n/locale-context"
import type { ReactNode } from "react"
import { vi } from "vitest"
import type { User } from "@/types"
import type { Permission } from "@/lib/permissions"
import type { AxiosResponse, InternalAxiosRequestConfig } from "axios"

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
}

/** Minimal wrapper — no ThemeProvider or AuthProvider (mock in tests) */
export function createWrapper({ initialEntries = ["/"], queryClient }: WrapperOptions = {}) {
  const qc = queryClient ?? createTestQueryClient()

  function TestWrapper({ children }: { children: ReactNode }) {
    return (
      <HelmetProvider>
        <QueryClientProvider client={qc}>
          <LocaleProvider>
            <MemoryRouter initialEntries={initialEntries}>
              {children}
            </MemoryRouter>
          </LocaleProvider>
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

export function createMockAuthUser(overrides: Partial<User> = {}): User {
  return {
    id: "user-1",
    email: "test@operionerp.xyz",
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
  } as User
}

interface MockAuthContextValue {
  user: User | null
  isLoading: boolean
  isAuthenticated: boolean
  isAdmin: boolean
  permissions: Permission[]
  hasPermission: (permission: Permission) => boolean
  mfaRequired: boolean
  mfaSessionToken: string | null
  login: (email: string, password: string, rememberMe?: boolean, turnstileToken?: string) => Promise<{ mfaRequired: boolean }>
  register: (data: { email: string; password: string; name: string; company_name?: string; turnstile_token?: string }) => Promise<void>
  logout: () => void
  refreshUser: () => Promise<void>
  updateUser: (user: User) => void
  verifyMfa: (code: string) => Promise<void>
}

export function createMockAuthContext(overrides: Partial<MockAuthContextValue> = {}): MockAuthContextValue {
  return {
    user: null,
    isLoading: false,
    isAuthenticated: false,
    isAdmin: false,
    permissions: [],
    hasPermission: vi.fn(),
    mfaRequired: false,
    mfaSessionToken: null,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    refreshUser: vi.fn(),
    updateUser: vi.fn(),
    verifyMfa: vi.fn(),
    ...overrides,
  }
}

/** Build a minimal AxiosResponse wrapper around `data` for mockResolvedValue callbacks. */
export function mockAxiosResponse<T>(data: T): AxiosResponse<T> {
  return {
    data,
    status: 200,
    statusText: "OK",
    headers: {},
    config: { headers: {} } as InternalAxiosRequestConfig,
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
