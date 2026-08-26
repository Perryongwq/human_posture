// frontend/tests/router.test.js
import { describe, it, expect, vi, beforeEach } from 'vitest'

// Swap createWebHistory → createMemoryHistory for jsdom compatibility
vi.mock('vue-router', async (importOriginal) => {
  const mod = await importOriginal()
  return { ...mod, createWebHistory: () => mod.createMemoryHistory() }
})

// Stub view components
vi.mock('../src/views/HomeView.vue', () => ({ default: { template: '<div>Home</div>' } }))
vi.mock('../src/views/UnauthorizedView.vue', () => ({ default: { template: '<div>Unauthorized</div>' } }))

// Stub AppLayout component (Wave 1 implementation — not yet created)
vi.mock('../src/components/AppLayout.vue', () => ({ default: { template: '<div><router-view /></div>' } }))

// Mock useRbac with controllable can() and rbacLoaded
const mockCan = vi.fn().mockReturnValue(true)
const mockRbacLoaded = { value: true }
vi.mock('../src/composables/useRbac.js', () => ({
  useRbac: () => ({ can: mockCan, rbacLoaded: mockRbacLoaded }),
}))

// Mock auth.js functions for auth guard tests
const mockGetStoredJwt = vi.fn().mockReturnValue('valid.jwt.token')
const mockIsExpired = vi.fn().mockReturnValue(false)
const mockInitAuth = vi.fn().mockResolvedValue(undefined)
vi.mock('../src/auth.js', () => ({
  getStoredJwt: () => mockGetStoredJwt(),
  isExpired: (token) => mockIsExpired(token),
  initAuth: () => mockInitAuth(),
}))

describe('Router Guard', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.clearAllMocks()
    vi.unstubAllEnvs()
    mockCan.mockReturnValue(true)  // default: allow access
    mockRbacLoaded.value = true    // default: RBAC loaded
    mockGetStoredJwt.mockReturnValue('valid.jwt.token')
    mockIsExpired.mockReturnValue(false)
    mockInitAuth.mockClear()
  })

  // ponytail: the only route that ever carried a screen_id (the old
  // "/protected" demo page) was deleted 2026-08-20 — no route in the app
  // currently sets meta.screen_id, so the can()=false/rbacLoaded=false
  // redirect branches below are untested (not untrue — just unreachable
  // in the shipped app right now). Re-add a screen_id route + these cases
  // if a real RBAC-gated page comes back.
  it('mode=2: navigating to / (no screen_id) succeeds — guard passes through', async () => {
    vi.stubEnv('VITE_AUTH_MODE', '2')
    const { router } = await import('../src/router/index.js')
    await router.push('/')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/')
  })
})

describe('Auth Guard (LAYOUT-01)', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.clearAllMocks()
    vi.unstubAllEnvs()
    mockCan.mockReturnValue(true)
    mockRbacLoaded.value = true
    mockGetStoredJwt.mockReturnValue('valid.jwt.token')
    mockIsExpired.mockReturnValue(false)
    mockInitAuth.mockClear()
  })

  it('unauthenticated: no JWT → calls initAuth()', async () => {
    vi.stubEnv('VITE_AUTH_MODE', '1')
    mockGetStoredJwt.mockReturnValue(null)
    const { router } = await import('../src/router/index.js')
    await router.push('/')
    expect(mockInitAuth).toHaveBeenCalled()
  })

  it('unauthenticated: expired JWT → calls initAuth()', async () => {
    vi.stubEnv('VITE_AUTH_MODE', '1')
    mockGetStoredJwt.mockReturnValue('expired.jwt.token')
    mockIsExpired.mockReturnValue(true)
    const { router } = await import('../src/router/index.js')
    await router.push('/')
    expect(mockInitAuth).toHaveBeenCalled()
  })

  it('authenticated: valid JWT → navigation proceeds (initAuth not called)', async () => {
    vi.stubEnv('VITE_AUTH_MODE', '1')
    mockGetStoredJwt.mockReturnValue('valid.jwt.token')
    mockIsExpired.mockReturnValue(false)
    const { router } = await import('../src/router/index.js')
    await router.push('/')
    await router.isReady()
    expect(mockInitAuth).not.toHaveBeenCalled()
    expect(router.currentRoute.value.path).toBe('/')
  })

  it('/unauthorized route does not require auth', async () => {
    vi.stubEnv('VITE_AUTH_MODE', '1')
    mockGetStoredJwt.mockReturnValue(null)
    const { router } = await import('../src/router/index.js')
    await router.push('/unauthorized')
    await router.isReady()
    expect(mockInitAuth).not.toHaveBeenCalled()
    expect(router.currentRoute.value.path).toBe('/unauthorized')
  })
})

describe('Nested Route Structure (LAYOUT-02)', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.clearAllMocks()
    vi.unstubAllEnvs()
    mockCan.mockReturnValue(true)
    mockRbacLoaded.value = true
    mockGetStoredJwt.mockReturnValue('valid.jwt.token')
    mockIsExpired.mockReturnValue(false)
    mockInitAuth.mockClear()
  })

  it('/ route is child of AppLayout parent', async () => {
    vi.stubEnv('VITE_AUTH_MODE', '1')
    mockGetStoredJwt.mockReturnValue('valid.jwt.token')
    mockIsExpired.mockReturnValue(false)
    const { router } = await import('../src/router/index.js')
    await router.push('/')
    await router.isReady()
    const matched = router.currentRoute.value.matched
    expect(matched.length).toBeGreaterThanOrEqual(2)  // AppLayout parent + HomeView child
    expect(matched[0].path).toBe('/')  // AppLayout at root
  })

  it('routes have meta.title for header display', async () => {
    vi.stubEnv('VITE_AUTH_MODE', '1')
    mockGetStoredJwt.mockReturnValue('valid.jwt.token')
    mockIsExpired.mockReturnValue(false)
    const { router } = await import('../src/router/index.js')
    await router.push('/')
    await router.isReady()
    expect(router.currentRoute.value.meta.title).toBe('Home')
  })
})
