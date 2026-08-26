<template>
  <component :is="as" v-bind="attrs">
    <slot />
  </component>
</template>

<script setup>
import { useAttrs } from 'vue'

defineOptions({
  inheritAttrs: false,
})

defineProps({
  as: { type: String, default: 'div' },
})

const attrs = useAttrs()
</script>
