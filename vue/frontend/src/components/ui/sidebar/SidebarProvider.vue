<template>
  <slot />
</template>

<script setup>
import { onMounted, watch } from 'vue'
import { provideSidebarContext } from './composables.js'

const props = defineProps({
  defaultOpen: { type: Boolean, default: true },
})

const emit = defineEmits(['update:open'])

const { open, setOpen } = provideSidebarContext(props.defaultOpen)

// Emit open state changes
watch(open, (newValue) => {
  emit('update:open', newValue)
})

// Sync prop changes
watch(() => props.defaultOpen, (newValue) => {
  setOpen(newValue)
})
</script>
