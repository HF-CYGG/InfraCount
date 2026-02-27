<template>
  <RouterLink class="ui-link-button" :class="[`ui-link-button--${variant}`, `ui-link-button--${size}`]" :to="to">
    <slot />
  </RouterLink>
</template>

<script setup lang="ts">
import { RouterLink } from "vue-router";

withDefaults(
  defineProps<{
    to: string;
    variant?: "default" | "primary" | "danger";
    size?: "sm" | "md";
  }>(),
  {
    variant: "default",
    size: "md"
  }
);
</script>

<style scoped>
.ui-link-button {
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
  text-decoration: none;
}

.ui-link-button--md {
  padding: var(--间距-10) var(--间距-12);
  font-size: var(--字号-14);
}

.ui-link-button--sm {
  padding: var(--间距-8) var(--间距-10);
  font-size: var(--字号-12);
}

.ui-link-button:hover {
  background: rgba(255, 255, 255, 0.09);
  border-color: rgba(255, 255, 255, 0.18);
}

.ui-link-button:active {
  transform: translateY(1px);
}

.ui-link-button--primary {
  background: rgba(78, 161, 255, 0.18);
  border-color: rgba(78, 161, 255, 0.42);
}

.ui-link-button--danger {
  background: rgba(255, 90, 95, 0.14);
  border-color: rgba(255, 90, 95, 0.38);
}
</style>
