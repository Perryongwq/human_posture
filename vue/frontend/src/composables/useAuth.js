// frontend/src/composables/useAuth.js
// ═══════════════════════════════════════════════════════════════════
// Vue 3 auth composable — exposes reactive currentUser and logout().
// Singleton: module-level ref shared across all component instances.
// Version 2.0: reads stored claims from localStorage (JWE payload is
// encrypted so cannot be decoded in the browser).
// ═══════════════════════════════════════════════════════════════════
import { ref, readonly } from 'vue'
import { JWT_CLAIMS_KEY, LOGIN_METHOD_KEY, getStoredJwt, logout as authLogout, initAuth } from '../auth.js'

// Module-level singleton ref — starts null, populated by syncCurrentUser().
const _currentUser = ref(null)

/**
 * Populate _currentUser after initAuth() has run.
 * Called by main.js immediately after await initAuth() — before mount.
 *
 * With JWE, the token payload is encrypted so claims are read from
 * localStorage (stored there by initAuth() when the token was issued).
 */
export function syncCurrentUser() {
  if (import.meta.env.VITE_AUTH_MODE === '0') {
    _currentUser.value = { username: 'dev', payroll: 'DEV001', deptcode: 'IT' }
    return
  }
  try {
    const stored = localStorage.getItem(JWT_CLAIMS_KEY)
    _currentUser.value = stored ? JSON.parse(stored) : null
  } catch {
    _currentUser.value = null
  }
}

export function useAuth() {
  function logout() {
    const mode = import.meta.env.VITE_AUTH_MODE
    // Read login method BEFORE authLogout clears localStorage
    const loginMethod = localStorage.getItem(LOGIN_METHOD_KEY)

    authLogout()                 // clear localStorage token + exp + claims (from auth.js)
    _currentUser.value = null    // reactively clear currentUser

    // MODE=3: logout destination depends on how the user originally signed in.
    // 'sso'   → they used the SSO button, so Azure AD session must be cleared too.
    // 'local' → local credentials only, just redirect back to the local login page.
    if (mode === '3') {
      if (loginMethod === 'sso') {
        const tenantId = import.meta.env.VITE_AZURE_TENANT_ID
        const postLogoutUri = import.meta.env.VITE_POST_LOGOUT_REDIRECT_URI
        if (tenantId && postLogoutUri) {
          window.location.href =
            `https://login.microsoftonline.com/${tenantId}/oauth2/v2.0/logout` +
            `?post_logout_redirect_uri=${encodeURIComponent(postLogoutUri)}`
          return
        }
      }
      const returnUrl = encodeURIComponent(window.location.origin + (import.meta.env.BASE_URL || '/'))
      window.location.href =
        `${import.meta.env.VITE_LOCAL_AUTH_URL}/login?next=${returnUrl}&app=${encodeURIComponent(import.meta.env.VITE_APP_NAME || '')}`
      return
    }

    // MODE=1/2: Redirect to Microsoft Azure AD logout — clears the Azure AD session.
    const tenantId = import.meta.env.VITE_AZURE_TENANT_ID
    const postLogoutUri = import.meta.env.VITE_POST_LOGOUT_REDIRECT_URI
    if (tenantId && postLogoutUri) {
      window.location.href =
        `https://login.microsoftonline.com/${tenantId}/oauth2/v2.0/logout` +
        `?post_logout_redirect_uri=${encodeURIComponent(postLogoutUri)}`
    } else {
      initAuth()?.catch(err => console.error('Re-auth failed:', err))
    }
  }

  return {
    currentUser: readonly(_currentUser),
    logout,
  }
}
