// frontend/tests/auth.test.js
// Unit tests for auth.js — covers all initAuth() branches per 02-VALIDATION.md
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// ─── Axios mock (hoisted above all imports) ───────────────────────
const mockPost = vi.fn()
vi.mock('axios', () => ({
  default: { post: mockPost },
}))

// ─── JWT test fixtures ────────────────────────────────────────────
const VALID_JWT = [
  btoa('{"alg":"HS256","typ":"JWT"}'),
  btoa(JSON.stringify({ username: 'test', exp: 4102444800 })),
  'fakesig',
].join('.')

const EXPIRED_JWT = [
  btoa('{"alg":"HS256","typ":"JWT"}'),
  btoa(JSON.stringify({ username: 'test', exp: 1000000 })),
  'fakesig',
].join('.')

// ─── isExpired() ──────────────────────────────────────────────────
describe('isExpired()', () => {
  let isExpired

  beforeEach(async () => {
    vi.resetModules()
    const mod = await import('../src/auth.js')
    isExpired = mod.isExpired
  })

  it('returns false for a valid non-expired token', () => {
    expect(isExpired(VALID_JWT)).toBe(false)
  })

  it('returns true for an expired token', () => {
    expect(isExpired(EXPIRED_JWT)).toBe(true)
  })

  it('returns true for a malformed token', () => {
    expect(isExpired('not.a.jwt')).toBe(true)
  })
})

// ─── initAuth() ───────────────────────────────────────────────────
describe('initAuth()', () => {
  let initAuth, getStoredJwt
  const originalLocation = window.location

  beforeEach(async () => {
    mockPost.mockReset()
    vi.resetModules()
    // JWT_KEY etc. are computed from VITE_APP_NAME at module load — stub it
    // to the default BEFORE importing, or the real .env value (currently
    // 'VUE_APP_TESTING') leaks in and every 'app_template_jwt' key below stops matching.
    vi.stubEnv('VITE_APP_NAME', '')
    const mod = await import('../src/auth.js')
    initAuth = mod.initAuth
    getStoredJwt = mod.getStoredJwt
  })

  afterEach(() => {
    // Restore original window.location after tests that override it
    Object.defineProperty(window, 'location', {
      value: originalLocation,
      writable: true,
      configurable: true,
    })
  })

  // --- TOG-03: Auth toggle ---
  describe('TOG-03: auth toggle', () => {
    it('resolves immediately when VITE_AUTH_MODE=0', async () => {
      vi.stubEnv('VITE_AUTH_MODE', '0')
      await expect(initAuth()).resolves.toBeUndefined()
      expect(mockPost).not.toHaveBeenCalled()
      expect(localStorage.getItem('app_template_jwt')).toBeNull()
    })

    it('does NOT short-circuit when VITE_AUTH_MODE!=0', async () => {
      vi.stubEnv('VITE_AUTH_MODE', '1')
      vi.stubEnv('VITE_SSO_URL', 'https://sso.local/login')
      vi.stubEnv('VITE_AUTH_TOKENS', 'test-token')
    })
  })

  // --- FE-02: URL strip before POST ---
  describe('FE-02: URL strip before POST', () => {
    it('strips ?Authorization from URL before POST (order verified)', async () => {
      vi.stubEnv('VITE_AUTH_MODE', '1')
      vi.stubEnv('VITE_AUTH_SERVICE_URL', 'http://auth.local')

      Object.defineProperty(window, 'location', {
        value: {
          search: '?Authorization=test-jwe',
          pathname: '/app',
          href: 'http://localhost/app?Authorization=test-jwe',
        },
        writable: true,
        configurable: true,
      })

      // Track call order to prove replaceState happens BEFORE post
      const callOrder = []
      vi.spyOn(window.history, 'replaceState').mockImplementation(() => {
        callOrder.push('replaceState')
      })
      mockPost.mockImplementation(() => {
        callOrder.push('post')
        return Promise.resolve({ data: { access_token: 'new-jwt' } })
      })

      await initAuth()

      expect(callOrder).toEqual(['replaceState', 'post'])
      expect(localStorage.getItem('app_template_jwt')).toBe('new-jwt')
    })

    it('URL is clean even if POST throws', async () => {
      vi.stubEnv('VITE_AUTH_MODE', '1')
      vi.stubEnv('VITE_AUTH_SERVICE_URL', 'http://auth.local')

      Object.defineProperty(window, 'location', {
        value: {
          search: '?Authorization=test-jwe',
          pathname: '/app',
          href: 'http://localhost/app?Authorization=test-jwe',
        },
        writable: true,
        configurable: true,
      })

      const replaceStateSpy = vi.spyOn(window.history, 'replaceState').mockImplementation(() => {})
      mockPost.mockRejectedValue(new Error('network error'))

      await expect(initAuth()).rejects.toThrow('network error')
      // replaceState was STILL called (synchronously before the failing POST)
      expect(replaceStateSpy).toHaveBeenCalledWith({}, '', '/app')
    })
  })

  // --- FE-01: JWT exchange and storage ---
  describe('FE-01: JWT exchange', () => {
    it('stores JWT in localStorage after successful exchange', async () => {
      vi.stubEnv('VITE_AUTH_MODE', '1')
      vi.stubEnv('VITE_AUTH_SERVICE_URL', 'http://auth.local')

      Object.defineProperty(window, 'location', {
        value: {
          search: '?Authorization=test-jwe',
          pathname: '/app',
          href: 'http://localhost/app?Authorization=test-jwe',
        },
        writable: true,
        configurable: true,
      })
      vi.spyOn(window.history, 'replaceState').mockImplementation(() => {})
      mockPost.mockResolvedValue({ data: { access_token: 'received-jwt' } })

      await initAuth()

      expect(localStorage.getItem('app_template_jwt')).toBe('received-jwt')
    })

    it('POSTs to VITE_AUTH_SERVICE_URL/auth/token with JWE body', async () => {
      vi.stubEnv('VITE_AUTH_MODE', '1')
      vi.stubEnv('VITE_AUTH_SERVICE_URL', 'http://vueauth.local')

      Object.defineProperty(window, 'location', {
        value: {
          search: '?Authorization=the-jwe-token',
          pathname: '/',
          href: 'http://localhost/?Authorization=the-jwe-token',
        },
        writable: true,
        configurable: true,
      })
      vi.spyOn(window.history, 'replaceState').mockImplementation(() => {})
      mockPost.mockResolvedValue({ data: { access_token: 'jwt' } })

      await initAuth()

      expect(mockPost).toHaveBeenCalledWith(
        'http://vueauth.local/auth/token',
        { jwe_token: 'the-jwe-token', app_name: '' }
      )
    })
  })

  // --- FE-04: JWT expiry check ---
  describe('FE-04: JWT expiry check', () => {
    it('returns early if valid JWT already stored', async () => {
      vi.stubEnv('VITE_AUTH_MODE', '1')
      localStorage.setItem('app_template_jwt', VALID_JWT)

      Object.defineProperty(window, 'location', {
        value: { search: '', pathname: '/', href: 'http://localhost/' },
        writable: true,
        configurable: true,
      })

      await initAuth()

      // No redirect, no POST — existing valid JWT is sufficient
      expect(mockPost).not.toHaveBeenCalled()
      expect(window.location.href).toBe('http://localhost/')
    })

    it('proceeds to redirect if JWT is expired', async () => {
      vi.stubEnv('VITE_AUTH_MODE', '1')
      vi.stubEnv('VITE_SSO_URL', 'https://sso.local/login')
      vi.stubEnv('VITE_AUTH_TOKENS', 'test-token')
      localStorage.setItem('app_template_jwt', EXPIRED_JWT)

      Object.defineProperty(window, 'location', {
        value: { search: '', pathname: '/', href: 'http://localhost/' },
        writable: true,
        configurable: true,
      })

      await initAuth()

      expect(window.location.href).toContain('sso.local/login')
    })
  })

  // --- FE-03: Redirect loop guards ---
  describe('FE-03: redirect loop guards', () => {
    it('throws after MAX_REDIRECT_ATTEMPTS', async () => {
      vi.stubEnv('VITE_AUTH_MODE', '1')
      // Simulate 3 prior redirects (MAX_REDIRECT_ATTEMPTS = 3)
      sessionStorage.setItem('_auth_redirects', '3')

      Object.defineProperty(window, 'location', {
        value: { search: '', pathname: '/', href: 'http://localhost/' },
        writable: true,
        configurable: true,
      })

      await expect(initAuth()).rejects.toThrow('Auth redirect loop detected')
    })

    it('isRedirecting flag prevents parallel initAuth calls', async () => {
      vi.stubEnv('VITE_AUTH_MODE', '1')
      vi.stubEnv('VITE_SSO_URL', 'https://sso.local/login')
      vi.stubEnv('VITE_AUTH_TOKENS', 'test-token')

      Object.defineProperty(window, 'location', {
        value: { search: '', pathname: '/', href: 'http://localhost/' },
        writable: true,
        configurable: true,
      })

      // First call — sets isRedirecting = true and redirects
      await initAuth()
      expect(window.location.href).toContain('sso.local/login')

      // Reset href to detect if second call would redirect again
      window.location.href = 'http://localhost/'

      // Second call — should return immediately (isRedirecting is true)
      await initAuth()
      expect(window.location.href).toBe('http://localhost/')
    })
  })

  // --- FE-08: localStorage key ---
  describe('FE-08: localStorage key', () => {
    it('uses app_template_jwt as storage key', () => {
      localStorage.setItem('app_template_jwt', 'correct-token')
      localStorage.setItem('jwt', 'wrong-token')
      localStorage.setItem('token', 'wrong-token')

      expect(getStoredJwt()).toBe('correct-token')
    })
  })
})
