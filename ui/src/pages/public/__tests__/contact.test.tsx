import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '@/contexts/theme-provider'
import ContactPage from '@/pages/public/contact'
import { toast } from 'sonner'

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

function renderContact() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <ContactPage />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('ContactPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the page title and description', () => {
    renderContact()
    expect(screen.getByText('Get in Touch')).toBeInTheDocument()
    expect(
      screen.getByText(/have questions/i),
    ).toBeInTheDocument()
  })

  it('renders all form fields', () => {
    renderContact()
    expect(screen.getByLabelText('Name')).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toBeInTheDocument()
    expect(screen.getByLabelText('Subject')).toBeInTheDocument()
    expect(screen.getByLabelText('Message')).toBeInTheDocument()
  })

  it('shows validation errors on empty submit', async () => {
    const user = userEvent.setup()
    renderContact()

    await user.click(screen.getByRole('button', { name: /send message/i }))

    await waitFor(() => {
      expect(
        screen.getByText('Name must be at least 2 characters'),
      ).toBeInTheDocument()
    })
    expect(
      screen.getByText('Please enter a valid email address'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Subject must be at least 5 characters'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Message must be at least 10 characters'),
    ).toBeInTheDocument()
  })

  it('shows sending state during submit', async () => {
    // Make the form never resolve to keep loading state
    const user = userEvent.setup()
    renderContact()

    await user.type(screen.getByLabelText('Name'), 'John Doe')
    await user.type(screen.getByLabelText('Email'), 'john@example.com')
    await user.type(screen.getByLabelText('Subject'), 'Test subject here')
    await user.type(
      screen.getByLabelText('Message'),
      'This is a test message that is long enough.',
    )
    await user.click(screen.getByRole('button', { name: /send message/i }))

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /sending/i }),
      ).toBeInTheDocument()
    })
  })

  it('shows success toast on successful submission', async () => {
    const user = userEvent.setup()
    renderContact()

    await user.type(screen.getByLabelText('Name'), 'John Doe')
    await user.type(screen.getByLabelText('Email'), 'john@example.com')
    await user.type(screen.getByLabelText('Subject'), 'Test subject here')
    await user.type(
      screen.getByLabelText('Message'),
      'This is a test message that is long enough.',
    )
    await user.click(screen.getByRole('button', { name: /send message/i }))

    await waitFor(() => {
      expect(toast.success).toHaveBeenCalledWith(
        expect.stringContaining('sent'),
      )
    })
  })

  it('renders contact information cards', () => {
    renderContact()
    // Email appears both as form label and contact info — use getAllByText
    const emailLabels = screen.getAllByText('Email')
    expect(emailLabels.length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText('support@operion.com')).toBeInTheDocument()
    expect(screen.getByText('Phone')).toBeInTheDocument()
    expect(screen.getByText(/\+40 123 456 789/)).toBeInTheDocument()
    expect(screen.getByText('Office')).toBeInTheDocument()
    expect(screen.getByText('Hours')).toBeInTheDocument()
  })
})
