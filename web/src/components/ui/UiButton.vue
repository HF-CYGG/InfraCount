<template>
  <button
    class="ui-button"
    :class="[`ui-button--${variant}`, `ui-button--${size}`]"
    :type="type"
    :disabled="disabled || loading"
  >
    <span v-if="loading" class="ui-button__spinner" aria-hidden="true" />
    <span class="ui-button__content">
      <slot />
    </span>
  </button>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    variant?: "default" | "primary" | "danger";
    size?: "sm" | "md";
    type?: "button" | "submit" | "reset";
    disabled?: boolean;
    loading?: boolean;
  }>(),
  {
    variant: "default",
    size: "md",
    type: "button",
    disabled: false,
    loading: false
  }
);
</script>

<style scoped>
.ui-button {
  border: var(--边框-卡片);
  background: rgba(255, 255, 255, 0.06);
  color: var(--颜色-文本);
  border-radius: var(--圆角-10);
  cursor: pointer;
  transition: transform var(--动效-快) var(--ease-标准), background var(--动效-中) var(--ease-标准),
    border-color var(--动效-中) var(--ease-标准), opacity var(--动效-中) var(--ease-标准);
  display: inline-flex;
  align-items: center;
  gap: var(--间距-8);
  justify-content: center;
  user-select: none;
}

.ui-button--md {
  padding: var(--间距-10) var(--间距-12);
  font-size: var(--字号-14);
}

.ui-button--sm {
  padding: var(--间距-8) var(--间距-10);
  font-size: var(--字号-12);
}

.ui-button:hover {
  background: rgba(255, 255, 255, 0.09);
  border-color: rgba(255, 255, 255, 0.18);
}

.ui-button:active {
  transform: translateY(1px);
}

.ui-button:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.ui-button--primary {
  background: rgba(78, 161, 255, 0.18);
  border-color: rgba(78, 161, 255, 0.42);
}

.ui-button--danger {
  background: rgba(255, 90, 95, 0.14);
  border-color: rgba(255, 90, 95, 0.38);
}

.ui-button__spinner {
  width: 14px;
  height: 14px;
  border-radius: 999px;
  border: 2px solid rgba(255, 255, 255, 0.25);
  border-top-color: rgba(255, 255, 255, 0.8);
  animation: ui-spin 700ms linear infinite;
}

.ui-button__content {
  display: inline-flex;
  align-items: center;
  gap: var(--间距-8);
}

@keyframes ui-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
