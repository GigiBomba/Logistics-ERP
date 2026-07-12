import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AppShell } from '@/components/layout/app-shell'
import { ThemeProvider } from '@/contexts/theme-provider'
import { AuthProvider } from '@/contexts/auth-provider'

// Mock the API module used by AuthProvider
vi.mock('@/lib/api', () => ({
  api: {
    post: vi.fn(),
    postForm: vi.fn(),
    get: vi.fn(),
  },
  setTokens: vi.fn(),
  clearTokens: vi.fn(),
  getStoredUser: vi.fn(() => null),
  getStoredRefreshToken: vi.fn(() => null),
}))

function renderShell(initialEntries = ['/']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <ThemeProvider>
        <AuthProvider>
          <AppShell />
        </AuthProvider>
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('AppShell', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('renders Navbar with logo and nav items', () => {
    renderShell()
    // Logo brand appears in both header and footer; use getAllByText
    const brandElements = screen.getAllByText('Operion ERP')
    expect(brandElements.length).toBeGreaterThanOrEqual(1)

    // Public nav items ("Features" and "Pricing" also appear in footer "Product" section)
    expect(screen.getAllByText('Features').length).toBe(2) // Nav + Footer
    expect(screen.getAllByText('Pricing').length).toBe(2) // Nav + Footer
    expect(screen.getByText('Support')).toBeInTheDocument() // Only in nav
  })

  it('renders Footer with links', () => {
    renderShell()
    expect(screen.getByText('Product')).toBeInTheDocument()
    expect(screen.getByText('Company')).toBeInTheDocument()
    expect(screen.getByText('Legal')).toBeInTheDocument()
    // "About" appears in both nav and footer; use getAllByText
    const aboutElements = screen.getAllByText('About')
    expect(aboutElements.length).toBe(2) // Nav link + footer link
  })

  it('shows Sign In / Get Started when not authenticated', () => {
    renderShell()
    expect(screen.getByText('Sign in')).toBeInTheDocument()
    expect(screen.getByText('Get started')).toBeInTheDocument()
  })
})
