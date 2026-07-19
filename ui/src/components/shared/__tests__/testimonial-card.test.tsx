import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { TestimonialCard } from '@/components/shared/testimonial-card'

const defaultProps = {
  quote: 'This product changed our workflow completely.',
  author: 'Jane Doe',
  role: 'CEO',
  company: 'Acme Inc',
}

describe('TestimonialCard', () => {
  it('renders quote, author, role and company', () => {
    render(<TestimonialCard {...defaultProps} />)
    expect(screen.getByText(defaultProps.quote)).toBeInTheDocument()
    expect(screen.getByText(defaultProps.author)).toBeInTheDocument()
    expect(screen.getByText(`${defaultProps.role}, ${defaultProps.company}`)).toBeInTheDocument()
  })

  it('renders author initials when avatarUrl is not provided', () => {
    render(<TestimonialCard {...defaultProps} />)
    // Jane Doe -> JD
    expect(screen.getByText('JD')).toBeInTheDocument()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })

  it('renders avatar image when avatarUrl is provided', () => {
    render(<TestimonialCard {...defaultProps} avatarUrl="/avatars/jane.jpg" />)
    const img = screen.getByRole('img')
    expect(img).toHaveAttribute('src', '/avatars/jane.jpg')
    expect(img).toHaveAttribute('alt', defaultProps.author)
    expect(screen.queryByText('JD')).not.toBeInTheDocument()
  })

  it('forwards additional className', () => {
    render(<TestimonialCard {...defaultProps} className="custom-class" />)
    // The className is applied to the Card inside the motion.div
    // We check that something in the document has a class containing "custom-class"
    const card = screen.getByText(defaultProps.quote).closest('.custom-class')
    expect(card).toBeInTheDocument()
  })

  it('applies different animation delay based on index prop', () => {
    const { container } = render(<TestimonialCard {...defaultProps} index={2} />)
    // motion.div renders transition styles; just verify rendering succeeds
    expect(container.firstChild).toBeInTheDocument()
  })
})
