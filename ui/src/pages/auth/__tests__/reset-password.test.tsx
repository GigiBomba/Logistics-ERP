import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { ThemeProvider } from '@/contexts/theme-provider'
import ResetPasswordPage from '@/pages/auth/reset-password'

// Mock the api module — factory must not reference any top-level variables
vi.mock('@/lib/api', () => ({
  api: { post: vi.fn() },
}))

import { api } from '@/lib/api'

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

import { toast } from 'sonner'

function renderResetPassword(initialEntries: string[] = ['/reset-password?token=valid-token-123']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <ThemeProvider>
        <ResetPasswordPage />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('ResetPasswordPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders password fields and reset button', () => {
    renderResetPassword()
    expect(screen.getByLabelText('New Password')).toBeInTheDocument()
    expect(screen.getByLabelText('Confirm New Password')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /reset password/i }),
    ).toBeInTheDocument()
  })

  it('reads token from search params', () => {
    renderResetPassword()
    // Token is present — no warning should show
    expect(
      screen.queryByText(/no reset token detected/i),
    ).not.toBeInTheDocument()
  })

  it('shows warning when token is missing from URL', () => {
    renderResetPassword(['/reset-password'])
    expect(
      screen.getByText(/no reset token detected/i),
    ).toBeInTheDocument()
  })

  it('shows validation error on empty submit', async () => {
    const user = userEvent.setup()
    renderResetPassword()

    await user.click(screen.getByRole('button', { name: /reset password/i }))

    await waitFor(() => {
      expect(
        screen.getByText('Password must be at least 8 characters'),
      ).toBeInTheDocument()
    })
  })

  it('shows error when passwords do not match', async () => {
    const user = userEvent.setup()
    renderResetPassword()

    await user.type(screen.getByLabelText('New Password'), 'password123')
    await user.type(screen.getByLabelText('Confirm New Password'), 'different')
    await user.click(screen.getByRole('button', { name: /reset password/i }))

    await waitFor(() => {
      expect(screen.getByText("Passwords don't match")).toBeInTheDocument()
    })
  })

  it('shows loading state during submit', async () => {
    const mockPost = vi.mocked(api.post)
    mockPost.mockImplementation(() => new Promise(() => {})) // never resolves

    const user = userEvent.setup()
    renderResetPassword()

    await user.type(screen.getByLabelText('New Password'), 'newpassword123')
    await user.type(screen.getByLabelText('Confirm New Password'), 'newpassword123')
    await user.click(screen.getByRole('button', { name: /reset password/i }))

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /resetting/i }),
      ).toBeInTheDocument()
    })
  })

  it('shows error toast when no token and form is submitted', async () => {
    const user = userEvent.setup()
    renderResetPassword(['/reset-password'])

    await user.type(screen.getByLabelText('New Password'), 'newpassword123')
    await user.type(screen.getByLabelText('Confirm New Password'), 'newpassword123')
    await user.click(screen.getByRole('button', { name: /reset password/i }))

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        'No reset token provided. Please use the link from your email.',
      )
    })
  })

  it('does not call API when token is missing', async () => {
    const user = userEvent.setup()
    renderResetPassword(['/reset-password'])

    await user.type(screen.getByLabelText('New Password'), 'newpassword123')
    await user.type(screen.getByLabelText('Confirm New Password'), 'newpassword123')
    await user.click(screen.getByRole('button', { name: /reset password/i }))

    await waitFor(() => {
      expect(api.post).not.toHaveBeenCalled()
    })
  })

  it('calls API and shows success toast on valid submission', async () => {
    const mockPost = vi.mocked(api.post)
    mockPost.mockResolvedValue({ detail: 'Password reset successfully!' })

    const user = userEvent.setup()
    renderResetPassword()

    await user.type(screen.getByLabelText('New Password'), 'newpassword123')
    await user.type(screen.getByLabelText('Confirm New Password'), 'newpassword123')
    await user.click(screen.getByRole('button', { name: /reset password/i }))

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/v1/auth/reset-password', {
        token: 'valid-token-123',
        new_password: 'newpassword123',
      })
      expect(toast.success).toHaveBeenCalledWith(
        'Password reset successfully!',
      )
    })
  })

  it('shows error toast on API failure (invalid/expired token)', async () => {
    const mockPost = vi.mocked(api.post)
    mockPost.mockRejectedValue(new Error('Invalid or expired reset token'))

    const user = userEvent.setup()
    renderResetPassword()

    await user.type(screen.getByLabelText('New Password'), 'newpassword123')
    await user.type(screen.getByLabelText('Confirm New Password'), 'newpassword123')
    await user.click(screen.getByRole('button', { name: /reset password/i }))

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        'Invalid or expired reset token',
      )
    })
  })

  it('renders back to home link', () => {
    renderResetPassword()
    const backLink = screen.getByRole('link', { name: /back to home/i })
    expect(backLink).toBeInTheDocument()
    expect(backLink.getAttribute('href')).toBe('/')
  })

  it('has show/hide password toggle buttons', async () => {
    const user = userEvent.setup()
    renderResetPassword()

    const showButtons = screen.getAllByRole('button', { name: /show password/i })
    expect(showButtons).toHaveLength(2)

    await user.click(showButtons[0])
    expect(
      screen.getByRole('button', { name: /hide password/i }),
    ).toBeInTheDocument()
  })
})
