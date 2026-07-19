import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '@/contexts/theme-provider'
import FaqPage from '@/pages/public/faq'

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

function renderFaq() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <FaqPage />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('FaqPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the page title', () => {
    renderFaq()
    expect(
      screen.getByText('Frequently Asked Questions'),
    ).toBeInTheDocument()
  })

  it('renders all category badges', () => {
    renderFaq()
    expect(screen.getByText('General')).toBeInTheDocument()
    expect(screen.getByText('Pricing')).toBeInTheDocument()
    expect(screen.getByText('Technical')).toBeInTheDocument()
    expect(screen.getByText('Support')).toBeInTheDocument()
  })

  it('renders all question buttons', () => {
    renderFaq()
    expect(
      screen.getByText('What is Operion ERP?'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('How does pricing work?'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('What are the system requirements?'),
    ).toBeInTheDocument()
  })

  it('opens answer on click', async () => {
    const user = userEvent.setup()
    renderFaq()

    // Answer should not be visible initially
    expect(
      screen.queryByText(
        /Operion ERP is a comprehensive enterprise logistics platform/,
      ),
    ).not.toBeInTheDocument()

    // Click to open
    await user.click(screen.getByText('What is Operion ERP?'))
    expect(
      screen.getByText(
        /Operion ERP is a comprehensive enterprise logistics platform/,
      ),
    ).toBeInTheDocument()
  })

  it('shows different answer when clicking another question', async () => {
    const user = userEvent.setup()
    renderFaq()

    await user.click(screen.getByText('How does pricing work?'))
    expect(
      screen.getByText(/We offer three plans/),
    ).toBeInTheDocument()
  })
})
