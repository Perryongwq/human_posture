<script setup>
import { cn } from '@/lib/utils'
const props = defineProps({ class: { type: null, required: false } })
</script>

<template>
  <tr data-slot="table-empty">
    <td colspan="100%" :class="cn('text-muted-foreground h-24 text-center', props.class)">
      <slot>No results.</slot>
    </td>
  </tr>
</template>
