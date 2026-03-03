<template>
  <input
    class="ui-input"
    :class="[{ 'ui-input--invalid': props.invalid }]"
    :value="props.modelValue"
    :type="props.type"
    :placeholder="props.placeholder"
    :disabled="props.disabled"
    :readonly="props.readonly"
    v-bind="$attrs"
    @input="onInput"
  />
</template>

<script setup lang="ts">
defineOptions({ inheritAttrs: false });

const props = withDefaults(
  defineProps<{
    modelValue?: string | number;
    modelModifiers?: Record<string, boolean>;
    type?: string;
    placeholder?: string;
    disabled?: boolean;
    readonly?: boolean;
    invalid?: boolean;
  }>(),
  {
    modelValue: "",
    modelModifiers: () => ({}),
    type: "text",
    placeholder: "",
    disabled: false,
    readonly: false,
    invalid: false
  }
);

const emit = defineEmits<{
  (e: "update:modelValue", value: string | number): void;
}>();

function onInput(e: Event): void {
  const raw = (e.target as HTMLInputElement).value;
  const v = props.modelModifiers?.trim ? raw.trim() : raw;
  emit("update:modelValue", props.modelModifiers?.number ? Number(v) : v);
}
</script>

<style scoped>
.ui-input {
  width: 100%;
  border: var(--边框-卡片);
  background: var(--颜色-面板2);
  color: var(--颜色-文本);
  padding: var(--间距-10) var(--间距-12);
  border-radius: var(--圆角-10);
  outline: none;
  transition: border-color var(--动效-中) var(--ease-标准), box-shadow var(--动效-中) var(--ease-标准);
}

.ui-input:focus {
  border-color: rgba(var(--颜色-强调-rgb), 0.65);
  box-shadow: 0 0 0 3px rgba(var(--颜色-强调-rgb), 0.12);
}

.ui-input--invalid {
  border-color: rgba(var(--颜色-危险-rgb), 0.55);
  box-shadow: 0 0 0 3px rgba(var(--颜色-危险-rgb), 0.12);
}

.ui-input:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}
</style>
