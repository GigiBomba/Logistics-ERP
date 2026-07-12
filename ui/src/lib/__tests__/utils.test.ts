import { describe, it, expect } from 'vitest'
import { cn } from '@/lib/utils'

describe('cn()', () => {
  it('merges class names', () => {
    expect(cn('foo', 'bar')).toBe('foo bar')
  })

  it('handles falsy values (false, null, undefined)', () => {
    expect(cn('foo', false, null, undefined, 'bar')).toBe('foo bar')
  })

  it('handles conditional classes', () => {
    expect(cn('base', true && 'visible', false && 'hidden')).toBe('base visible')
  })

  it('handles tailwind-merge conflicts', () => {
    // tailwind-merge should resolve conflicting classes
    const result = cn('px-4', 'px-2')
    expect(result).toBe('px-2')
  })
})
