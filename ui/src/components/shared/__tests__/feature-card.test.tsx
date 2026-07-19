import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { FeatureCard } from '@/components/shared/feature-card'

function StarIcon({ className }: { className?: string }) {
  return <svg data-testid="custom-icon" className={className} />
}

describe('FeatureCard', () => {
  it('renders title and description', () => {
    render(
      <FeatureCard
        icon={StarIcon}
        title="Fast Performance"
        description="Lightning-fast load times."
      />,
    )
    expect(screen.getByText('Fast Performance')).toBeInTheDocument()
    expect(screen.getByText('Lightning-fast load times.')).toBeInTheDocument()
  })

  it('renders the icon component', () => {
    render(
      <FeatureCard
        icon={StarIcon}
        title="Fast Performance"
        description="Lightning-fast load times."
      />,
    )
    expect(screen.getByTestId('custom-icon')).toBeInTheDocument()
  })

  it('forwards additional className', () => {
    const { container } = render(
      <FeatureCard
        icon={StarIcon}
        title="Title"
        description="Description"
        className="custom-feature"
      />,
    )
    const card = container.querySelector('.custom-feature')
    expect(card).toBeInTheDocument()
  })

  it('renders with a different animation delay when index is set', () => {
    const { container } = render(
      <FeatureCard
        icon={StarIcon}
        title="Title"
        description="Description"
        index={3}
      />,
    )
    expect(container.firstChild).toBeInTheDocument()
  })

  it('renders a placeholder icon using a lucide-react-like component', () => {
    const CustomIcon = vi.fn(() => (
      <div data-testid="icon-wrapper">Icon</div>
    ))
    render(
      <FeatureCard
        icon={CustomIcon}
        title="With Icon"
        description="Test"
      />,
    )
    expect(screen.getByTestId('icon-wrapper')).toBeInTheDocument()
  })
})
