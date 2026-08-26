// frontend/tests/useRbac.test.js
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('axios', () => ({ default: { get: vi.fn() } }))
vi.mock('../src/auth.js', () => ({
  getStoredJwt: vi.fn().mockReturnValue('test.jwt.token'),
}))

const MOCK_SCREENS = [
  { screen_id: 'SCREEN_001', screen_name: 'Screen 1', min_level: 1, allowed_depts: ['IT'] },
  { screen_id: 'SCREEN_002', screen_name: 'Screen 2', min_level: 2, allowed_depts: ['HR'] },
]

describe('useRbac', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.clearAllMocks()
    vi.unstubAllEnvs()
  })

  it('fetchRbac() with AUTH_MODE=0 returns immediately — axios.get NOT called', async () => {
    vi.stubEnv('VITE_AUTH_MODE', '0')
    const axios = (await import('axios')).default
    const { fetchRbac } = await import('../src/composables/useRbac.js')
    await fetchRbac()
    expect(axios.get).not.toHaveBeenCalled()
  })

  it('fetchRbac() with AUTH_MODE=1 returns immediately — axios.get NOT called', async () => {
    vi.stubEnv('VITE_AUTH_MODE', '1')
    const axios = (await import('axios')).default
    const { fetchRbac } = await import('../src/composables/useRbac.js')
    await fetchRbac()
    expect(axios.get).not.toHaveBeenCalled()
  })

  it('fetchRbac() with AUTH_MODE=2 calls axios.get with Bearer header', async () => {
    vi.stubEnv('VITE_AUTH_MODE', '2')
    vi.stubEnv('VITE_AUTH_SERVICE_URL', 'http://auth.local')
    vi.stubEnv('VITE_APP_NAME', '')   // real code sends this as a query param — pin it, don't let ambient .env leak in
    const axios = (await import('axios')).default
    axios.get.mockResolvedValue({ data: { accessible_screens: MOCK_SCREENS } })
    const { fetchRbac } = await import('../src/composables/useRbac.js')
    await fetchRbac()
    expect(axios.get).toHaveBeenCalledWith(
      'http://auth.local/rbac/me',
      { headers: { Authorization: 'Bearer test.jwt.token' }, params: {} }
    )
  })

  it('fetchRbac() sets rbacLoaded=true on success', async () => {
    vi.stubEnv('VITE_AUTH_MODE', '2')
    vi.stubEnv('VITE_AUTH_SERVICE_URL', 'http://auth.local')
    const axios = (await import('axios')).default
    axios.get.mockResolvedValue({ data: { accessible_screens: MOCK_SCREENS } })
    const { fetchRbac, useRbac } = await import('../src/composables/useRbac.js')
    await fetchRbac()
    const { rbacLoaded } = useRbac()
    expect(rbacLoaded.value).toBe(true)
  })

  it('fetchRbac() on 403: sets rbacError=true and re-throws', async () => {
    vi.stubEnv('VITE_AUTH_MODE', '2')
    vi.stubEnv('VITE_AUTH_SERVICE_URL', 'http://auth.local')
    const axios = (await import('axios')).default
    const err403 = { response: { status: 403 } }
    axios.get.mockRejectedValue(err403)
    const { fetchRbac, useRbac } = await import('../src/composables/useRbac.js')
    await expect(fetchRbac()).rejects.toBe(err403)
    const { rbacError } = useRbac()
    expect(rbacError.value).toBe(true)
  })

  it('fetchRbac() on non-403 error: rbacError stays false and re-throws', async () => {
    vi.stubEnv('VITE_AUTH_MODE', '2')
    vi.stubEnv('VITE_AUTH_SERVICE_URL', 'http://auth.local')
    const axios = (await import('axios')).default
    const networkErr = new Error('Network Error')
    axios.get.mockRejectedValue(networkErr)
    const { fetchRbac, useRbac } = await import('../src/composables/useRbac.js')
    await expect(fetchRbac()).rejects.toThrow('Network Error')
    const { rbacError } = useRbac()
    expect(rbacError.value).toBe(false)
  })

  it('can() returns true when screen_id is in accessible_screens', async () => {
    vi.stubEnv('VITE_AUTH_MODE', '2')
    vi.stubEnv('VITE_AUTH_SERVICE_URL', 'http://auth.local')
    const axios = (await import('axios')).default
    axios.get.mockResolvedValue({ data: { accessible_screens: MOCK_SCREENS } })
    const { fetchRbac, useRbac } = await import('../src/composables/useRbac.js')
    await fetchRbac()
    const { can } = useRbac()
    expect(can('SCREEN_001')).toBe(true)
  })

  it('can() returns false when screen_id not in accessible_screens', async () => {
    vi.stubEnv('VITE_AUTH_MODE', '2')
    vi.stubEnv('VITE_AUTH_SERVICE_URL', 'http://auth.local')
    const axios = (await import('axios')).default
    axios.get.mockResolvedValue({ data: { accessible_screens: MOCK_SCREENS } })
    const { fetchRbac, useRbac } = await import('../src/composables/useRbac.js')
    await fetchRbac()
    const { can } = useRbac()
    expect(can('SCREEN_999')).toBe(false)
  })

  it('can() returns false before fetchRbac() is called (empty _screens)', async () => {
    vi.stubEnv('VITE_AUTH_MODE', '2')
    const { useRbac } = await import('../src/composables/useRbac.js')
    const { can } = useRbac()
    expect(can('SCREEN_001')).toBe(false)
  })

  it('multiple useRbac() calls return same rbacLoaded ref (singleton)', async () => {
    vi.stubEnv('VITE_AUTH_MODE', '2')
    vi.stubEnv('VITE_AUTH_SERVICE_URL', 'http://auth.local')
    const axios = (await import('axios')).default
    axios.get.mockResolvedValue({ data: { accessible_screens: MOCK_SCREENS } })
    const { fetchRbac, useRbac } = await import('../src/composables/useRbac.js')
    await fetchRbac()
    const a = useRbac()
    const b = useRbac()
    expect(a.rbacLoaded).toBe(b.rbacLoaded)
    expect(a.rbacError).toBe(b.rbacError)
  })

  it('VITE_AUTH_SERVICE_URL with trailing slash is stripped (no double-slash)', async () => {
    vi.stubEnv('VITE_AUTH_MODE', '2')
    vi.stubEnv('VITE_AUTH_SERVICE_URL', 'http://auth.local/')
    const axios = (await import('axios')).default
    axios.get.mockResolvedValue({ data: { accessible_screens: [] } })
    const { fetchRbac } = await import('../src/composables/useRbac.js')
    await fetchRbac()
    expect(axios.get).toHaveBeenCalledWith(
      'http://auth.local/rbac/me',
      expect.any(Object)
    )
  })

  it('fetchRbac() on 500 error: rbacError stays false and re-throws', async () => {
    vi.stubEnv('VITE_AUTH_MODE', '2')
    vi.stubEnv('VITE_AUTH_SERVICE_URL', 'http://auth.local')
    const axios = (await import('axios')).default
    const err500 = { response: { status: 500 }, message: 'Internal Server Error' }
    axios.get.mockRejectedValue(err500)
    const { fetchRbac, useRbac } = await import('../src/composables/useRbac.js')
    await expect(fetchRbac()).rejects.toBe(err500)
    const { rbacError } = useRbac()
    expect(rbacError.value).toBe(false)
  })
})
