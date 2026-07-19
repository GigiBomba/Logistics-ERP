import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Badge } from '@/components/ui/badge'

describe('Badge', () => {
  it('renders children', () => {
    render(<Badge>Badge text</Badge>)
    const badge = screen.getByText('Badge text')
    expect(badge).toBeInTheDocument()
  })

  it('renders as a div element', () => {
    render(<Badge>Test</Badge>)
    const badge = screen.getByText('Test')
    expect(badge.tagName).toBe('DIV')
  })

  describe('variants', () => {
    const variants = [
      { name: 'default', expected: 'bg-primary' },
      { name: 'secondary', expected: 'bg-secondary' },
      { name: 'destructive', expected: 'bg-destructive' },
      { name: 'outline', expected: 'text-foreground' },
      { name: 'success', expected: 'bg-emerald' },
      { name: 'warning', expected: 'bg-amber' },
    ] as const

    for (const { name, expected } of variants) {
      it(`renders ${name} variant`, () => {
        render(<Badge variant={name}>{name}</Badge>)
        const badge = screen.getByText(name)
        expect(badge).toBeInTheDocument()
        expect(badge.className).toContain(expected)
      })
    }
  })

  it('forwards additional className and merges with variant classes', () => {
    render(<Badge className="my-custom-class">Styled</Badge>)
    const badge = screen.getByText('Styled')
    expect(badge.className).toContain('my-custom-class')
    // Should also retain default variant classes
    expect(badge.className).toContain('bg-primary')
    expect(badge.className).toContain('inline-flex')
  })

  it('forwards ref to the underlying div', () => {
    const ref = { current: null }
    render(<Badge ref={ref}>Ref test</Badge>)
    expect(ref.current).toBeInstanceOf(HTMLDivElement)
    expect(ref.current?.textContent).toBe('Ref test')
  })

  it('spreads additional props', () => {
    render(
      <Badge data-testid="custom-badge" id="badge-id">
        Props
      </Badge>,
    )
    const badge = screen.getByTestId('custom-badge')
    expect(badge).toHaveAttribute('id', 'badge-id')
  })

  it('handles default variant when none is specified', () => {
    render(<Badge>Default</Badge>)
    const badge = screen.getByText('Default')
    expect(badge.className).toContain('bg-primary')
  })

  describe('snapshots', () => {
    const variants = ['default', 'secondary', 'destructive', 'outline', 'success', 'warning'] as const
    for (const variant of variants) {
      it(`matches snapshot for ${variant} variant`, () => {
        const { container } = render(<Badge variant={variant}>{variant}</Badge>)
        expect(container.firstChild).toMatchSnapshot()
      })
    }

    it('matches snapshot with additional className', () => {
      const { container } = render(<Badge className="custom-badge">Styled</Badge>)
      expect(container.firstChild).toMatchSnapshot()
    })
  })
})
