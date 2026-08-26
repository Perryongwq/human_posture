// frontend/src/composables/useRbac.js
// ═══════════════════════════════════════════════════════════════════
// Vue 3 RBAC composable — fetches RBAC data from VueAuthService.
// Singleton: module-level refs shared across all component instances.
// Pattern: identical to useAuth.js (module-level ref, readonly exports).
//
// IMPORTANT: This module is dynamically imported in main.js and
// router/index.js ONLY when VITE_AUTH_MODE === '2' or '3' (RBF-03).
// ═══════════════════════════════════════════════════════════════════
import { ref, readonly } from 'vue'
import axios from 'axios'
import { getStoredJwt } from '../auth.js'

// Module-level singletons — shared across all useRbac() callers.
// Reset only via vi.resetModules() in tests.
const rbacLoaded = ref(false)
const rbacError = ref(false)
const _screens = ref([])
const _accessCodes = ref([])

/**
 * Fetch RBAC data from VueAuthService /rbac/me endpoint.
 * Sets rbacLoaded=true on success, rbacError=true on 403.
 * Re-throws ALL errors (403 and non-403) so callers can handle.
 *
 * No-op when VITE_AUTH_MODE is not '2' or '3' — returns immediately.
 */
export async function fetchRbac() {
  if (!['2', '3'].includes(import.meta.env.VITE_AUTH_MODE)) return
  try {
    const jwt = getStoredJwt()
    const authUrl = (import.meta.env.VITE_AUTH_SERVICE_URL || '').replace(/\/$/, '')
    const appName = import.meta.env.VITE_APP_NAME || ''
    const res = await axios.get(`${authUrl}/rbac/me`, {
      headers: { Authorization: `Bearer ${jwt}` },
      params: appName ? { app_name: appName } : {},
    })
    _screens.value = res.data.accessible_screens
    _accessCodes.value = res.data.access_codes ?? []
    rbacLoaded.value = true
  } catch (err) {
    if (err.response?.status === 403) {
      rbacError.value = true
    }
    // Non-403 errors: rbacError stays false, rbacLoaded stays false
    throw err  // re-throw so main.js bootstrap().catch() sees it
  }
}

/**
 * Composable exposing RBAC state and permission check.
 * can(screen_id) checks if screen_id is in the user's accessible_screens.
 * accessCodes exposes the list of AccessCode objects for the current user.
 */
export function useRbac() {
  function can(screen_id) {
    return _screens.value.some(s => s.screen_id === screen_id)
  }
  return {
    rbacLoaded: readonly(rbacLoaded),
    rbacError: readonly(rbacError),
    accessCodes: readonly(_accessCodes),
    can,
    fetchRbac,
  }
}
