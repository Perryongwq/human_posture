<template>
  <div v-bind="attrs">
    <slot />
  </div>
</template>

<script setup>
import { useAttrs } from 'vue'

defineOptions({
  inheritAttrs: false,
})

const attrs = useAttrs()
</script>
