<template>
  <span class="ui-tag" :class="[`ui-tag--${tone}`]">
    <slot />
  </span>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    tone?: "default" | "success" | "danger" | "primary" | "warning";
  }>(),
  {
    tone: "default"
  }
);
</script>

<style scoped>
.ui-tag {
  display: inline-flex;
  align-items: center;
  gap: var(--间距-6);
  padding: var(--间距-4) var(--间距-8);
  border-radius: var(--圆角-999);
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(255, 255, 255, 0.06);
  font-size: var(--字号-12);
  color: rgba(255, 255, 255, 0.86);
}

.ui-tag--success {
  border-color: rgba(51, 214, 159, 0.35);
  background: rgba(51, 214, 159, 0.14);
}

.ui-tag--danger {
  border-color: rgba(255, 90, 95, 0.35);
  background: rgba(255, 90, 95, 0.14);
}

.ui-tag--primary {
  border-color: rgba(78, 161, 255, 0.35);
  background: rgba(78, 161, 255, 0.14);
}

.ui-tag--warning {
  border-color: rgba(255, 176, 32, 0.35);
  background: rgba(255, 176, 32, 0.14);
}
</style>
