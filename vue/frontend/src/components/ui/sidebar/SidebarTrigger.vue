<template>
  <button
    v-bind="attrs"
    @click="toggleSidebar"
    type="button"
  >
    <MenuIcon v-if="!hideIcon" class="w-5 h-5" />
    <slot />
  </button>
</template>

<script setup>
import { useAttrs } from 'vue'
import { MenuIcon } from 'lucide-vue-next'
import { useSidebar } from './composables.js'

defineOptions({
  inheritAttrs: false,
})

defineProps({
  hideIcon: { type: Boolean, default: false },
})

const attrs = useAttrs()
const { toggleSidebar } = useSidebar()
</script>
