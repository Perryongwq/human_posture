<script setup>
import { Input } from '@/components/ui/input'

const props = defineProps({
  modelValue:  { type: [String, Number], default: '' },
  label:       { type: String,  default: '' },
  id:          { type: String,  default: () => `mu-input-${Math.random().toString(36).slice(2, 7)}` },
  type:        { type: String,  default: 'text' },
  placeholder: { type: String,  default: '' },
  error:       { type: String,  default: '' },
  required:    { type: Boolean, default: false },
  disabled:    { type: Boolean, default: false },
  class:       { type: [String, Object, Array], default: '' },
})

defineEmits(['update:modelValue'])
</script>

<template>
  <div :class="['mu-field', { 'mu-err': !!props.error }]">
    <label v-if="props.label" :for="props.id">
      {{ props.label }}<span v-if="props.required" class="mu-req"> *</span>
    </label>
    <Input
      :id="props.id"
      :class="props.class"
      :type="props.type"
      :placeholder="props.placeholder"
      :disabled="props.disabled"
      :model-value="props.modelValue"
      v-bind="$attrs"
      @update:model-value="$emit('update:modelValue', $event)"
    />
    <p v-if="props.error" class="mu-field-hint">{{ props.error }}</p>
  </div>
</template>
