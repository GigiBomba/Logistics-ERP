import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Input, Label, Textarea } from '@/components/ui/input'

describe('Input', () => {
  it('renders an input element', () => {
    render(<Input />)
    const input = screen.getByRole('textbox')
    expect(input).toBeInTheDocument()
    expect(input.tagName).toBe('INPUT')
  })

  it('forwards ref to the underlying input', () => {
    const ref = { current: null }
    render(<Input ref={ref} />)
    expect(ref.current).toBeInstanceOf(HTMLInputElement)
  })

  it('accepts and displays a placeholder', () => {
    render(<Input placeholder="Enter text" />)
    const input = screen.getByPlaceholderText('Enter text')
    expect(input).toBeInTheDocument()
  })

  it('applies default input classes', () => {
    render(<Input />)
    const input = screen.getByRole('textbox')
    expect(input.className).toContain('flex')
    expect(input.className).toContain('h-10')
    expect(input.className).toContain('w-full')
    expect(input.className).toContain('rounded-lg')
    expect(input.className).toContain('border-input')
  })

  it('includes focus-visible classes', () => {
    render(<Input />)
    const input = screen.getByRole('textbox')
    expect(input.className).toContain('focus-visible:outline-none')
    expect(input.className).toContain('focus-visible:ring-2')
  })

  it('includes disabled classes and disabled attribute', () => {
    render(<Input disabled />)
    const input = screen.getByRole('textbox')
    expect(input).toBeDisabled()
    expect(input.className).toContain('disabled:cursor-not-allowed')
    expect(input.className).toContain('disabled:opacity-50')
  })

  it('does not fire onChange when disabled', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<Input disabled onChange={onChange} />)
    const input = screen.getByRole('textbox')
    await user.type(input, 'a')
    expect(onChange).not.toHaveBeenCalled()
  })

  it('fires onChange when typing', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<Input onChange={onChange} />)
    const input = screen.getByRole('textbox')
    await user.type(input, 'hello')
    expect(onChange).toHaveBeenCalled()
  })

  it('forwards additional className', () => {
    render(<Input className="my-custom-input" />)
    const input = screen.getByRole('textbox')
    expect(input.className).toContain('my-custom-input')
  })

  it('accepts a type prop', () => {
    render(<Input type="email" />)
    const input = screen.getByRole('textbox')
    expect(input).toHaveAttribute('type', 'email')
  })

  it('spreads additional HTML attributes', () => {
    render(<Input data-testid="test-input" id="input-id" />)
    const input = screen.getByTestId('test-input')
    expect(input).toHaveAttribute('id', 'input-id')
  })

  it('supports controlled value', () => {
    render(<Input value="controlled" onChange={() => {}} />)
    const input = screen.getByRole('textbox')
    expect(input).toHaveValue('controlled')
  })

  it('applies hover classes', () => {
    render(<Input />)
    const input = screen.getByRole('textbox')
    expect(input.className).toContain('hover:border-primary/30')
  })
})

describe('Label', () => {
  it('renders a label element', () => {
    render(<Label>Username</Label>)
    const label = screen.getByText('Username')
    expect(label).toBeInTheDocument()
    expect(label.tagName).toBe('LABEL')
  })

  it('forwards ref', () => {
    const ref = { current: null }
    render(<Label ref={ref}>Label</Label>)
    expect(ref.current).toBeInstanceOf(HTMLLabelElement)
  })

  it('applies default classes', () => {
    render(<Label>Label</Label>)
    const label = screen.getByText('Label')
    expect(label.className).toContain('text-sm')
    expect(label.className).toContain('font-medium')
  })

  it('forwards additional className', () => {
    render(<Label className="custom-label">Label</Label>)
    expect(screen.getByText('Label').className).toContain('custom-label')
  })

  it('associates with an input via htmlFor', () => {
    render(
      <>
        <Label htmlFor="email">Email</Label>
        <Input id="email" />
      </>,
    )
    const label = screen.getByText('Email')
    expect(label).toHaveAttribute('for', 'email')
    const input = screen.getByRole('textbox')
    expect(input).toHaveAttribute('id', 'email')
  })
})

describe('Textarea', () => {
  it('renders a textarea element', () => {
    render(<Textarea />)
    const textarea = screen.getByRole('textbox')
    expect(textarea).toBeInTheDocument()
    expect(textarea.tagName).toBe('TEXTAREA')
  })

  it('forwards ref', () => {
    const ref = { current: null }
    render(<Textarea ref={ref} />)
    expect(ref.current).toBeInstanceOf(HTMLTextAreaElement)
  })

  it('accepts and displays a placeholder', () => {
    render(<Textarea placeholder="Enter description" />)
    const textarea = screen.getByPlaceholderText('Enter description')
    expect(textarea).toBeInTheDocument()
  })

  it('applies default textarea classes', () => {
    render(<Textarea />)
    const textarea = screen.getByRole('textbox')
    expect(textarea.className).toContain('min-h-[100px]')
    expect(textarea.className).toContain('w-full')
    expect(textarea.className).toContain('rounded-lg')
    expect(textarea.className).toContain('border-input')
  })

  it('includes focus-visible classes', () => {
    render(<Textarea />)
    const textarea = screen.getByRole('textbox')
    expect(textarea.className).toContain('focus-visible:outline-none')
    expect(textarea.className).toContain('focus-visible:ring-2')
  })

  it('includes disabled classes and disabled attribute', () => {
    render(<Textarea disabled />)
    const textarea = screen.getByRole('textbox')
    expect(textarea).toBeDisabled()
    expect(textarea.className).toContain('disabled:cursor-not-allowed')
    expect(textarea.className).toContain('disabled:opacity-50')
  })

  it('forwards additional className', () => {
    render(<Textarea className="custom-textarea" />)
    const textarea = screen.getByRole('textbox')
    expect(textarea.className).toContain('custom-textarea')
  })

  it('fires onChange when typing', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<Textarea onChange={onChange} />)
    const textarea = screen.getByRole('textbox')
    await user.type(textarea, 'hello')
    expect(onChange).toHaveBeenCalled()
  })

  it('does not fire onChange when disabled', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<Textarea disabled onChange={onChange} />)
    const textarea = screen.getByRole('textbox')
    await user.type(textarea, 'a')
    expect(onChange).not.toHaveBeenCalled()
  })

  it('applies hover classes', () => {
    render(<Textarea />)
    const textarea = screen.getByRole('textbox')
    expect(textarea.className).toContain('hover:border-primary/30')
  })

  it('supports controlled value', () => {
    render(<Textarea value="controlled text" onChange={() => {}} />)
    const textarea = screen.getByRole('textbox')
    expect(textarea).toHaveValue('controlled text')
  })
})
