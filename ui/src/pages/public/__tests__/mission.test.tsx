import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '@/contexts/theme-provider'
import MissionPage from '@/pages/public/mission'

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

function renderMission() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <MissionPage />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('MissionPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the page title', () => {
    renderMission()
    expect(screen.getByText('Our Mission')).toBeInTheDocument()
  })

  it('renders the mission statement', () => {
    renderMission()
    expect(
      screen.getByText(
        /To make enterprise logistics accessible, efficient, and sustainable for every fleet, everywhere/,
      ),
    ).toBeInTheDocument()
  })

  it('renders What We Believe section', () => {
    renderMission()
    expect(screen.getByText('What We Believe')).toBeInTheDocument()
    expect(
      screen.getByText(
        'Technology Should Empower, Not Complicate',
      ),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Efficiency Drives Sustainability'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Every Fleet Deserves Great Tools'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Data-Driven Decisions Beat Gut Feelings'),
    ).toBeInTheDocument()
  })

  it('renders Our Commitment section with stats', () => {
    renderMission()
    expect(screen.getByText('Our Commitment')).toBeInTheDocument()
    expect(screen.getByText('99.9%')).toBeInTheDocument()
    expect(screen.getByText('Uptime SLA')).toBeInTheDocument()
    expect(screen.getByText('Monthly')).toBeInTheDocument()
    expect(screen.getByText('Feature Updates')).toBeInTheDocument()
    expect(screen.getByText('24/7')).toBeInTheDocument()
    expect(screen.getByText('Customer Support')).toBeInTheDocument()
  })

  it('renders CTA section with get started link', () => {
    renderMission()
    const getStarted = screen.getByRole('link', { name: /get started/i })
    expect(getStarted).toBeInTheDocument()
    expect(getStarted.getAttribute('href')).toBe('/register')
  })
})
