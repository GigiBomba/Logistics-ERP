import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '@/contexts/theme-provider'
import PricingPage from '@/pages/public/pricing'

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

function renderPricing() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <PricingPage />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('PricingPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the page title', () => {
    renderPricing()
    expect(
      screen.getByText('Simple, Transparent Pricing'),
    ).toBeInTheDocument()
  })

  it('renders all plan names', () => {
    renderPricing()
    expect(screen.getByText('Starter')).toBeInTheDocument()
    expect(screen.getByText('Professional')).toBeInTheDocument()
    expect(screen.getByText('Enterprise')).toBeInTheDocument()
  })

  it('renders plan prices', () => {
    renderPricing()
    expect(screen.getByText('€49')).toBeInTheDocument()
    expect(screen.getByText('€99')).toBeInTheDocument()
    expect(screen.getByText('€249')).toBeInTheDocument()
  })

  it('renders "Most Popular" badge on Professional', () => {
    renderPricing()
    expect(screen.getByText('Most Popular')).toBeInTheDocument()
  })

  it('renders yearly pricing info', () => {
    renderPricing()
    expect(screen.getByText(/Save up to 20% with annual billing/)).toBeInTheDocument()
  })

  it('renders CTA buttons with correct links', () => {
    renderPricing()
    const startTrialLinks = screen.getAllByRole('link', {
      name: /start free trial/i,
    })
    // One in each pricing card (3) + possibly in the CTA section
    expect(startTrialLinks.length).toBeGreaterThanOrEqual(3)
    startTrialLinks.forEach((link) => {
      expect(link.getAttribute('href')).toBe('/register')
    })
  })

  it('renders FAQ section with togglable items', async () => {
    const user = userEvent.setup()
    renderPricing()

    expect(
      screen.getByText('Frequently Asked Questions'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Can I change plans?'),
    ).toBeInTheDocument()

    // Click to open
    await user.click(screen.getByText('Can I change plans?'))
    expect(
      screen.getByText(/upgrade or downgrade anytime/i),
    ).toBeInTheDocument()
  })
})
