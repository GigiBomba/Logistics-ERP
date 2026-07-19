import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '@/contexts/theme-provider'
import FeaturesPage from '@/pages/public/features'

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

function renderFeatures() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <FeaturesPage />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('FeaturesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the page title', () => {
    renderFeatures()
    expect(
      screen.getByText('Powerful Features for Modern Logistics'),
    ).toBeInTheDocument()
  })

  it('renders all feature categories', () => {
    renderFeatures()
    expect(
      screen.getByText('Route Planning & Optimization'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Fleet Management'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Dispatch & Operations'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Document Management'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Analytics & Reporting'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Driver Management'),
    ).toBeInTheDocument()
  })

  it('renders individual features within categories', () => {
    renderFeatures()
    expect(
      screen.getByText('Intelligent Route Planning'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Multi-Stop Optimization'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Real-Time GPS Tracking'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('AI-Powered OCR'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Custom Dashboards'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Driver Profiles'),
    ).toBeInTheDocument()
  })
})
