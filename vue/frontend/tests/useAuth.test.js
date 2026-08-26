// frontend/tests/useAuth.test.js
import { describe, it, expect, vi, beforeEach } from 'vitest'

// JWT_CLAIMS_KEY: real auth.js (v2.0, JWE) stores claims in localStorage
// separately from the token — syncCurrentUser() reads THIS key, not a
// decoded JWT (the JWE payload is encrypted, unreadable client-side).
vi.mock('../src/auth.js', () => ({
  JWT_CLAIMS_KEY: 'test_jwt_claims',
  LOGIN_METHOD_KEY: 'test_login_method',
  getStoredJwt: vi.fn(),
  logout: vi.fn(),
  initAuth: vi.fn(),
}))

const CLAIMS = { username: 'testuser', payroll: 'P12345', deptcode: 'SP5121' }

describe('useAuth()', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.clearAllMocks()
    vi.unstubAllEnvs()
    localStorage.clear()
  })

  it('currentUser is null when no JWT stored (syncCurrentUser not called)', async () => {
    const { useAuth } = await import('../src/composables/useAuth.js')
    const { currentUser } = useAuth()
    expect(currentUser.value).toBeNull()
  })

  it('currentUser is populated with JWT claims after syncCurrentUser()', async () => {
    vi.stubEnv('VITE_AUTH_MODE', '1')   // non-0 — otherwise syncCurrentUser() takes the mock-dev-claims branch
    localStorage.setItem('test_jwt_claims', JSON.stringify(CLAIMS))
    const { useAuth, syncCurrentUser } = await import('../src/composables/useAuth.js')
    syncCurrentUser()  // simulates main.js call after await initAuth()
    const { currentUser } = useAuth()
    expect(currentUser.value.username).toBe('testuser')
    expect(currentUser.value.payroll).toBe('P12345')
    expect(currentUser.value.deptcode).toBe('SP5121')
  })

  it('currentUser is reactive — shared ref across multiple useAuth() calls', async () => {
    vi.stubEnv('VITE_AUTH_MODE', '1')
    localStorage.setItem('test_jwt_claims', JSON.stringify(CLAIMS))
    const { useAuth, syncCurrentUser } = await import('../src/composables/useAuth.js')
    syncCurrentUser()
    const a = useAuth()
    const b = useAuth()
    expect(a.currentUser.value).toEqual(b.currentUser.value)
    expect(a.currentUser.value.username).toBe('testuser')   // not just equal-to-each-other, actually populated
  })

  it('logout() calls authLogout, clears currentUser, and redirects to Microsoft logout', async () => {
    vi.stubEnv('VITE_AUTH_MODE', '1')   // non-0 — otherwise syncCurrentUser() takes the mock-dev-claims branch
    vi.stubEnv('VITE_AZURE_TENANT_ID', 'test-tenant-id')
    vi.stubEnv('VITE_POST_LOGOUT_REDIRECT_URI', 'https://myapp.local')
    localStorage.setItem('test_jwt_claims', JSON.stringify(CLAIMS))
    const { logout: authLogout } = await import('../src/auth.js')
    const { useAuth, syncCurrentUser } = await import('../src/composables/useAuth.js')
    syncCurrentUser()
    const { currentUser, logout } = useAuth()
    expect(currentUser.value.username).toBe('testuser')

    // Mock window.location so href assignment is captured
    Object.defineProperty(window, 'location', {
      value: { href: 'http://localhost/' },
      writable: true,
      configurable: true,
    })

    logout()

    expect(authLogout).toHaveBeenCalledOnce()
    expect(currentUser.value).toBeNull()
    expect(window.location.href).toContain('login.microsoftonline.com/test-tenant-id')
    expect(window.location.href).toContain('post_logout_redirect_uri')
  })

  it('syncCurrentUser() sets mock claims when VITE_AUTH_MODE=0', async () => {
    vi.stubEnv('VITE_AUTH_MODE', '0')
    const { useAuth, syncCurrentUser } = await import('../src/composables/useAuth.js')
    syncCurrentUser()
    const { currentUser } = useAuth()
    expect(currentUser.value.username).toBe('dev')
    expect(currentUser.value.payroll).toBe('DEV001')
    expect(currentUser.value.deptcode).toBe('IT')
  })
})
