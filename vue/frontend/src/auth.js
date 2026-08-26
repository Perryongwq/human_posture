// frontend/src/auth.js
// ═══════════════════════════════════════════════════════════════════
// Auth seam for VueAuthService JWE integration
// Version: 2.0 | Token upgraded from JWT to JWE (dir/A256GCM)
// JWE payload is encrypted — frontend stores expiry and claims separately
// ═══════════════════════════════════════════════════════════════════
import axios from 'axios'

const _appPrefix = (import.meta.env.VITE_APP_NAME || 'app_template')
  .toLowerCase()
  .replace(/[^a-z0-9]+/g, '_')
  .replace(/^_|_$/g, '')               // trim leading/trailing underscores
export const JWT_KEY = `${_appPrefix}_jwt`           // stored token (JWE string)
export const JWT_EXP_KEY = `${_appPrefix}_jwt_exp`   // expiry timestamp (ms)
export const JWT_CLAIMS_KEY = `${_appPrefix}_jwt_claims` // { username, payroll, deptcode }
export const LOGIN_METHOD_KEY = `${_appPrefix}_login_method` // 'local' | 'sso'
const MAX_REDIRECT_ATTEMPTS = 3                     // FE-03: infinite loop guard
let isRedirecting = false                           // C5: parallel-401 guard

/**
 * FE-04: Client-side token expiry check.
 * UX only — the server still verifies independently.
 *
 * With JWE the payload is encrypted so exp cannot be decoded.
 * Falls back to a stored expiry timestamp written at login.
 */
export function isExpired(token) {
  // Try decoding as plain JWT first (backward compat / dev mode)
  try {
    const b64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
    const padded = b64.padEnd(Math.ceil(b64.length / 4) * 4, '=')
    const payload = JSON.parse(atob(padded))
    if (payload.exp) return payload.exp * 1000 < Date.now()
  } catch {
    // Not a plain JWT — fall through to stored expiry
  }
  // JWE path: read stored expiry timestamp set at login
  const storedExp = localStorage.getItem(JWT_EXP_KEY)
  if (storedExp) return parseInt(storedExp) < Date.now()
  return true  // no expiry info → treat as expired
}

/**
 * Read stored token from localStorage using namespaced key.
 */
export function getStoredJwt() {
  return localStorage.getItem(JWT_KEY)
}

/**
 * Clear stored token, expiry, and claims. Reset redirect guard.
 * Called by apiClient 401 interceptor before re-auth.
 */
export function logout() {
  localStorage.removeItem(JWT_KEY)
  localStorage.removeItem(JWT_EXP_KEY)
  localStorage.removeItem(JWT_CLAIMS_KEY)
  localStorage.removeItem(LOGIN_METHOD_KEY)
  isRedirecting = false
}

/**
 * FE-01: Full SSO login flow. Five-case ordered handler.
 *
 * SEQUENCE IS STRICT — wrong order causes security or loop bugs:
 *   1. VITE_AUTH_MODE === '0' → return immediately (TOG-03)
 *   2. ?Authorization=<JWE> in URL → strip URL sync (FE-02) → POST exchange → store token → return
 *   3. storedToken && !isExpired → return immediately (FE-04)
 *   4. Check sessionStorage redirect counter (FE-03 cold-start guard)
 *   5. Check isRedirecting flag (FE-03 parallel-401 guard) → redirect to SSO
 */
export async function initAuth() {
  // TOG-03: AUTH_MODE=0 → resolve immediately (auth off)
  if (import.meta.env.VITE_AUTH_MODE === '0') {
    return
  }

  // FE-02: JWE in URL — strip BEFORE the async exchange
  // CRITICAL: replaceState is synchronous and unconditional (C3 pitfall)
  // If POST fails, URL is already clean — JWE never in browser history
  const params = new URLSearchParams(window.location.search)
  const jweToken = params.get('Authorization')

  if (jweToken) {
    // Strip synchronously — failure-safe
    // auth_mode is a routing hint appended by VueLocalAuth on local logins.
    // It is NOT a security boundary — the JWE is. Its only purpose is to tell
    // the logout flow whether to clear an Azure AD session. Absence means the
    // real SSO proxy handled the login (it never appends auth_mode), so we
    // default to 'sso'. A forged value only affects logout routing, not access.
    const loginMethod = params.get('auth_mode') === 'local' ? 'local' : 'sso'
    params.delete('Authorization')
    params.delete('auth_mode')
    const cleanUrl = window.location.pathname +
      (params.toString() ? '?' + params.toString() : '')
    window.history.replaceState({}, '', cleanUrl)

    // Exchange SSO JWE for app JWE via VueAuthService
    const authUrl = (import.meta.env.VITE_AUTH_SERVICE_URL || '').replace(/\/$/, '')
    const appName = import.meta.env.VITE_APP_NAME || ''
    const res = await axios.post(`${authUrl}/auth/token`, { jwe_token: jweToken, app_name: appName })

    // Store app JWE token
    localStorage.setItem(JWT_KEY, res.data.access_token)
    // Store expiry timestamp (ms) for client-side check — UX only, backend enforces
    localStorage.setItem(JWT_EXP_KEY, String(Date.now() + (res.data.expires_in * 1000)))
    // Store user claims (returned in response — JWE payload is encrypted so can't decode)
    localStorage.setItem(JWT_CLAIMS_KEY, JSON.stringify({
      username: res.data.username,
      payroll: res.data.payroll,
      deptcode: res.data.deptcode,
    }))
    // Track which login path was used so logout can do the right thing
    localStorage.setItem(LOGIN_METHOD_KEY, loginMethod)
    return
  }

  // FE-04: valid stored token → skip SSO entirely
  const storedJwt = getStoredJwt()
  if (storedJwt && !isExpired(storedJwt)) {
    return
  }

  // FE-03: redirect loop guard — sessionStorage counter for cold-start loops
  // VueAuthService down → no token → redirect → repeat → infinite loop
  const redirectCount = parseInt(sessionStorage.getItem('_auth_redirects') || '0')
  if (redirectCount >= MAX_REDIRECT_ATTEMPTS) {
    sessionStorage.removeItem('_auth_redirects')
    throw new Error('Auth redirect loop detected — check VITE_SSO_URL and VueAuthService availability')
  }

  // C5: isRedirecting flag — prevents parallel-401 interceptor storm
  // Dashboard fires 4 API calls → all 401 → all call initAuth → 4 redirects
  if (isRedirecting) return
  isRedirecting = true

  // FE-01: redirect to SSO Proxy — pick a random token from VITE_AUTH_TOKENS
  // Equivalent to Python: secrets.choice(config["AUTHTOKENS"])
  sessionStorage.setItem('_auth_redirects', String(redirectCount + 1))
  const returnUrl = encodeURIComponent(window.location.href)

  // AUTH_MODE=3: redirect to VueLocalAuth login form (local SSO mimic)
  if (import.meta.env.VITE_AUTH_MODE === '3') {
    window.location.href =
      `${import.meta.env.VITE_LOCAL_AUTH_URL}/login?next=${returnUrl}&app=${encodeURIComponent(import.meta.env.VITE_APP_NAME || '')}`
  } else {
    const authTokens = (import.meta.env.VITE_AUTH_TOKENS || '').split(',').map(t => t.trim()).filter(Boolean)
    const token = authTokens[Math.floor(Math.random() * authTokens.length)]
    window.location.href =
      `${import.meta.env.VITE_SSO_URL}?next=${returnUrl}&Authorization=${token}`
  }
}
