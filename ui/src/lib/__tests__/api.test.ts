import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import {
  api,
  setTokens,
  clearTokens,
  getStoredUser,
  getStoredRefreshToken,
} from '@/lib/api'

// ── Helpers ─────────────────────────────────────────────────────────────

function mockFetchOnce(response: Partial<Response>, body?: unknown) {
  const mockFetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(body ?? { data: 'ok' }),
    ...response,
  })
  vi.stubGlobal('fetch', mockFetch)
  return mockFetch
}

function assertRequestUrl(mockFetch: ReturnType<typeof vi.fn>, expectedPath: string) {
  const url: string = mockFetch.mock.calls[0][0]
  expect(url).toContain(expectedPath)
}

function assertRequestMethod(mockFetch: ReturnType<typeof vi.fn>, expectedMethod: string) {
  const method: string = mockFetch.mock.calls[0][1]?.method ?? 'GET'
  expect(method).toBe(expectedMethod)
}

function assertRequestBody(mockFetch: ReturnType<typeof vi.fn>, expectedBody: string) {
  const body: string = mockFetch.mock.calls[0][1]?.body ?? ''
  expect(body).toBe(expectedBody)
}

// ── Tests ───────────────────────────────────────────────────────────────

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

      const mockFetch = mockFetchOnce({ ok: true })

      await api.get('/test')

      const callHeaders = mockFetch.mock.calls[0][1].headers
      expect(callHeaders['Authorization']).toBe('Bearer test-token-123')
    })

    it('does not attach Authorization header when no token', async () => {
      const mockFetch = mockFetchOnce({ ok: true })

      await api.get('/test')

      const callHeaders = mockFetch.mock.calls[0][1].headers
      expect(callHeaders['Authorization']).toBeUndefined()
    })

    // VITE_API_KEY is a compile-time constant (import.meta.env is not writable
    // in vitest). The API key header behavior is covered by integration tests.
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

    it('non-ok response throws with HTTP status when no detail is returned', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
        json: () => Promise.resolve({}),
      })
      vi.stubGlobal('fetch', mockFetch)

      await expect(api.get('/forbidden')).rejects.toThrow('HTTP 403')
    })

    it('network failure (fetch throws) is propagated', async () => {
      vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

      await expect(api.get('/fail')).rejects.toThrow(TypeError)
      await expect(api.get('/fail')).rejects.toThrow('Failed to fetch')
    })

    it('network failure with custom error message', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockRejectedValue(new Error('NetworkError: Unable to connect')),
      )

      await expect(api.get('/fail')).rejects.toThrow('Unable to connect')
    })

    it('timeout (AbortController signal) is propagated as DOMException', async () => {
      const abortError = new DOMException('The operation was aborted', 'AbortError')
      vi.stubGlobal('fetch', vi.fn().mockRejectedValue(abortError))

      await expect(api.get('/timeout')).rejects.toThrow(DOMException)
      await expect(api.get('/timeout')).rejects.toThrow('The operation was aborted')
    })
  })

  describe('non-JSON response handling', () => {
    afterEach(() => {
      vi.restoreAllMocks()
    })

    it('parses JSON when Content-Type is application/json', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve({ message: 'hello' }),
      })
      vi.stubGlobal('fetch', mockFetch)

      const result = await api.get<{ message: string }>('/hello')
      expect(result.message).toBe('hello')
    })

    it('handles JSON response with array body', async () => {
      const data = [{ id: 1 }, { id: 2 }]
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(data),
      })
      vi.stubGlobal('fetch', mockFetch)

      const result = await api.get<Array<{ id: number }>>('/list')
      expect(Array.isArray(result)).toBe(true)
      expect(result).toHaveLength(2)
    })
  })

  describe('api.post method', () => {
    afterEach(() => {
      vi.restoreAllMocks()
    })

    it('sends POST request with JSON body', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ id: 42 }),
      })
      vi.stubGlobal('fetch', mockFetch)

      const body = { name: 'Test', value: 123 }
      const result = await api.post<{ id: number }>('/create', body)

      expect(result.id).toBe(42)
      assertRequestUrl(mockFetch, '/create')
      assertRequestMethod(mockFetch, 'POST')
      assertRequestBody(mockFetch, JSON.stringify(body))
    })

    it('sends POST with empty object body', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ ok: true }),
      })
      vi.stubGlobal('fetch', mockFetch)

      await api.post('/no-body', {})

      assertRequestBody(mockFetch, '{}')
    })

    it('sends POST with Content-Type application/json', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({}),
      })
      vi.stubGlobal('fetch', mockFetch)

      await api.post('/create', { key: 'value' })

      const headers = mockFetch.mock.calls[0][1].headers
      expect(headers['Content-Type']).toBe('application/json')
    })

    it('POST non-ok response throws error', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 409,
        json: () => Promise.resolve({ detail: 'Conflict' }),
      })
      vi.stubGlobal('fetch', mockFetch)

      await expect(api.post('/conflict', {})).rejects.toThrow('Conflict')
    })

    it('POST network failure is propagated', async () => {
      vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

      await expect(api.post('/fail', {})).rejects.toThrow(TypeError)
    })
  })

  describe('api.postForm method', () => {
    afterEach(() => {
      vi.restoreAllMocks()
    })

    it('sends POST request with URL-encoded body', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ access_token: 'token-123' }),
      })
      vi.stubGlobal('fetch', mockFetch)

      const result = await api.postForm<{ access_token: string }>('/token', {
        username: 'a@b.com',
        password: 'secret',
      })

      expect(result.access_token).toBe('token-123')
      assertRequestUrl(mockFetch, '/token')
      assertRequestMethod(mockFetch, 'POST')
    })

    it('URL-encodes form fields correctly', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({}),
      })
      vi.stubGlobal('fetch', mockFetch)

      await api.postForm('/login', {
        username: 'user@example.com',
        password: 'p@ss!w0rd',
      })

      const body = mockFetch.mock.calls[0][1].body
      expect(body).toContain('username=user%40example.com')
      expect(body).toContain('password=p%40ss%21w0rd')
    })

    it('sends Content-Type application/x-www-form-urlencoded', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({}),
      })
      vi.stubGlobal('fetch', mockFetch)

      await api.postForm('/token', { grant_type: 'password' })

      const headers = mockFetch.mock.calls[0][1].headers
      expect(headers['Content-Type']).toBe('application/x-www-form-urlencoded')
    })

    it('postForm non-ok response throws error', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        json: () => Promise.resolve({ detail: 'Invalid credentials' }),
      })
      vi.stubGlobal('fetch', mockFetch)

      await expect(
        api.postForm('/token', { username: 'a', password: 'b' }),
      ).rejects.toThrow('Invalid credentials')
    })

    it('postForm network failure is propagated', async () => {
      vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

      await expect(api.postForm('/token', {})).rejects.toThrow(TypeError)
    })

    it('handles empty form body', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({}),
      })
      vi.stubGlobal('fetch', mockFetch)

      await api.postForm('/empty', {})

      assertRequestBody(mockFetch, '')
    })

    it('merges auth headers with form content-type header', async () => {
      localStorage.setItem('operion_access_token', 'test-token')

      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({}),
      })
      vi.stubGlobal('fetch', mockFetch)

      await api.postForm('/token', { username: 'test' })

      const headers = mockFetch.mock.calls[0][1].headers
      expect(headers['Content-Type']).toBe('application/x-www-form-urlencoded')
      expect(headers['Authorization']).toBe('Bearer test-token')
    })
  })
})
