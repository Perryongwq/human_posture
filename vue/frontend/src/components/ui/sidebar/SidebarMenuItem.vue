<template>
  <li v-bind="attrs">
    <slot />
  </li>
</template>

<script setup>
import { useAttrs } from 'vue'

defineOptions({
  inheritAttrs: false,
})

const attrs = useAttrs()
</script>
