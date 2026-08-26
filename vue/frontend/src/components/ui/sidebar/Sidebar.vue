<template>
  <component
    :is="isMobile ? 'div' : 'aside'"
    v-bind="attrs"
    :data-state="open ? 'expanded' : 'collapsed'"
    :data-sidebar="'sidebar'"
    :class="sidebarClass"
  >
    <slot />
  </component>
</template>

<script setup>
import { computed, useAttrs } from 'vue'
import { useSidebar } from './composables.js'
import { cn } from '@/lib/utils'

defineOptions({
  inheritAttrs: false,
})

const props = defineProps({
  collapsible: { type: String, default: 'offcanvas' }, // 'offcanvas', 'icon', 'none'
  side: { type: String, default: 'left' },
  variant: { type: String, default: 'sidebar' },
})

const attrs = useAttrs()
const { open, isMobile } = useSidebar()

const sidebarClass = computed(() => {
  return cn(
    'flex flex-col',
    attrs.class
  )
})
</script>
