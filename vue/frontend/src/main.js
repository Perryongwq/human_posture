import './style.css'
// frontend/src/main.js
// ═══════════════════════════════════════════════════════════════════
// Async bootstrap — auth + RBAC resolve BEFORE Vue mounts.
// FE-07: await initAuth() ensures no flash of unauthenticated UI.
// RBF-02: RBAC pre-mount check blocks app if user lacks access.
// RBF-03: useRbac dynamically imported ONLY when AUTH_MODE=2 or 3.
// ═══════════════════════════════════════════════════════════════════
import { createApp } from 'vue'
import App from './App.vue'
import { router } from './router/index.js'
import { initAuth, JWT_CLAIMS_KEY } from './auth.js'
import { syncCurrentUser } from './composables/useAuth.js'

async function bootstrap() {
  await initAuth()       // FE-07: auth fully resolved before any Vue renders
  syncCurrentUser()      // populate reactive currentUser ref from localStorage

  // RBF-02: RBAC pre-mount check (dynamic import satisfies RBF-03)
  if (['2', '3'].includes(import.meta.env.VITE_AUTH_MODE)) {
    const { fetchRbac, useRbac } = await import('./composables/useRbac.js')
    try {
      await fetchRbac()
    } catch (err) {
      const { rbacError } = useRbac()
      if (rbacError.value) {
        // 403 — user not registered for this app. Render branded access-denied page.
        const appName = import.meta.env.VITE_APP_NAME || 'This Application'
        // Read claims from localStorage (written at login — JWE payload is encrypted)
        let user = {}
        try {
          user = JSON.parse(localStorage.getItem(JWT_CLAIMS_KEY) || '{}')
        } catch (_) {}
        document.getElementById('app').innerHTML = `
          <div style="font-family:sans-serif;padding:2rem;max-width:600px;margin:0 auto">
            <h2 style="color:#c00">[${appName}] Access Denied</h2>
            <p>Your account is not registered for <strong>${appName}</strong>. Contact the system administrator.</p>
            <p style="color:#666;font-size:.9em">User: ${user.username} | Payroll: ${user.payroll} | Dept: ${user.deptcode}</p>
          </div>`
        return  // exit bootstrap() — Vue never mounts
      }
      throw err  // non-403 error — propagate to bootstrap().catch() (fail closed)
    }
  }

  createApp(App).use(router).mount('#app')
}

bootstrap().catch(err => {
  // Auth or RBAC fatal error — show developer-friendly error; do NOT mount Vue
  document.getElementById('app').innerHTML =
    `<div style="font-family:monospace;color:red;padding:2rem">
      <strong>Auth Error:</strong> ${err.message}<br><br>
      Check VITE_SSO_URL and VueAuthService availability, then hard-refresh.
    </div>`
})
