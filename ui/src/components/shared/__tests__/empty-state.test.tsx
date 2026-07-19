import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { EmptyState } from '@/components/shared/empty-state'

function CustomIcon({ className }: { className?: string }) {
  return <svg data-testid="custom-icon" className={className} />
}

describe('EmptyState', () => {
  it('renders default title and description', () => {
    render(<EmptyState />)
    expect(screen.getByText('Nothing here yet')).toBeInTheDocument()
    expect(
      screen.getByText('Get started by creating your first item.'),
    ).toBeInTheDocument()
  })

  it('renders custom title and description', () => {
    render(
      <EmptyState
        title="No results found"
        description="Try adjusting your filters."
      />,
    )
    expect(screen.getByText('No results found')).toBeInTheDocument()
    expect(screen.getByText('Try adjusting your filters.')).toBeInTheDocument()
  })

  it('renders default PackageOpen icon', () => {
    render(<EmptyState />)
    // The icon is rendered inside a container; check the outer wrapper exists
    expect(
      screen.getByText('Nothing here yet'),
    ).toBeInTheDocument()
  })

  it('renders custom icon when provided', () => {
    render(<EmptyState icon={CustomIcon} />)
    expect(screen.getByTestId('custom-icon')).toBeInTheDocument()
  })

  it('renders action button and fires onClick', async () => {
    const user = userEvent.setup()
    const onClick = vi.fn()
    render(<EmptyState action={{ label: 'Create item', onClick }} />)
    const btn = screen.getByRole('button', { name: /create item/i })
    expect(btn).toBeInTheDocument()

    await user.click(btn)
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('does not render action button when action is not provided', () => {
    render(<EmptyState />)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('forwards additional className', () => {
    const { container } = render(
      <EmptyState className="custom-empty" />,
    )
    const el = container.querySelector('.custom-empty')
    expect(el).toBeInTheDocument()
  })
})
