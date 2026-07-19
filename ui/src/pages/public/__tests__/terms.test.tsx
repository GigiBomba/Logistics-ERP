import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '@/contexts/theme-provider'
import TermsPage from '@/pages/public/terms'

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

function renderTerms() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <TermsPage />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('TermsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the page title', () => {
    renderTerms()
    expect(screen.getByText('Terms of Service')).toBeInTheDocument()
    expect(
      screen.getByText('Last updated: July 2026'),
    ).toBeInTheDocument()
  })

  it('renders table of contents', () => {
    renderTerms()
    expect(screen.getByText('Table of Contents')).toBeInTheDocument()
    const sectionOneItems = screen.getAllByText('1. Acceptance of Terms')
    expect(sectionOneItems.length).toBe(2)
  })

  it('renders all terms sections', () => {
    renderTerms()
    // Each section title appears twice: in TOC nav and as <h2> heading
    expect(screen.getAllByText('1. Acceptance of Terms').length).toBe(2)
    expect(
      screen.getAllByText('2. Account Registration & Security').length,
    ).toBe(2)
    expect(
      screen.getAllByText('3. Subscription & Payment Terms').length,
    ).toBe(2)
    expect(
      screen.getAllByText('4. License Grant & Restrictions').length,
    ).toBe(2)
    expect(screen.getAllByText('5. Acceptable Use Policy').length).toBe(2)
    expect(screen.getAllByText('6. Intellectual Property').length).toBe(2)
    expect(
      screen.getAllByText('7. Limitation of Liability').length,
    ).toBe(2)
    expect(screen.getAllByText('8. Termination').length).toBe(2)
    expect(screen.getAllByText('9. Governing Law').length).toBe(2)
    expect(screen.getAllByText('10. Changes to Terms').length).toBe(2)
  })

  it('renders section content paragraphs', () => {
    renderTerms()
    expect(
      screen.getByText(/By accessing or using Operion ERP/),
    ).toBeInTheDocument()
  })
})
