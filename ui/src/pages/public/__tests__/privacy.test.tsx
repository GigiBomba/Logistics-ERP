import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '@/contexts/theme-provider'
import PrivacyPage from '@/pages/public/privacy'

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

function renderPrivacy() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <PrivacyPage />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('PrivacyPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the page title', () => {
    renderPrivacy()
    expect(screen.getByText('Privacy Policy')).toBeInTheDocument()
    expect(
      screen.getByText('Last updated: July 2026'),
    ).toBeInTheDocument()
  })

  it('renders table of contents', () => {
    renderPrivacy()
    expect(screen.getByText('Table of Contents')).toBeInTheDocument()
    // Section titles appear in TOC and again as headings — use getAllByText
    const sectionOneItems = screen.getAllByText('1. Information We Collect')
    expect(sectionOneItems.length).toBe(2)
  })

  it('renders all policy sections', () => {
    renderPrivacy()
    // Each section title appears twice: in TOC nav and as <h2> heading
    expect(screen.getAllByText('1. Information We Collect').length).toBe(2)
    expect(screen.getAllByText('2. How We Use Information').length).toBe(2)
    expect(
      screen.getAllByText('3. Data Storage & Security').length,
    ).toBe(2)
    expect(screen.getAllByText('4. Data Sharing').length).toBe(2)
    expect(screen.getAllByText('5. Your Rights (GDPR)').length).toBe(2)
    expect(screen.getAllByText('6. Cookies').length).toBe(2)
    expect(
      screen.getAllByText('7. Contact for Privacy Inquiries').length,
    ).toBe(2)
  })

  it('renders section content paragraphs', () => {
    renderPrivacy()
    expect(
      screen.getByText(/When you register for an Operion ERP account/),
    ).toBeInTheDocument()
  })
})
