import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '@/contexts/theme-provider'
import HomePage from '@/pages/public/home'

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

function renderPublicHome() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <HomePage />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('PublicHomePage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the hero heading', () => {
    renderPublicHome()
    expect(
      screen.getByText('Enterprise Logistics,'),
    ).toBeInTheDocument()
    expect(screen.getByText('Simplified')).toBeInTheDocument()
  })

  it('renders feature highlights', () => {
    renderPublicHome()
    expect(
      screen.getByText('Intelligent Route Planning'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Real-Time Fleet Tracking'),
    ).toBeInTheDocument()
    expect(screen.getByText('Smart Dispatch')).toBeInTheDocument()
    expect(
      screen.getByText('OCR Document Processing'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Advanced Analytics'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Driver Management'),
    ).toBeInTheDocument()
  })

  it('renders benefits section', () => {
    renderPublicHome()
    expect(
      screen.getByText('Reduce Operational Costs'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Increase Delivery Speed'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Eliminate Paperwork'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Scale With Confidence'),
    ).toBeInTheDocument()
  })

  it('renders testimonials', () => {
    renderPublicHome()
    expect(screen.getByText('Andrei M.')).toBeInTheDocument()
    expect(screen.getByText('Maria P.')).toBeInTheDocument()
    expect(screen.getByText('Victor D.')).toBeInTheDocument()
  })

  it('renders mission section', () => {
    renderPublicHome()
    expect(screen.getByText('Our Mission')).toBeInTheDocument()
  })

  it('renders CTA section with links', () => {
    renderPublicHome()
    const startTrialLinks = screen.getAllByRole('link', {
      name: /start free trial/i,
    })
    expect(startTrialLinks.length).toBeGreaterThanOrEqual(1)
    // The hero section and CTA section both have Start Free Trial
    startTrialLinks.forEach((link) => {
      expect(link.getAttribute('href')).toBe('/register')
    })
  })

  it('renders hero action links', () => {
    renderPublicHome()
    const seeHowLink = screen.getByRole('link', { name: /see how it works/i })
    expect(seeHowLink).toBeInTheDocument()
    expect(seeHowLink.getAttribute('href')).toBe('/features')
  })
})
