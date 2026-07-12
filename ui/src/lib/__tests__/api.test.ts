import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import {
  api,
  setTokens,
  clearTokens,
  getStoredUser,
  getStoredRefreshToken,
} from '@/lib/api'

describe('API module', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  describe('authHeaders behavior (via api.get request)', () => {
    afterEach(() => {
      vi.restoreAllMocks()
    })

    it('attaches Bearer token when token exists', async () => {
      localStorage.setItem('operion_access_token', 'test-token-123')

      // Mock fetch to capture the request
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ data: 'ok' }),
      })
      vi.stubGlobal('fetch', mockFetch)

      await api.get('/test')

      const callHeaders = mockFetch.mock.calls[0][1].headers
      expect(callHeaders['Authorization']).toBe('Bearer test-token-123')
    })

    it('does not attach Authorization header when no token', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ data: 'ok' }),
      })
      vi.stubGlobal('fetch', mockFetch)

      await api.get('/test')

      const callHeaders = mockFetch.mock.calls[0][1].headers
      expect(callHeaders['Authorization']).toBeUndefined()
    })
  })

  describe('setTokens() and clearTokens()', () => {
    it('setTokens() stores access token in localStorage', () => {
      setTokens({
        access_token: 'access-123',
        refresh_token: 'refresh-456',
        token_type: 'bearer',
        expires_in: 3600,
      })
      expect(localStorage.getItem('operion_access_token')).toBe('access-123')
    })

    it('setTokens() stores user info when provided', () => {
      const user = {
        id: 1,
        email: 'test@example.com',
        role: 'admin',
        company_id: 42,
        display_name: 'Test User',
      }
      setTokens(
        {
          access_token: 'access-123',
          refresh_token: 'refresh-456',
          token_type: 'bearer',
          expires_in: 3600,
        },
        user,
      )
      const stored = JSON.parse(localStorage.getItem('operion_user')!)
      expect(stored.email).toBe('test@example.com')
      expect(stored.display_name).toBe('Test User')
    })

    it('clearTokens() removes access token and user info', () => {
      localStorage.setItem('operion_access_token', 'access-123')
      localStorage.setItem('operion_user', JSON.stringify({ email: 'test@example.com' }))
      clearTokens()
      expect(localStorage.getItem('operion_access_token')).toBeNull()
      expect(localStorage.getItem('operion_user')).toBeNull()
    })
  })

  describe('getStoredUser()', () => {
    it('returns parsed user from localStorage', () => {
      const user = { id: 1, email: 'test@example.com', role: 'admin', company_id: 0, display_name: 'Test' }
      localStorage.setItem('operion_user', JSON.stringify(user))
      expect(getStoredUser()).toEqual(user)
    })

    it('returns null when no user stored', () => {
      expect(getStoredUser()).toBeNull()
    })

    it('returns null on invalid JSON', () => {
      localStorage.setItem('operion_user', 'not-json')
      expect(getStoredUser()).toBeNull()
    })
  })

  describe('getStoredRefreshToken()', () => {
    it('returns null (httpOnly cookie strategy)', () => {
      expect(getStoredRefreshToken()).toBeNull()
    })
  })

  describe('request error handling (via api.get)', () => {
    afterEach(() => {
      vi.restoreAllMocks()
    })

    it('non-ok response throws Error with message from body.detail', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
        json: () => Promise.resolve({ detail: 'Bad request error' }),
      })
      vi.stubGlobal('fetch', mockFetch)

      await expect(api.get('/fail')).rejects.toThrow('Bad request error')
    })

    it('non-ok response throws "Request failed" when json parsing fails', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: () => Promise.reject(new Error('parse error')),
      })
      vi.stubGlobal('fetch', mockFetch)

      await expect(api.get('/fail')).rejects.toThrow('Request failed')
    })
  })
})
