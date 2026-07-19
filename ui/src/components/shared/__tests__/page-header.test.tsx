import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { PageHeader } from '@/components/shared/page-header'

describe('PageHeader', () => {
  it('renders title', () => {
    render(<PageHeader title="Welcome" />)
    const heading = screen.getByRole('heading', { name: /welcome/i })
    expect(heading).toBeInTheDocument()
    expect(heading.tagName).toBe('H1')
  })

  it('renders description when provided', () => {
    render(
      <PageHeader
        title="About Us"
        description="Learn more about our team."
      />,
    )
    expect(screen.getByText('Learn more about our team.')).toBeInTheDocument()
  })

  it('does not render description when not provided', () => {
    render(<PageHeader title="No desc" />)
    expect(screen.queryByText(/learn more/i)).not.toBeInTheDocument()
  })

  it('renders children when provided', () => {
    render(
      <PageHeader title="Dashboard">
        <button data-testid="child-btn">Action</button>
      </PageHeader>,
    )
    expect(screen.getByTestId('child-btn')).toBeInTheDocument()
  })

  it('does not render children slot when children is not provided', () => {
    const { container } = render(<PageHeader title="Only title" />)
    // The container should not have extra block-level children beyond the h1 and optional description
    const h1 = container.querySelector('h1')
    // The parent div should only contain h1 (and no extra child elements)
    expect(h1?.nextElementSibling).toBeNull()
  })

  it('forwards additional className', () => {
    const { container } = render(
      <PageHeader title="Styled" className="custom-header" />,
    )
    const el = container.querySelector('.custom-header')
    expect(el).toBeInTheDocument()
  })
})
