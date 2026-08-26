<!-- frontend/src/views/UnauthorizedView.vue -->
<template>
  <div class="min-h-screen flex items-center justify-center bg-background">
    <div class="w-[480px] rounded-lg border border-border bg-card text-card-foreground shadow-sm p-6 space-y-4">

      <!-- Header -->
      <div class="space-y-1">
        <h2 class="text-lg font-semibold leading-tight text-destructive">Access Denied</h2>
        <p class="text-sm text-muted-foreground">
          You do not have permission to access
          <strong class="text-foreground">{{ appName }}</strong>{{ screenLabel }}.
        </p>
      </div>

      <!-- User info -->
      <div v-if="currentUser" class="rounded-md border border-border bg-muted/40 px-4 py-3 space-y-2">
        <p class="text-xs font-medium text-muted-foreground uppercase tracking-wide">Logged in as</p>
        <div class="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
          <span class="text-muted-foreground">Name</span>
          <span class="font-medium text-foreground font-mono">{{ currentUser.username }}</span>
          <span class="text-muted-foreground">Payroll</span>
          <span class="font-medium text-foreground font-mono">{{ currentUser.payroll }}</span>
          <span class="text-muted-foreground">Department</span>
          <span class="font-medium text-foreground font-mono">{{ currentUser.deptcode }}</span>
        </div>
      </div>

      <!-- Advisory -->
      <div class="rounded-md bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive">
        Contact your system administrator if you believe this is an error.
      </div>

      <div class="flex justify-end pt-2">
        <RouterLink to="/" class="text-sm font-medium text-primary hover:underline">← Go Home</RouterLink>
      </div>

    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuth } from '../composables/useAuth.js'

const route = useRoute()
const { currentUser } = useAuth()

const appName = import.meta.env.VITE_APP_NAME || 'This Application'
const screenLabel = computed(() =>
  route.query.screen ? ` (screen: ${route.query.screen})` : ''
)
</script>

