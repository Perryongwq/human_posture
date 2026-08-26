<script setup>
import { Alert } from '@/components/ui/alert'

defineProps({
  variant: { type: String, default: 'info' }, // info | ok | warn | err
  title:   { type: String, default: '' },
})
</script>

<template>
  <Alert :variant="variant">
    <!-- info -->
    <svg v-if="variant === 'info'" viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>
    </svg>
    <!-- ok -->
    <svg v-else-if="variant === 'ok'" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="m22 4-10 10.01-3-3"/>
    </svg>
    <!-- warn -->
    <svg v-else-if="variant === 'warn'" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
      <path d="M12 9v4M12 17h.01"/>
    </svg>
    <!-- err -->
    <svg v-else-if="variant === 'err'" viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="10"/><path d="m15 9-6 6M9 9l6 6"/>
    </svg>
    <div><b v-if="title">{{ title }} — </b><slot /></div>
  </Alert>
</template>
