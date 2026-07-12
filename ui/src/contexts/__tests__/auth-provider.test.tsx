import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { AuthProvider, useAuth } from '@/contexts/auth-provider'

// Mock the API module
vi.mock('@/lib/api', () => ({
  api: {
    post: vi.fn(),
    postForm: vi.fn(),
    get: vi.fn(),
  },
  setTokens: vi.fn(),
  clearTokens: vi.fn(),
  getStoredUser: vi.fn(),
  getStoredRefreshToken: vi.fn(() => null),
}))

import { api, setTokens, clearTokens, getStoredUser } from '@/lib/api'

// Test helper
function TestConsumer() {
  const { user, isAuthenticated, login, register, logout } = useAuth()
  return (
    <div>
      <span data-testid="auth-status">
        {isAuthenticated ? 'authenticated' : 'anonymous'}
      </span>
      {user && <span data-testid="user-email">{user.email}</span>}
      <button data-testid="btn-login" onClick={() => login('a@b.com', 'pass').catch(() => {})}>
        Login
      </button>
      <button
        data-testid="btn-register"
        onClick={() => register('a@b.com', 'pass', 'Alice', 'Acme').catch(() => {})}
      >
        Register
      </button>
      <button data-testid="btn-logout" onClick={() => logout().catch(() => {})}>
        Logout
      </button>
    </div>
  )
}

describe('AuthProvider', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
    ;(getStoredUser as ReturnType<typeof vi.fn>).mockReturnValue(null)
  })

  it('renders children', () => {
    render(
      <AuthProvider>
        <div data-testid="child">Hello</div>
      </AuthProvider>,
    )
    expect(screen.getByTestId('child')).toBeInTheDocument()
  })

  it('starts unauthenticated', () => {
    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    )
    expect(screen.getByTestId('auth-status').textContent).toBe('anonymous')
  })

  it('login() calls API and sets user state', async () => {
    const mockPostForm = vi.mocked(api.postForm)
    mockPostForm.mockResolvedValue({
      access_token: 'token-123',
      refresh_token: 'refresh-456',
      token_type: 'bearer',
      expires_in: 3600,
    })
    ;(setTokens as ReturnType<typeof vi.fn>).mockImplementation(() => {})

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    )

    screen.getByTestId('btn-login').click()

    await waitFor(() => {
      expect(mockPostForm).toHaveBeenCalledWith('/api/v1/auth/token', {
        username: 'a@b.com',
        password: 'pass',
      })
    })

    await waitFor(() => {
      expect(screen.getByTestId('auth-status').textContent).toBe('authenticated')
    })
  })

  it('login() failure does not set user', async () => {
    const mockPostForm = vi.mocked(api.postForm)
    mockPostForm.mockRejectedValue(new Error('Invalid credentials'))

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    )

    screen.getByTestId('btn-login').click()

    await waitFor(() => {
      expect(screen.getByTestId('auth-status').textContent).toBe('anonymous')
    })
  })

  it('logout() clears user state', async () => {
    // Start with user logged in by setting localStorage
    localStorage.setItem(
      'operion_user',
      JSON.stringify({
        id: 1,
        email: 'a@b.com',
        role: 'user',
        company_id: 0,
        display_name: 'Alice',
      }),
    )
    ;(getStoredUser as ReturnType<typeof vi.fn>).mockReturnValue({
      id: 1,
      email: 'a@b.com',
      role: 'user',
      company_id: 0,
      display_name: 'Alice',
    })

    const mockPost = vi.mocked(api.post)
    mockPost.mockResolvedValue({})

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('auth-status').textContent).toBe('authenticated')
    })

    screen.getByTestId('btn-logout').click()

    await waitFor(() => {
      expect(screen.getByTestId('auth-status').textContent).toBe('anonymous')
    })
  })

  it('register() calls API and sets user state', async () => {
    const mockPost = vi.mocked(api.post)
    mockPost.mockResolvedValue({
      access_token: 'token-abc',
      refresh_token: 'refresh-def',
      token_type: 'bearer',
      expires_in: 3600,
      user: {
        id: 1,
        email: 'a@b.com',
        role: 'user',
        company_id: 42,
        display_name: 'Alice',
      },
    })

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    )

    screen.getByTestId('btn-register').click()

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/v1/registration/register', {
        email: 'a@b.com',
        password: 'pass',
        display_name: 'Alice',
        company_name: 'Acme',
      })
    })

    await waitFor(() => {
      expect(screen.getByTestId('auth-status').textContent).toBe('authenticated')
      expect(screen.getByTestId('user-email').textContent).toBe('a@b.com')
    })
  })

  it('localStorage rehydration on mount', () => {
    localStorage.setItem(
      'operion_user',
      JSON.stringify({
        id: 2,
        email: 'stored@example.com',
        role: 'admin',
        company_id: 0,
        display_name: 'Stored User',
      }),
    )
    ;(getStoredUser as ReturnType<typeof vi.fn>).mockReturnValue({
      id: 2,
      email: 'stored@example.com',
      role: 'admin',
      company_id: 0,
      display_name: 'Stored User',
    })

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    )

    expect(screen.getByTestId('auth-status').textContent).toBe('authenticated')
    expect(screen.getByTestId('user-email').textContent).toBe('stored@example.com')
  })
})

describe('useAuth() outside provider', () => {
  it('throws when used without AuthProvider', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    expect(() => render(<TestConsumer />)).toThrow(
      'useAuth must be used within an AuthProvider',
    )
    consoleSpy.mockRestore()
  })
})
