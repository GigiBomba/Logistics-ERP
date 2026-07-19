import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Button } from '@/components/ui/button'

describe('Button', () => {
  it('renders default button with text', () => {
    render(<Button>Click me</Button>)
    const btn = screen.getByRole('button', { name: /click me/i })
    expect(btn).toBeInTheDocument()
    expect(btn.tagName).toBe('BUTTON')
  })

  describe('variants', () => {
    const variants = ['default', 'destructive', 'outline', 'secondary', 'ghost', 'link'] as const
    for (const variant of variants) {
      it(`renders ${variant} variant`, () => {
        render(<Button variant={variant}>{variant}</Button>)
        const btn = screen.getByRole('button', { name: variant })
        expect(btn).toBeInTheDocument()
        // Class should contain variant-specific styling
        expect(btn.className).toContain(variant === 'default' ? 'bg-primary' : '')
      })
    }
  })

  describe('sizes', () => {
    const sizes = ['default', 'sm', 'lg', 'icon'] as const
    for (const size of sizes) {
      it(`renders ${size} size`, () => {
        render(<Button size={size}>{size === 'icon' ? 'X' : size}</Button>)
        const btn = screen.getByRole('button', { name: size === 'icon' ? 'X' : size })
        expect(btn).toBeInTheDocument()
      })
    }
  })

  it('disabled state does not fire onClick', async () => {
    const user = userEvent.setup()
    const onClick = vi.fn()

    render(
      <Button disabled onClick={onClick}>
        Disabled
      </Button>,
    )

    const btn = screen.getByRole('button', { name: /disabled/i })
    expect(btn).toBeDisabled()

    await user.click(btn)
    expect(onClick).not.toHaveBeenCalled()
  })

  it('forwards additional className', () => {
    render(<Button className="extra-class">Styled</Button>)
    const btn = screen.getByRole('button', { name: /styled/i })
    expect(btn.className).toContain('extra-class')
  })

  it('renders as child when asChild is true', () => {
    render(
      <Button asChild>
        <a href="/test">Link Button</a>
      </Button>,
    )
    const link = screen.getByRole('link', { name: /link button/i })
    expect(link).toBeInTheDocument()
    expect(link.getAttribute('href')).toBe('/test')
  })

  describe('snapshots', () => {
    const variants = ['default', 'destructive', 'outline', 'secondary', 'ghost', 'link'] as const
    for (const variant of variants) {
      it(`matches snapshot for ${variant} variant`, () => {
        const { container } = render(<Button variant={variant}>{variant}</Button>)
        expect(container.firstChild).toMatchSnapshot()
      })
    }

    const sizes = ['default', 'sm', 'lg', 'icon'] as const
    for (const size of sizes) {
      it(`matches snapshot for ${size} size`, () => {
        const { container } = render(
          <Button size={size}>{size === 'icon' ? 'X' : size}</Button>,
        )
        expect(container.firstChild).toMatchSnapshot()
      })
    }

    it('matches snapshot for disabled button', () => {
      const { container } = render(<Button disabled>Disabled</Button>)
      expect(container.firstChild).toMatchSnapshot()
    })

    it('matches snapshot with additional className', () => {
      const { container } = render(<Button className="extra-class">Styled</Button>)
      expect(container.firstChild).toMatchSnapshot()
    })
  })
})
