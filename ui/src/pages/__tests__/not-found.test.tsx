import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '@/contexts/theme-provider'
import NotFoundPage from '@/pages/not-found'

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

function renderNotFound() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <NotFoundPage />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('NotFoundPage (root)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders 404 title and description', () => {
    renderNotFound()
    expect(screen.getByText('Page not found')).toBeInTheDocument()
    expect(
      screen.getByText("The page you're looking for doesn't exist or has been moved."),
    ).toBeInTheDocument()
  })

  it('renders the go home button', () => {
    renderNotFound()
    const goHome = screen.getByRole('button', { name: /go home/i })
    expect(goHome).toBeInTheDocument()
  })

  it('renders the EmptyState component', () => {
    renderNotFound()
    expect(screen.getByText('Page not found')).toBeInTheDocument()
  })
})
