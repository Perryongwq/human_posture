// Sidebar composable for managing state
import { ref, computed, provide, inject } from 'vue'

const SIDEBAR_CONTEXT = Symbol('sidebar')

export function provideSidebarContext(defaultOpen = true) {
  const open = ref(defaultOpen)

  const context = {
    open,
    toggleSidebar: () => { open.value = !open.value },
    setOpen: (value) => { open.value = value },
  }

  provide(SIDEBAR_CONTEXT, context)
  return context
}

export function useSidebar() {
  const context = inject(SIDEBAR_CONTEXT, null)
  if (!context) {
    throw new Error('useSidebar must be used within SidebarProvider')
  }
  return context
}
