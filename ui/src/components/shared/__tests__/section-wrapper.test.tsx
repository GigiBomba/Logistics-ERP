import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { SectionWrapper } from '@/components/shared/section-wrapper'

describe('SectionWrapper', () => {
  it('renders children', () => {
    render(
      <SectionWrapper>
        <p data-testid="child">Hello</p>
      </SectionWrapper>,
    )
    expect(screen.getByTestId('child')).toBeInTheDocument()
    expect(screen.getByText('Hello')).toBeInTheDocument()
  })

  it('renders as section element by default', () => {
    const { container } = render(<SectionWrapper>Content</SectionWrapper>)
    const section = container.querySelector('section')
    expect(section).toBeInTheDocument()
  })

  it('renders as custom element when as prop is provided', () => {
    const { container } = render(
      <SectionWrapper as="article">
        Content
      </SectionWrapper>,
    )
    expect(container.querySelector('article')).toBeInTheDocument()
    expect(container.querySelector('section')).not.toBeInTheDocument()
  })

  it('sets id prop on the root element', () => {
    const { container } = render(
      <SectionWrapper id="features">
        Content
      </SectionWrapper>,
    )
    const section = container.querySelector('section')
    expect(section).toHaveAttribute('id', 'features')
  })

  it('forwards additional className', () => {
    const { container } = render(
      <SectionWrapper className="extra-class">
        Content
      </SectionWrapper>,
    )
    const section = container.querySelector('section')
    expect(section?.className).toContain('extra-class')
  })

  it('contains a max-w-7xl inner container', () => {
    const { container } = render(<SectionWrapper>Content</SectionWrapper>)
    const inner = container.querySelector('.max-w-7xl')
    expect(inner).toBeInTheDocument()
    expect(inner?.textContent).toBe('Content')
  })
})
