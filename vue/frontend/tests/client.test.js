// frontend/tests/client.test.js
// Unit tests for api/client.js — covers request + response interceptors
import { describe, it, expect, vi, beforeEach } from 'vitest'

// ─── Mock auth module (hoisted) ───────────────────────────────────
vi.mock('../src/auth.js', () => ({
  getStoredJwt: vi.fn(),
  logout: vi.fn(),
  initAuth: vi.fn(),
}))

// ─── Tests ────────────────────────────────────────────────────────
describe('apiClient', () => {
  let apiClient, getStoredJwt, logout, initAuth

  beforeEach(async () => {
    // Reset modules for fresh isRedirecting state in client.js
    vi.resetModules()
    // Clear accumulated call counts on all mocks (vi.fn() instances are reused
    // across resets, so call counts must be cleared explicitly each test)
    vi.clearAllMocks()
    // client.js reads baseURL from VITE_API_URL at import time — pin it to the
    // shipped default ('/api', proxied by vite.config.js) rather than whatever
    // the local .env currently points at (e.g. a LAN hostname for remote access).
    vi.stubEnv('VITE_API_URL', '/api')

    // Re-import mocked auth to get fresh mock function references
    const authMod = await import('../src/auth.js')
    getStoredJwt = authMod.getStoredJwt
    logout = authMod.logout
    initAuth = authMod.initAuth

    // Re-import client for fresh isRedirecting state
    const clientMod = await import('../src/api/client.js')
    apiClient = clientMod.apiClient
  })

  // --- FE-05: Request interceptor ---
  describe('request interceptor (FE-05)', () => {
    it('attaches Bearer token when JWT exists', async () => {
      getStoredJwt.mockReturnValue('test-jwt-token')

      let capturedConfig
      apiClient.defaults.adapter = (config) => {
        capturedConfig = config
        return Promise.resolve({
          data: {}, status: 200, statusText: 'OK', headers: {}, config,
        })
      }

      await apiClient.get('/test')

      // Check Authorization header — AxiosHeaders supports both property and .get()
      const authHeader = capturedConfig.headers.Authorization
        || capturedConfig.headers.get?.('Authorization')
      expect(authHeader).toBe('Bearer test-jwt-token')
    })

    it('skips Authorization header when no JWT stored', async () => {
      getStoredJwt.mockReturnValue(null)

      let capturedConfig
      apiClient.defaults.adapter = (config) => {
        capturedConfig = config
        return Promise.resolve({
          data: {}, status: 200, statusText: 'OK', headers: {}, config,
        })
      }

      await apiClient.get('/test')

      const authHeader = capturedConfig.headers.Authorization
        || capturedConfig.headers.get?.('Authorization')
      expect(authHeader).toBeFalsy()
    })
  })

  // --- FE-06: Response interceptor ---
  describe('response interceptor (FE-06)', () => {
    it('clears JWT and calls initAuth on 401', async () => {
      apiClient.defaults.adapter = () =>
        Promise.reject({ response: { status: 401 } })

      await apiClient.get('/test').catch(() => {})

      expect(logout).toHaveBeenCalled()
      expect(initAuth).toHaveBeenCalled()
    })

    it('parallel 401s only trigger one initAuth call', async () => {
      apiClient.defaults.adapter = () =>
        Promise.reject({ response: { status: 401 } })

      await Promise.allSettled([
        apiClient.get('/test1'),
        apiClient.get('/test2'),
      ])

      // isRedirecting guard prevents second call
      expect(initAuth).toHaveBeenCalledTimes(1)
    })

    it('does not call initAuth on non-401 errors', async () => {
      apiClient.defaults.adapter = () =>
        Promise.reject({ response: { status: 500 } })

      await apiClient.get('/test').catch(() => {})

      expect(logout).not.toHaveBeenCalled()
      expect(initAuth).not.toHaveBeenCalled()
    })

    it('passes through successful responses', async () => {
      apiClient.defaults.adapter = (config) =>
        Promise.resolve({
          data: { ok: true }, status: 200, statusText: 'OK', headers: {}, config,
        })

      const res = await apiClient.get('/test')
      expect(res.data).toEqual({ ok: true })
    })
  })

  // --- baseURL ---
  it('uses /api as baseURL', () => {
    expect(apiClient.defaults.baseURL).toBe('/api')
  })
})
