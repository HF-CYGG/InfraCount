<template>
  <select
    class="ui-select"
    :class="[{ 'ui-select--invalid': props.invalid }]"
    :disabled="props.disabled"
    v-bind="$attrs"
    v-model="innerValue"
  >
    <slot />
  </select>
</template>

<script setup lang="ts">
defineOptions({ inheritAttrs: false });

import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    modelValue?: string | number | Array<string | number>;
    modelModifiers?: Record<string, boolean>;
    disabled?: boolean;
    invalid?: boolean;
  }>(),
  {
    modelValue: "",
    modelModifiers: () => ({}),
    disabled: false,
    invalid: false
  }
);

const emit = defineEmits<{
  (e: "update:modelValue", value: string | number | Array<string | number>): void;
}>();

const innerValue = computed({
  get: () => props.modelValue as any,
  set: (value: any) => {
    let out = value;
    if (props.modelModifiers?.trim) {
      if (Array.isArray(out)) out = out.map((x) => (typeof x === "string" ? x.trim() : x));
      else if (typeof out === "string") out = out.trim();
    }
    if (props.modelModifiers?.number) {
      if (Array.isArray(out)) out = out.map((x) => Number(x));
      else out = Number(out);
    }
    emit("update:modelValue", out);
  }
});
</script>

<style scoped>
.ui-select {
  width: 100%;
  border: var(--边框-卡片);
  background: rgba(0, 0, 0, 0.18);
  color: var(--颜色-文本);
  padding: var(--间距-10) var(--间距-12);
  border-radius: var(--圆角-10);
  outline: none;
  transition: border-color var(--动效-中) var(--ease-标准), box-shadow var(--动效-中) var(--ease-标准);
}

.ui-select:focus {
  border-color: rgba(78, 161, 255, 0.65);
  box-shadow: 0 0 0 3px rgba(78, 161, 255, 0.15);
}

.ui-select--invalid {
  border-color: rgba(255, 90, 95, 0.55);
  box-shadow: 0 0 0 3px rgba(255, 90, 95, 0.14);
}

.ui-select:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}
</style>
