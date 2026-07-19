import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '@/contexts/theme-provider'
import PublicNotFoundPage from '@/pages/public/not-found'

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

function renderPublicNotFound() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <PublicNotFoundPage />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('PublicNotFoundPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders 404 heading and message', () => {
    renderPublicNotFound()
    expect(screen.getByText('404')).toBeInTheDocument()
    expect(screen.getByText('Page not found')).toBeInTheDocument()
    expect(
      screen.getByText(
        "The page you're looking for doesn't exist or has been moved.",
      ),
    ).toBeInTheDocument()
  })

  it('renders go home link', () => {
    renderPublicNotFound()
    const goHome = screen.getByRole('link', { name: /go home/i })
    expect(goHome).toBeInTheDocument()
    expect(goHome.getAttribute('href')).toBe('/')
  })

  it('renders contact support link', () => {
    renderPublicNotFound()
    const contactLink = screen.getByRole('link', { name: /contact support/i })
    expect(contactLink).toBeInTheDocument()
    expect(contactLink.getAttribute('href')).toBe('/contact')
  })
})
