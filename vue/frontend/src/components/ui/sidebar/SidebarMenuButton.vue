<template>
  <component
    :is="asChild ? 'slot' : 'button'"
    v-bind="!asChild ? attrs : {}"
  >
    <slot v-if="!asChild" />
    <slot v-else />
  </component>
</template>

<script setup>
import { useAttrs } from 'vue'

defineOptions({
  inheritAttrs: false,
})

defineProps({
  asChild: { type: Boolean, default: false },
})

const attrs = useAttrs()
</script>
