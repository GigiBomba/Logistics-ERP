import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from '@/components/ui/card'

describe('Card', () => {
  it('renders children', () => {
    render(<Card>Card content</Card>)
    expect(screen.getByText('Card content')).toBeInTheDocument()
  })

  it('renders as a div element', () => {
    render(<Card>Test</Card>)
    expect(screen.getByText('Test').tagName).toBe('DIV')
  })

  it('includes hover effect classes', () => {
    render(<Card>Hover</Card>)
    const el = screen.getByText('Hover')
    expect(el.className).toContain('hover:shadow-md')
    expect(el.className).toContain('hover:border-primary/20')
  })

  it('applies base card classes', () => {
    render(<Card>Base</Card>)
    const el = screen.getByText('Base')
    expect(el.className).toContain('rounded-xl')
    expect(el.className).toContain('border')
    expect(el.className).toContain('bg-card')
    expect(el.className).toContain('shadow-sm')
  })

  it('forwards additional className', () => {
    render(<Card className="custom-class">Styled</Card>)
    const el = screen.getByText('Styled')
    expect(el.className).toContain('custom-class')
  })

  it('forwards ref', () => {
    const ref = { current: null }
    render(<Card ref={ref}>Ref</Card>)
    expect(ref.current).toBeInstanceOf(HTMLDivElement)
    expect(ref.current?.textContent).toBe('Ref')
  })
})

describe('CardHeader', () => {
  it('renders children', () => {
    render(<CardHeader>Header</CardHeader>)
    expect(screen.getByText('Header')).toBeInTheDocument()
  })

  it('renders as a div', () => {
    render(<CardHeader>Test</CardHeader>)
    expect(screen.getByText('Test').tagName).toBe('DIV')
  })

  it('applies default classes', () => {
    render(<CardHeader>Header</CardHeader>)
    const el = screen.getByText('Header')
    expect(el.className).toContain('flex')
    expect(el.className).toContain('p-6')
  })

  it('forwards className', () => {
    render(<CardHeader className="custom-header">Header</CardHeader>)
    expect(screen.getByText('Header').className).toContain('custom-header')
  })

  it('forwards ref', () => {
    const ref = { current: null }
    render(<CardHeader ref={ref}>Ref</CardHeader>)
    expect(ref.current).toBeInstanceOf(HTMLDivElement)
  })
})

describe('CardTitle', () => {
  it('renders children', () => {
    render(<CardTitle>Title</CardTitle>)
    expect(screen.getByText('Title')).toBeInTheDocument()
  })

  it('renders as an h3 element', () => {
    render(<CardTitle>Test</CardTitle>)
    expect(screen.getByText('Test').tagName).toBe('H3')
  })

  it('applies default classes', () => {
    render(<CardTitle>Title</CardTitle>)
    const el = screen.getByText('Title')
    expect(el.className).toContain('text-lg')
    expect(el.className).toContain('font-semibold')
  })

  it('forwards className', () => {
    render(<CardTitle className="custom-title">Title</CardTitle>)
    expect(screen.getByText('Title').className).toContain('custom-title')
  })

  it('forwards ref', () => {
    const ref = { current: null }
    render(<CardTitle ref={ref}>Ref</CardTitle>)
    expect(ref.current).toBeInstanceOf(HTMLHeadingElement)
  })
})

describe('CardDescription', () => {
  it('renders children', () => {
    render(<CardDescription>Description</CardDescription>)
    expect(screen.getByText('Description')).toBeInTheDocument()
  })

  it('renders as a paragraph element', () => {
    render(<CardDescription>Test</CardDescription>)
    expect(screen.getByText('Test').tagName).toBe('P')
  })

  it('applies default classes', () => {
    render(<CardDescription>Desc</CardDescription>)
    const el = screen.getByText('Desc')
    expect(el.className).toContain('text-sm')
    expect(el.className).toContain('text-muted-foreground')
  })

  it('forwards className', () => {
    render(<CardDescription className="custom-desc">Desc</CardDescription>)
    expect(screen.getByText('Desc').className).toContain('custom-desc')
  })

  it('forwards ref', () => {
    const ref = { current: null }
    render(<CardDescription ref={ref}>Ref</CardDescription>)
    expect(ref.current).toBeInstanceOf(HTMLParagraphElement)
  })
})

describe('CardContent', () => {
  it('renders children', () => {
    render(<CardContent>Content</CardContent>)
    expect(screen.getByText('Content')).toBeInTheDocument()
  })

  it('renders as a div', () => {
    render(<CardContent>Test</CardContent>)
    expect(screen.getByText('Test').tagName).toBe('DIV')
  })

  it('applies default classes', () => {
    render(<CardContent>Content</CardContent>)
    const el = screen.getByText('Content')
    expect(el.className).toContain('p-6')
    expect(el.className).toContain('pt-0')
  })

  it('forwards className', () => {
    render(<CardContent className="custom-content">Content</CardContent>)
    expect(screen.getByText('Content').className).toContain('custom-content')
  })

  it('forwards ref', () => {
    const ref = { current: null }
    render(<CardContent ref={ref}>Ref</CardContent>)
    expect(ref.current).toBeInstanceOf(HTMLDivElement)
  })
})

describe('CardFooter', () => {
  it('renders children', () => {
    render(<CardFooter>Footer</CardFooter>)
    expect(screen.getByText('Footer')).toBeInTheDocument()
  })

  it('renders as a div', () => {
    render(<CardFooter>Test</CardFooter>)
    expect(screen.getByText('Test').tagName).toBe('DIV')
  })

  it('applies default classes', () => {
    render(<CardFooter>Footer</CardFooter>)
    const el = screen.getByText('Footer')
    expect(el.className).toContain('flex')
    expect(el.className).toContain('p-6')
    expect(el.className).toContain('pt-0')
  })

  it('forwards className', () => {
    render(<CardFooter className="custom-footer">Footer</CardFooter>)
    expect(screen.getByText('Footer').className).toContain('custom-footer')
  })

  it('forwards ref', () => {
    const ref = { current: null }
    render(<CardFooter ref={ref}>Ref</CardFooter>)
    expect(ref.current).toBeInstanceOf(HTMLDivElement)
  })
})

describe('Card composition', () => {
  it('renders a complete card with all sub-components', () => {
    render(
      <Card>
        <CardHeader>
          <CardTitle>Card Title</CardTitle>
          <CardDescription>Card Description</CardDescription>
        </CardHeader>
        <CardContent>Main content</CardContent>
        <CardFooter>Footer actions</CardFooter>
      </Card>,
    )

    expect(screen.getByText('Card Title')).toBeInTheDocument()
    expect(screen.getByText('Card Description')).toBeInTheDocument()
    expect(screen.getByText('Main content')).toBeInTheDocument()
    expect(screen.getByText('Footer actions')).toBeInTheDocument()
  })

  describe('snapshots', () => {
    it('matches snapshot for Card', () => {
      const { container } = render(<Card>Card content</Card>)
      expect(container.firstChild).toMatchSnapshot()
    })

    it('matches snapshot for CardHeader', () => {
      const { container } = render(<CardHeader>Header</CardHeader>)
      expect(container.firstChild).toMatchSnapshot()
    })

    it('matches snapshot for CardTitle', () => {
      const { container } = render(<CardTitle>Title</CardTitle>)
      expect(container.firstChild).toMatchSnapshot()
    })

    it('matches snapshot for CardDescription', () => {
      const { container } = render(<CardDescription>Description</CardDescription>)
      expect(container.firstChild).toMatchSnapshot()
    })

    it('matches snapshot for CardContent', () => {
      const { container } = render(<CardContent>Content</CardContent>)
      expect(container.firstChild).toMatchSnapshot()
    })

    it('matches snapshot for CardFooter', () => {
      const { container } = render(<CardFooter>Footer</CardFooter>)
      expect(container.firstChild).toMatchSnapshot()
    })

    it('matches snapshot for composed card', () => {
      const { container } = render(
        <Card>
          <CardHeader>
            <CardTitle>Card Title</CardTitle>
            <CardDescription>Card Description</CardDescription>
          </CardHeader>
          <CardContent>Main content</CardContent>
          <CardFooter>Footer actions</CardFooter>
        </Card>,
      )
      expect(container.firstChild).toMatchSnapshot()
    })
  })
})
