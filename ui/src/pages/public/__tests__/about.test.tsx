import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '@/contexts/theme-provider'
import AboutPage from '@/pages/public/about'

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

function renderAbout() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <AboutPage />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('AboutPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the page title', () => {
    renderAbout()
    expect(screen.getByText('About Operion')).toBeInTheDocument()
  })

  it('renders the Our Story section', () => {
    renderAbout()
    expect(screen.getByText('Our Story')).toBeInTheDocument()
  })

  it('renders all company values', () => {
    renderAbout()
    expect(screen.getByText('Customer First')).toBeInTheDocument()
    expect(screen.getByText('Reliability')).toBeInTheDocument()
    expect(screen.getByText('Innovation')).toBeInTheDocument()
    expect(screen.getByText('Transparency')).toBeInTheDocument()
    expect(screen.getByText('Security')).toBeInTheDocument()
    expect(screen.getByText('Partnership')).toBeInTheDocument()
  })

  it('renders the Our Team section', () => {
    renderAbout()
    expect(screen.getByText('Our Team')).toBeInTheDocument()
  })
})
