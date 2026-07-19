import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { PricingCard } from '@/components/shared/pricing-card'

const defaultProps = {
  name: 'Pro',
  price: '$29',
  description: 'Best for growing teams',
  features: ['Unlimited projects', 'Priority support', 'Advanced analytics'],
}

function renderWithRouter(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>)
}

describe('PricingCard', () => {
  it('renders plan name, price, period and description', () => {
    renderWithRouter(<PricingCard {...defaultProps} />)
    expect(screen.getByText(defaultProps.name)).toBeInTheDocument()
    expect(screen.getByText(defaultProps.price)).toBeInTheDocument()
    expect(screen.getByText('/month')).toBeInTheDocument()
    expect(screen.getByText(defaultProps.description)).toBeInTheDocument()
  })

  it('renders all feature items', () => {
    renderWithRouter(<PricingCard {...defaultProps} />)
    for (const feature of defaultProps.features) {
      expect(screen.getByText(feature)).toBeInTheDocument()
    }
  })

  it('renders default CTA label and href', () => {
    renderWithRouter(<PricingCard {...defaultProps} />)
    const link = screen.getByRole('link', { name: /get started/i })
    expect(link).toBeInTheDocument()
    expect(link).toHaveAttribute('href', '/signup')
  })

  it('renders custom CTA label and href', () => {
    renderWithRouter(
      <PricingCard
        {...defaultProps}
        ctaLabel="Buy now"
        ctaHref="/checkout"
      />,
    )
    const link = screen.getByRole('link', { name: /buy now/i })
    expect(link).toBeInTheDocument()
    expect(link).toHaveAttribute('href', '/checkout')
  })

  it('renders custom period', () => {
    renderWithRouter(<PricingCard {...defaultProps} period="/year" />)
    expect(screen.getByText('/year')).toBeInTheDocument()
  })

  it('renders Most Popular badge when highlighted is true', () => {
    renderWithRouter(<PricingCard {...defaultProps} highlighted />)
    expect(screen.getByText('Most Popular')).toBeInTheDocument()
  })

  it('does not render Most Popular badge when highlighted is false', () => {
    renderWithRouter(<PricingCard {...defaultProps} highlighted={false} />)
    expect(screen.queryByText('Most Popular')).not.toBeInTheDocument()
  })

  it('forwards additional className', () => {
    const { container } = renderWithRouter(
      <PricingCard {...defaultProps} className="custom-card" />,
    )
    const card = container.querySelector('.custom-card')
    expect(card).toBeInTheDocument()
  })
})
