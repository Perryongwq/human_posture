<!-- frontend/src/components/AppLayout.vue — using shadcn-vue Sidebar -->
<template>
  <!-- User profile popover (teleported to body to escape aside overflow-hidden) -->
  <Teleport to="body">
    <div
      v-if="popoverOpen"
      ref="popoverRef"
      :style="popoverStyle"
      class="fixed z-50 bg-popover text-popover-foreground border border-border rounded-lg shadow-md p-1 min-w-[200px]"
    >
      <div class="flex items-center gap-3 px-3 py-2">
        <div class="w-8 h-8 rounded-full bg-primary text-primary-foreground flex items-center justify-center shrink-0 text-xs font-semibold">
          {{ initials }}
        </div>
        <div class="min-w-0">
          <p class="text-sm font-medium leading-tight truncate">{{ username }}</p>
          <p class="text-xs text-sidebar-foreground/60 leading-normal truncate">{{ payroll }} · {{ deptcode }}</p>
        </div>
      </div>
      <div class="h-px bg-border mx-1 my-1" />
      <button
        @click="handleLogout"
        class="flex items-center gap-2 w-full px-3 py-2 text-sm rounded-md hover:bg-accent hover:text-accent-foreground transition-colors"
        aria-label="Log out"
      >
        <LogOutIcon class="w-4 h-4" aria-hidden="true" />
        Log out
      </button>
    </div>
  </Teleport>

  <SidebarProvider :default-open="!isCollapsed" @update:open="handleOpenChange">
    <div class="flex h-screen overflow-hidden bg-background text-foreground">

      <!-- Sidebar -->
      <Sidebar
        collapsible="icon"
        class="flex flex-col shrink-0 bg-sidebar text-sidebar-foreground border-r border-border overflow-hidden transition-[width] duration-300 ease-in-out"
        :class="open ? 'w-64' : 'w-16'"
        aria-label="Sidebar"
      >
        <!-- Logo -->
        <SidebarHeader class="flex items-center justify-center h-16 px-3 shrink-0 border-b border-border/40">
          <img
            src="/logo.png"
            alt="Company Logo"
            class="object-contain transition-all duration-300"
            :class="open ? 'h-10 w-auto max-w-[160px]' : 'h-8 w-8'"
          />
        </SidebarHeader>

        <!-- Navigation -->
        <SidebarContent as="nav" class="flex-1 px-2 py-4 space-y-1 overflow-y-auto" aria-label="Main navigation">
          <SidebarMenu>
            <SidebarMenuItem v-for="item in navItems" :key="item.to">
              <SidebarMenuButton as-child>
                <RouterLink
                  :to="item.to"
                  v-bind="item.exact ? { exactActiveClass: 'bg-sidebar-primary/15 text-sidebar-primary font-medium', activeClass: '' }
                                     : { activeClass: 'bg-sidebar-primary/15 text-sidebar-primary font-medium' }"
                  class="flex items-center gap-3 px-3 py-2 rounded-md text-sm text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-foreground transition-colors"
                  :class="open ? '' : 'justify-center'"
                  :title="open ? undefined : item.label"
                  aria-current-value="page"
                >
                  <component :is="item.icon" class="w-5 h-5 shrink-0" aria-hidden="true" />
                  <span v-show="open" class="truncate">{{ item.label }}</span>
                </RouterLink>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarContent>

        <!-- User profile -->
        <SidebarFooter
          v-if="!authModeOff"
          class="shrink-0 border-t border-border/40"
        >
          <div ref="profileRef">
            <button
              @click="popoverOpen = !popoverOpen"
              class="flex items-center w-full p-3 gap-3 hover:bg-sidebar-accent transition-colors"
              :class="open ? '' : 'justify-center'"
              :title="open ? undefined : currentUser?.username"
              aria-label="User profile"
              aria-haspopup="true"
              :aria-expanded="popoverOpen"
            >
              <div class="w-8 h-8 rounded-full bg-primary text-primary-foreground flex items-center justify-center shrink-0 text-xs font-semibold">
                {{ initials }}
              </div>
              <div v-show="open" class="min-w-0 flex-1 text-left">
                <p class="text-sm font-medium leading-tight truncate">{{ username }}</p>
                <p class="text-xs text-sidebar-foreground/60 leading-normal truncate">{{ payroll }} · {{ deptcode }}</p>
              </div>
              <ChevronsUpDownIcon v-show="open" class="w-4 h-4 shrink-0 text-sidebar-foreground/40" aria-hidden="true" />
            </button>
          </div>
        </SidebarFooter>

        <!-- Dev footer -->
        <div v-show="open" class="shrink-0 px-3 py-1 text-center">
          <p class="text-xs">Developed By SP5143</p>
        </div>
      </Sidebar>

      <!-- Main area -->
      <div class="flex flex-col flex-1 overflow-hidden">
        <!-- Header -->
        <header class="h-14 bg-sidebar border-b border-border flex items-center px-4 gap-3 shrink-0">
          <SidebarTrigger
            class="p-1.5 rounded-md text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
            aria-label="Toggle sidebar"
            hide-icon
          >
            <MenuIcon class="w-5 h-5" aria-hidden="true" />
          </SidebarTrigger>
          <span class="text-sm font-semibold leading-tight">{{ route.meta.title }}</span>

          <!-- Right-side header actions -->
          <div class="ml-auto flex items-center gap-3">
            <!-- Dark mode toggle -->
            <button
              @click="toggleDark"
              class="p-1.5 rounded-md text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
              :aria-label="isDark ? 'Switch to light mode' : 'Switch to dark mode'"
              :title="isDark ? 'Light mode' : 'Dark mode'"
            >
              <SunIcon v-if="isDark" class="w-5 h-5" aria-hidden="true" />
              <MoonIcon v-else class="w-5 h-5" aria-hidden="true" />
            </button>

            <!-- Affiliate badge -->
            <span
              v-if="affiliateBadge"
              class="inline-flex items-center rounded-md bg-muted border border-muted-foreground/30 px-2 py-0.5 text-xs font-semibold text-red-600 dark:text-red-400"
            >
              {{ affiliateBadge }}
            </span>

            <!-- Clock -->
            <div class="text-right leading-tight tabular-nums">
              <p class="text-sm font-semibold">{{ clockTime }}</p>
              <p class="text-xs text-muted-foreground">{{ clockDate }}</p>
            </div>
          </div>
        </header>

        <!-- Content -->
        <main class="flex-1 overflow-y-auto p-6">
          <RouterView />
        </main>
      </div>

    </div>
  </SidebarProvider>
</template>

<script setup>
import { ref, watch, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { MenuIcon, LogOutIcon, ChevronsUpDownIcon, SunIcon, MoonIcon } from 'lucide-vue-next'
import {
  SidebarProvider, Sidebar, SidebarHeader, SidebarContent, SidebarFooter,
  SidebarMenu, SidebarMenuItem, SidebarMenuButton, SidebarTrigger, useSidebar
} from '@/components/ui/sidebar'
import { useAuth } from '../composables/useAuth.js'
import { useRbac } from '../composables/useRbac.js'
import navConfig from '../nav.config.js'

const route = useRoute()
const { currentUser, logout } = useAuth()

const authModeOff    = import.meta.env.VITE_AUTH_MODE === '0'
const authMode       = import.meta.env.VITE_AUTH_MODE
const affiliateBadge = import.meta.env.VITE_AFFILIATE_BADGE

const { can } = useRbac()

// Initialize collapsed state from localStorage
const isCollapsed = ref(localStorage.getItem('sidebar_collapsed') === 'true')

// Sidebar open state — driven by both localStorage and viewport width
const open = ref(!isCollapsed.value)

// Auto-collapse when viewport < 768px; restore from localStorage when wide again
const MOBILE_BREAKPOINT = 768
function checkViewport() {
  const isMobile = window.innerWidth < MOBILE_BREAKPOINT
  if (isMobile) {
    open.value = false           // always collapse on mobile
  } else {
    open.value = !isCollapsed.value  // restore saved preference on desktop
  }
}

// Sync open state to localStorage (only on desktop — don't persist mobile collapse)
const handleOpenChange = (newOpen) => {
  open.value = newOpen
  if (window.innerWidth >= MOBILE_BREAKPOINT) {
    isCollapsed.value = !newOpen
    localStorage.setItem('sidebar_collapsed', String(!newOpen))
  }
}

// In AUTH_MODE=2/3 filter items by RBAC; all other modes show everything.
const navItems = computed(() => {
  if (!['2', '3'].includes(authMode)) return navConfig
  return navConfig.filter(item => !item.requiredScreen || can(item.requiredScreen))
})

const initials  = computed(() => {
  const parts = currentUser.value?.username?.split(' ') ?? []
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase()
  return parts[0]?.slice(0, 2).toUpperCase() ?? '??'
})
const username  = computed(() => currentUser.value?.username)
const deptcode  = computed(() => currentUser.value?.deptcode)
const payroll   = computed(() => currentUser.value?.payroll)

// ── Profile popover ──────────────────────────────────────────────────────────
const popoverOpen = ref(false)
const profileRef  = ref(null)
const popoverRef  = ref(null)
const popoverStyle = ref({})

watch(popoverOpen, (val) => {
  if (val && profileRef.value) {
    const rect = profileRef.value.getBoundingClientRect()
    popoverStyle.value = {
      bottom: `${window.innerHeight - rect.top + 8}px`,
      left:   `${rect.left}px`,
      width:  `${Math.max(rect.width, 220)}px`,
    }
  }
})

function handleLogout() {
  popoverOpen.value = false
  logout()
}

function handleDocumentClick(e) {
  if (
    popoverOpen.value &&
    !profileRef.value?.contains(e.target) &&
    !popoverRef.value?.contains(e.target)
  ) {
    popoverOpen.value = false
  }
}

// ── Dark mode ────────────────────────────────────────────────────────────────
const isDark = ref(localStorage.getItem('dark_mode') === 'true')

function applyDark(val) {
  document.documentElement.classList.toggle('dark', val)
}

function toggleDark() {
  isDark.value = !isDark.value
  localStorage.setItem('dark_mode', String(isDark.value))
  applyDark(isDark.value)
}

// ── Clock ────────────────────────────────────────────────────────────────────
const now = ref(new Date())
let clockTimer = null

onMounted(() => {
  applyDark(isDark.value)
  checkViewport()
  window.addEventListener('resize', checkViewport)
  clockTimer = setInterval(() => { now.value = new Date() }, 1000)
  document.addEventListener('click', handleDocumentClick)
})
onUnmounted(() => {
  window.removeEventListener('resize', checkViewport)
  clearInterval(clockTimer)
  document.removeEventListener('click', handleDocumentClick)
})

const clockTime = computed(() => now.value.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }))
const clockDate = computed(() => now.value.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }))
</script>
