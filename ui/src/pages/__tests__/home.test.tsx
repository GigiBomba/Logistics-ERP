import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '@/contexts/theme-provider'
import HomePage from '@/pages/home'

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

function renderHome() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <HomePage />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('HomePage (root)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the hero heading', () => {
    renderHome()
    expect(screen.getByText('Enterprise resource planning,')).toBeInTheDocument()
    expect(screen.getByText('reimagined.')).toBeInTheDocument()
  })

  it('renders the public beta badge', () => {
    renderHome()
    expect(screen.getByText('Now in public beta')).toBeInTheDocument()
  })

  it('renders all feature cards', () => {
    renderHome()
    expect(screen.getByText('Real-time Analytics')).toBeInTheDocument()
    expect(screen.getByText('Team Collaboration')).toBeInTheDocument()
    expect(screen.getByText('Workflow Automation')).toBeInTheDocument()
    expect(screen.getByText('Enterprise Security')).toBeInTheDocument()
    expect(screen.getByText('Global Operations')).toBeInTheDocument()
    expect(screen.getByText('Modular Architecture')).toBeInTheDocument()
  })

  it('renders CTA section with links', () => {
    renderHome()
    const startTrial = screen.getByRole('link', { name: /start free trial/i })
    expect(startTrial).toBeInTheDocument()
    expect(startTrial.getAttribute('href')).toBe('/signup')

    const viewPricing = screen.getByRole('link', { name: /view pricing/i })
    expect(viewPricing).toBeInTheDocument()
    expect(viewPricing.getAttribute('href')).toBe('/pricing')
  })
})
