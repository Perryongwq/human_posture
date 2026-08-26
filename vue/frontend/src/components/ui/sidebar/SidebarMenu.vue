<template>
  <ul v-bind="attrs">
    <slot />
  </ul>
</template>

<script setup>
import { useAttrs } from 'vue'

defineOptions({
  inheritAttrs: false,
})

const attrs = useAttrs()
</script>
