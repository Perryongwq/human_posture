<script setup>
import { computed } from 'vue'

const props = defineProps({
  value: { type: [String, Number], required: true },
  label: { type: String, required: true },
  delta: { type: String, default: '' }, // e.g. "+12 this month" — pass empty to hide
})

const isPositive = computed(() => props.delta.trimStart().startsWith('+') || props.delta.trimStart().startsWith('↑'))
</script>

<template>
  <div class="mu-stat">
    <div class="mu-stat-val">{{ value }}</div>
    <div class="mu-stat-label">{{ label }}</div>
    <div v-if="delta" class="mu-stat-delta" :class="isPositive ? 'mu-up' : 'mu-down'">
      {{ delta }}
    </div>
  </div>
</template>
