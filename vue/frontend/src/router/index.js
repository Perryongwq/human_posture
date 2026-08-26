// frontend/src/router/index.js
// ═══════════════════════════════════════════════════════════════════
// Vue Router 4 — nested routes + auth guard + RBAC guard.
//
// CRITICAL (RBF-03): Do NOT add a static import of useRbac at the
// top of this file. The dynamic import() inside beforeEach ensures
// the useRbac module is never loaded when VITE_AUTH_MODE !== '2'.
//
// CRITICAL (LAYOUT-01): Auth guard calls initAuth() on unauthenticated
// access. Must `return false` after initAuth() to cancel navigation
// before SSO redirect fires.
//
// NOTE: createWebHistory() requires SPA fallback on the web server
// in production (e.g., nginx: try_files $uri $uri/ /index.html).
// ═══════════════════════════════════════════════════════════════════
import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import { getStoredJwt, isExpired, initAuth } from '../auth.js'

const routes = [
  {
    // AppLayout parent — all authenticated routes are children
    path: '/',
    component: () => import('../components/AppLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',           // matches /
        component: HomeView,
        meta: { title: 'Home' },
      },
      {
        path: 'posture',
        component: () => import('../views/PostureV3View.vue'),
        meta: { title: 'Pick & Place' },
      },
      // old grip-based v1 removed — v3 (station tracking) is Pick & Place now
      { path: 'posture-v3', redirect: '/posture' },
    ],
  },
  {
    // Unauthorized page — no shell, no auth required
    path: '/unauthorized',
    component: () => import('../views/UnauthorizedView.vue'),
    // No requiresAuth — rendered without shell
  },
  {
    // Reset cache page — no shell, no auth required
    path: '/reset',
    component: () => import('../views/ResetView.vue'),
    meta: { title: 'Reset Cache' },
    // No requiresAuth — public utility page
  },
]

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})


// Auto page title: "Page title — App Name" (or just "App Name" if no meta.title)
// Reads from route meta.title + VITE_APP_NAME — no per-page code needed.
const appName = import.meta.env.VITE_APP_NAME || 'App'
router.afterEach((to) => {
  document.title = to.meta.title || appName
})

// Single beforeEach: auth guard FIRST, then RBAC guard
router.beforeEach(async (to) => {
  // 0. Strip ?Authorization from URL — SSO redirects back with token as query param.
  //    Vue Router captures the URL before initAuth() strips it, so we must clean it
  //    here before any further processing. Redirect to same path/query without it.
  if ('Authorization' in to.query) {
    const { Authorization: _removed, ...cleanQuery } = to.query
    return { path: to.path, query: cleanQuery, replace: true }
  }

  // 1. Auth guard: AppLayout children require a valid JWT
  //    Check ALL matched routes (parent + children) for requiresAuth
  const requiresAuth = to.matched.some(r => r.meta.requiresAuth)
  if (requiresAuth && import.meta.env.VITE_AUTH_MODE !== '0') {
    const jwt = getStoredJwt()
    if (!jwt || isExpired(jwt)) {
      await initAuth()   // triggers SSO redirect — page navigation stops
      return false       // cancel Vue Router navigation (SSO takes over)
    }
  }

  // 2. RBAC guard (unchanged logic — AUTH_MODE=2/3 only, screen_id only)
  if (!['2', '3'].includes(import.meta.env.VITE_AUTH_MODE)) return true
  if (!to.meta.screen_id) return true
  const { useRbac } = await import('../composables/useRbac.js')
  const { can, rbacLoaded } = useRbac()
  // Guard: if RBAC data not yet loaded, deny rather than silently pass
  if (!rbacLoaded.value) {
    return { path: '/unauthorized', query: { screen: to.meta.screen_id } }
  }
  return can(to.meta.screen_id)
    ? true
    : { path: '/unauthorized', query: { screen: to.meta.screen_id } }
})