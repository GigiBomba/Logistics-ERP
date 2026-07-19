import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { ThemeProvider } from '@/contexts/theme-provider'
import ForgotPasswordPage from '@/pages/auth/forgot-password'

// Mock the api module — factory must not reference any top-level variables
vi.mock('@/lib/api', () => ({
  api: { post: vi.fn() },
}))

import { api } from '@/lib/api'

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

import { toast } from 'sonner'

function renderForgotPassword() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <ForgotPasswordPage />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('ForgotPasswordPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders email field and submit button', () => {
    renderForgotPassword()
    expect(screen.getByLabelText('Email')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /send reset link/i }),
    ).toBeInTheDocument()
  })

  it('shows validation error for invalid email', async () => {
    const user = userEvent.setup()
    renderForgotPassword()

    // "a@b" passes HTML5 input validation but fails Zod's email regex (no TLD)
    await user.type(screen.getByLabelText('Email'), 'a@b')
    await user.click(screen.getByRole('button', { name: /send reset link/i }))

    await waitFor(() => {
      expect(screen.getByText('Please enter a valid email')).toBeInTheDocument()
    })
  })

  it('passes the correct email to the API', async () => {
    const mockPost = vi.mocked(api.post)
    mockPost.mockResolvedValue({ detail: 'OK' })

    const user = userEvent.setup()
    renderForgotPassword()

    await user.type(screen.getByLabelText('Email'), 'user@example.com')
    await user.click(screen.getByRole('button', { name: /send reset link/i }))

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/v1/auth/forgot-password', {
        email: 'user@example.com',
      })
    })
  })

  it('shows loading state during submit', async () => {
    const mockPost = vi.mocked(api.post)
    mockPost.mockImplementation(() => new Promise(() => {})) // never resolves

    const user = userEvent.setup()
    renderForgotPassword()

    await user.type(screen.getByLabelText('Email'), 'test@example.com')
    await user.click(screen.getByRole('button', { name: /send reset link/i }))

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /sending/i }),
      ).toBeInTheDocument()
    })
  })

  it('shows success toast on successful API call', async () => {
    const mockPost = vi.mocked(api.post)
    mockPost.mockResolvedValue({
      detail: 'Reset link sent to your email',
    })

    const user = userEvent.setup()
    renderForgotPassword()

    await user.type(screen.getByLabelText('Email'), 'test@example.com')
    await user.click(screen.getByRole('button', { name: /send reset link/i }))

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/v1/auth/forgot-password', {
        email: 'test@example.com',
      })
      expect(toast.success).toHaveBeenCalledWith(
        'Reset link sent to your email',
      )
    })
  })

  it('shows generic success toast on API error (prevents email enumeration)', async () => {
    const mockPost = vi.mocked(api.post)
    mockPost.mockRejectedValue(new Error('Network error'))

    const user = userEvent.setup()
    renderForgotPassword()

    await user.type(screen.getByLabelText('Email'), 'test@example.com')
    await user.click(screen.getByRole('button', { name: /send reset link/i }))

    await waitFor(() => {
      // Must still call the API
      expect(mockPost).toHaveBeenCalled()
      // Always show the generic success message
      expect(toast.success).toHaveBeenCalledWith(
        'If an account exists, a reset link has been sent.',
      )
    })
  })

  it('renders back to home link', () => {
    renderForgotPassword()
    const backLink = screen.getByRole('link', { name: /back to home/i })
    expect(backLink).toBeInTheDocument()
    expect(backLink.getAttribute('href')).toBe('/')
  })

  it('renders sign in link', () => {
    renderForgotPassword()
    const signInLink = screen.getByRole('link', { name: /sign in/i })
    expect(signInLink).toBeInTheDocument()
    expect(signInLink.getAttribute('href')).toBe('/login')
  })
})
