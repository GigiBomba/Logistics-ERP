import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { ThemeProvider } from '@/contexts/theme-provider'
import VerifyEmailPage from '@/pages/auth/verify-email'

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

function renderVerifyEmail() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <VerifyEmailPage />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('VerifyEmailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the title and description', () => {
    renderVerifyEmail()
    expect(screen.getByText('Check your email')).toBeInTheDocument()
    expect(
      screen.getByText(/we've sent a verification link/i),
    ).toBeInTheDocument()
  })

  it('renders back to home link', () => {
    renderVerifyEmail()
    const backLink = screen.getByRole('link', { name: /back to home/i })
    expect(backLink).toBeInTheDocument()
    expect(backLink.getAttribute('href')).toBe('/')
  })

  it('renders go to sign in button', () => {
    renderVerifyEmail()
    const signInLink = screen.getByRole('link', { name: /go to sign in/i })
    expect(signInLink).toBeInTheDocument()
    expect(signInLink.getAttribute('href')).toBe('/login')
  })

  it('renders contact support link', () => {
    renderVerifyEmail()
    const contactLink = screen.getByRole('link', { name: /contact support/i })
    expect(contactLink).toBeInTheDocument()
    expect(contactLink.getAttribute('href')).toBe('/contact')
  })
})
