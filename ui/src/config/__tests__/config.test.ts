import { describe, it, expect } from 'vitest'
import { siteConfig } from '@/config/site'
import { publicNavItems, authNavItems } from '@/config/navigation'
import type { NavItem } from '@/config/navigation'

// ---------------------------------------------------------------------------
// siteConfig
// ---------------------------------------------------------------------------
describe('siteConfig', () => {
  it('has a name', () => {
    expect(siteConfig.name).toBe('Operion ERP')
  })

  it('has a description', () => {
    expect(siteConfig.description).toBe(
      'Modern enterprise resource planning for growing businesses.',
    )
  })

  it('has a valid url', () => {
    expect(siteConfig.url).toBe('https://operion.io')
  })

  it('has an ogImage', () => {
    expect(siteConfig.ogImage).toBe('https://operion.io/og.jpg')
  })

  describe('links', () => {
    it('has twitter link', () => {
      expect(siteConfig.links.twitter).toBe('https://twitter.com/operion')
    })

    it('has github link', () => {
      expect(siteConfig.links.github).toBe('https://github.com/operion')
    })

    it('has docs link', () => {
      expect(siteConfig.links.docs).toBe('https://docs.operion.io')
    })
  })

  describe('contact', () => {
    it('has an email', () => {
      expect(siteConfig.contact.email).toBe('hello@operion.io')
    })

    it('has a phone number', () => {
      expect(siteConfig.contact.phone).toBe('+1 (555) 123-4567')
    })
  })
})

// ---------------------------------------------------------------------------
// navigation – publicNavItems
// ---------------------------------------------------------------------------
describe('publicNavItems', () => {
  it('has the expected number of items', () => {
    expect(publicNavItems).toHaveLength(5)
  })

  it.each(publicNavItems)('$label has required properties', (item: NavItem) => {
    expect(item).toHaveProperty('label')
    expect(typeof item.label).toBe('string')
    expect(item.label.length).toBeGreaterThan(0)

    expect(item).toHaveProperty('href')
    expect(typeof item.href).toBe('string')
    expect(item.href.startsWith('/')).toBe(true)
  })

  it('includes Features', () => {
    expect(publicNavItems.find((n) => n.label === 'Features')?.href).toBe(
      '/features',
    )
  })

  it('includes Pricing', () => {
    expect(publicNavItems.find((n) => n.label === 'Pricing')?.href).toBe(
      '/pricing',
    )
  })

  it('includes About', () => {
    expect(publicNavItems.find((n) => n.label === 'About')?.href).toBe('/about')
  })

  it('includes Docs with external flag', () => {
    const docs = publicNavItems.find((n) => n.label === 'Docs')
    expect(docs?.href).toBe('/docs')
    expect(docs?.external).toBe(true)
  })

  it('includes Support', () => {
    expect(publicNavItems.find((n) => n.label === 'Support')?.href).toBe(
      '/support',
    )
  })

  it('every public item has an icon component', () => {
    for (const item of publicNavItems) {
      expect(item.icon).toBeDefined()
    }
  })
})

// ---------------------------------------------------------------------------
// navigation – authNavItems
// ---------------------------------------------------------------------------
describe('authNavItems', () => {
  it('has the expected number of items', () => {
    expect(authNavItems).toHaveLength(4)
  })

  it.each(authNavItems)('$label has required properties', (item: NavItem) => {
    expect(item).toHaveProperty('label')
    expect(typeof item.label).toBe('string')
    expect(item.label.length).toBeGreaterThan(0)

    expect(item).toHaveProperty('href')
    expect(typeof item.href).toBe('string')
    expect(item.href.startsWith('/')).toBe(true)
  })

  it('includes Dashboard', () => {
    expect(authNavItems.find((n) => n.label === 'Dashboard')?.href).toBe(
      '/dashboard',
    )
  })

  it('includes Analytics', () => {
    expect(authNavItems.find((n) => n.label === 'Analytics')?.href).toBe(
      '/analytics',
    )
  })

  it('includes Team', () => {
    expect(authNavItems.find((n) => n.label === 'Team')?.href).toBe('/team')
  })

  it('includes Settings', () => {
    expect(authNavItems.find((n) => n.label === 'Settings')?.href).toBe(
      '/settings',
    )
  })

  it('every auth item has an icon component', () => {
    for (const item of authNavItems) {
      expect(item.icon).toBeDefined()
    }
  })

  it('no auth items have external flag', () => {
    for (const item of authNavItems) {
      expect(item.external).toBeUndefined()
    }
  })
})
