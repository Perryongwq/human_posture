// frontend/src/api/client.js
// ═══════════════════════════════════════════════════════════════════
// Configured axios instance with auth interceptors.
// Request: injects JWT from localStorage on every outgoing request.
// Response: catches 401, clears JWT, triggers re-login via initAuth().
// ═══════════════════════════════════════════════════════════════════
import axios from 'axios'
import { getStoredJwt, logout, initAuth } from '../auth.js'

// FE-06: module-level guard prevents parallel-401 storm (C5 pitfall)
let isRedirecting = false

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
})

// FE-05: request interceptor — attach JWT to every outgoing request
apiClient.interceptors.request.use((config) => {
  const token = getStoredJwt()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// FE-06: response interceptor — 401 → clear JWT → re-login (exactly once)
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && !isRedirecting) {
      isRedirecting = true   // C5: guard — set before calling initAuth()
      logout()               // clear stored JWT before re-auth
      initAuth()             // triggers SSO redirect; page will unload
    }
    return Promise.reject(error)
  }
)
