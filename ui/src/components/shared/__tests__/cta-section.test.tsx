import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { CTASection } from '@/components/shared/cta-section'

function renderWithRouter(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>)
}

describe('CTASection', () => {
  it('renders title', () => {
    renderWithRouter(<CTASection title="Ready to start?" />)
    expect(
      screen.getByRole('heading', { name: /ready to start/i }),
    ).toBeInTheDocument()
  })

  it('renders description when provided', () => {
    renderWithRouter(
      <CTASection
        title="Get started"
        description="Join thousands of happy customers."
      />,
    )
    expect(
      screen.getByText('Join thousands of happy customers.'),
    ).toBeInTheDocument()
  })

  it('does not render description when not provided', () => {
    renderWithRouter(<CTASection title="Only title" />)
    const desc = screen.queryByText(/Join thousands/i)
    expect(desc).not.toBeInTheDocument()
  })

  it('renders only primary action when secondary is not provided', () => {
    renderWithRouter(
      <CTASection
        title="Start now"
        primaryAction={{ label: 'Sign up', href: '/signup' }}
      />,
    )
    expect(screen.getByRole('link', { name: /sign up/i })).toBeInTheDocument()
    expect(screen.getByText(/sign up/i).closest('a')).toHaveAttribute(
      'href',
      '/signup',
    )
  })

  it('renders both primary and secondary actions', () => {
    renderWithRouter(
      <CTASection
        title="Start now"
        primaryAction={{ label: 'Sign up', href: '/signup' }}
        secondaryAction={{ label: 'Learn more', href: '/about' }}
      />,
    )
    expect(screen.getByRole('link', { name: /sign up/i })).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: /learn more/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/learn more/i).closest('a'),
    ).toHaveAttribute('href', '/about')
  })

  it('does not render buttons when actions are not provided', () => {
    renderWithRouter(<CTASection title="Just text" />)
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })

  it('forwards additional className', () => {
    const { container } = renderWithRouter(
      <CTASection title="Title" className="custom-cta" />,
    )
    const el = container.querySelector('.custom-cta')
    expect(el).toBeInTheDocument()
  })
})
