<!-- frontend/src/views/ResetView.vue -->
<template>
  <div class="min-h-screen flex items-center justify-center bg-background">
    <div class="w-96 rounded-lg border border-border bg-card text-card-foreground shadow-sm p-6 space-y-4">
      <h2 class="text-lg font-semibold leading-tight">Cache Reset</h2>

      <!-- Loading -->
      <div v-if="loading" class="flex justify-center py-4">
        <div class="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>

      <!-- Error -->
      <div v-else-if="error" class="rounded-md bg-destructive/10 border border-destructive/30 px-4 py-3 text-sm text-destructive">
        {{ error }}
      </div>

      <!-- Success -->
      <div v-else-if="result" class="space-y-3">
        <div class="rounded-md bg-primary/10 border border-primary/20 px-4 py-3 text-sm text-foreground">
          Cache cleared for <strong>{{ result.app_name }}</strong>
        </div>
        <div v-if="result.cleared.length > 0">
          <p class="text-sm font-medium text-foreground mb-1">Keys cleared:</p>
          <ul class="space-y-1">
            <li
              v-for="key in result.cleared"
              :key="key"
              class="text-sm text-muted-foreground font-mono bg-muted rounded px-2 py-1"
            >{{ key }}</li>
          </ul>
        </div>
        <p v-else class="text-sm text-muted-foreground">No keys were present in cache.</p>
      </div>

      <div class="flex justify-end pt-2">
        <RouterLink to="/" class="text-sm font-medium text-primary hover:underline">← Go Home</RouterLink>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const loading = ref(true)
const error = ref(null)
const result = ref(null)

const authServiceUrl = import.meta.env.VITE_AUTH_SERVICE_URL
const localAuthUrl   = import.meta.env.VITE_LOCAL_AUTH_URL
const appName        = import.meta.env.VITE_APP_NAME
const authMode       = import.meta.env.VITE_AUTH_MODE

onMounted(async () => {
  if (!authServiceUrl || !appName) {
    error.value = 'Missing VITE_AUTH_SERVICE_URL or VITE_APP_NAME environment variable'
    loading.value = false
    return
  }

  try {
    // Always clear VueAuthService RBAC cache
    const res = await axios.delete(`${authServiceUrl}/reset/${appName}`)
    const combined = { ...res.data }

    // MODE=3: also clear VueLocalAuth user table cache
    if (authMode === '3' && localAuthUrl) {
      try {
        const localRes = await axios.delete(`${localAuthUrl}/reset/${appName}`)
        combined.cleared = [...(combined.cleared || []), ...(localRes.data.cleared || [])]
      } catch (localErr) {
        // Non-fatal — RBAC cache was cleared successfully
        combined.cleared = [...(combined.cleared || []), `[VueLocalAuth reset failed: ${localErr.message}]`]
      }
    }

    result.value = combined
  } catch (err) {
    error.value = err.response?.data?.detail || err.message || 'Failed to clear cache'
  } finally {
    loading.value = false
  }
})
</script>
