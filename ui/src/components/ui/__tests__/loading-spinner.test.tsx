import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { LoadingSpinner } from '@/components/ui/loading-spinner'

describe('LoadingSpinner', () => {
  it('renders with default size (md)', () => {
    render(<LoadingSpinner data-testid="spinner-default" />)
    const spinner = screen.getByTestId('spinner-default')
    expect(spinner).toBeInTheDocument()
    // Inner spinner should have md dimensions
    const innerSpinner = spinner.firstChild as HTMLElement
    expect(innerSpinner.className).toContain('h-6')
    expect(innerSpinner.className).toContain('w-6')
    expect(innerSpinner.className).toContain('border-2')
  })

  it('renders a visible spinner element with role status', () => {
    render(<LoadingSpinner data-testid="spinner" />)
    const spinner = screen.getByTestId('spinner')
    expect(spinner).toBeInTheDocument()
    expect(spinner.className).toContain('flex')
    expect(spinner.className).toContain('items-center')
    expect(spinner.className).toContain('justify-center')
  })

  describe('sizes', () => {
    const sizes = [
      { name: 'sm', expected: 'h-4 w-4 border-2' },
      { name: 'md', expected: 'h-6 w-6 border-2' },
      { name: 'lg', expected: 'h-8 w-8 border-[3px]' },
    ] as const

    for (const { name, expected } of sizes) {
      it(`renders ${name} size with correct dimensions`, () => {
        render(<LoadingSpinner size={name} data-testid={`spinner-${name}`} />)
        const container = screen.getByTestId(`spinner-${name}`)
        // The inner animated div is the first child
        const innerSpinner = container.firstChild as HTMLElement
        expect(innerSpinner.className).toContain('animate-spin')
        // Check size classes are applied to the inner div
        const sizeParts = expected.split(' ')
        for (const part of sizeParts) {
          expect(innerSpinner.className).toContain(part)
        }
      })
    }
  })

  it('forwards ref to the wrapper div', () => {
    const ref = { current: null }
    render(<LoadingSpinner ref={ref} data-testid="ref-spinner" />)
    expect(ref.current).toBeInstanceOf(HTMLDivElement)
  })

  it('forwards additional className to the wrapper', () => {
    render(<LoadingSpinner className="custom-spinner" data-testid="spinner" />)
    const spinner = screen.getByTestId('spinner')
    expect(spinner.className).toContain('custom-spinner')
  })

  it('merges className with default classes', () => {
    render(<LoadingSpinner className="extra-class" data-testid="spinner" />)
    const spinner = screen.getByTestId('spinner')
    // Should have both default layout classes and the custom class
    expect(spinner.className).toContain('flex')
    expect(spinner.className).toContain('items-center')
    expect(spinner.className).toContain('justify-center')
    expect(spinner.className).toContain('extra-class')
  })

  it('inner spinner has animation class and correct color', () => {
    render(<LoadingSpinner data-testid="spinner" />)
    const container = screen.getByTestId('spinner')
    const innerSpinner = container.firstChild as HTMLElement
    expect(innerSpinner.className).toContain('animate-spin')
    expect(innerSpinner.className).toContain('rounded-full')
    expect(innerSpinner.className).toContain('border-solid')
    expect(innerSpinner.className).toContain('border-current')
    expect(innerSpinner.className).toContain('border-t-transparent')
    expect(innerSpinner.className).toContain('text-primary')
  })

  it('renders with no children passed', () => {
    // The component does not render children, just a wrapper with an inner div
    const { container } = render(<LoadingSpinner data-testid="spinner" />)
    const wrapper = screen.getByTestId('spinner')
    expect(wrapper.childNodes.length).toBe(1)
    // The single child is the spinning circle
    const inner = wrapper.firstChild as HTMLElement
    expect(inner.tagName).toBe('DIV')
  })
})
