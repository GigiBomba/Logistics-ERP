import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider, useTheme } from '@/contexts/theme-provider'

// Test helper component that accesses theme context
function TestConsumer() {
  const { theme, resolvedTheme, setTheme } = useTheme()
  return (
    <div>
      <span data-testid="theme">{theme}</span>
      <span data-testid="resolved-theme">{resolvedTheme}</span>
      <button data-testid="set-dark" onClick={() => setTheme('dark')}>
        Set Dark
      </button>
    </div>
  )
}

describe('ThemeProvider', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.classList.remove('light', 'dark')
  })

  it('renders children', () => {
    render(
      <ThemeProvider>
        <div data-testid="child">Hello</div>
      </ThemeProvider>,
    )
    expect(screen.getByTestId('child')).toBeInTheDocument()
  })

  it('defaults to system theme with light resolved', () => {
    render(
      <ThemeProvider>
        <TestConsumer />
      </ThemeProvider>,
    )
    // defaultTheme is "system", so theme is "system"
    expect(screen.getByTestId('theme').textContent).toBe('system')
    // matchMedia mock returns matches: false, so resolved is "light"
    expect(screen.getByTestId('resolved-theme').textContent).toBe('light')
  })

  it('applies dark mode via setTheme', async () => {
    const user = userEvent.setup()
    render(
      <ThemeProvider>
        <TestConsumer />
      </ThemeProvider>,
    )

    await user.click(screen.getByTestId('set-dark'))

    await waitFor(() => {
      expect(screen.getByTestId('theme').textContent).toBe('dark')
    })
    expect(screen.getByTestId('resolved-theme').textContent).toBe('dark')
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(document.documentElement.classList.contains('light')).toBe(false)
  })

  it('reads theme from localStorage', () => {
    localStorage.setItem('operion-theme', 'dark')
    render(
      <ThemeProvider>
        <TestConsumer />
      </ThemeProvider>,
    )
    expect(screen.getByTestId('theme').textContent).toBe('dark')
  })

  it('uses defaultTheme prop when nothing in localStorage', () => {
    render(
      <ThemeProvider defaultTheme="dark">
        <TestConsumer />
      </ThemeProvider>,
    )
    expect(screen.getByTestId('theme').textContent).toBe('dark')
  })

  it('uses custom storageKey prop', () => {
    localStorage.setItem('custom-key', 'dark')
    render(
      <ThemeProvider storageKey="custom-key">
        <TestConsumer />
      </ThemeProvider>,
    )
    expect(screen.getByTestId('theme').textContent).toBe('dark')
  })

  it('useTheme() outside provider uses defaults (context has initialState)', () => {
    // ThemeProviderContext is created with a non-undefined default,
    // so useTheme() will never throw; it returns the default value.
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    render(<TestConsumer />)
    expect(screen.getByTestId('theme').textContent).toBe('system')
    expect(screen.getByTestId('resolved-theme').textContent).toBe('light')
    consoleSpy.mockRestore()
  })
})
