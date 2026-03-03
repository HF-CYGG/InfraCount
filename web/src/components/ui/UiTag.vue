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
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.04);
  font-size: var(--字号-12);
  color: rgba(255, 255, 255, 0.86);
}

.ui-tag--success {
  border-color: rgba(var(--颜色-成功-rgb), 0.35);
  background: rgba(var(--颜色-成功-rgb), 0.14);
}

.ui-tag--danger {
  border-color: rgba(var(--颜色-危险-rgb), 0.35);
  background: rgba(var(--颜色-危险-rgb), 0.14);
}

.ui-tag--primary {
  border-color: rgba(var(--颜色-强调-rgb), 0.35);
  background: rgba(var(--颜色-强调-rgb), 0.14);
}

.ui-tag--warning {
  border-color: rgba(var(--颜色-警告-rgb), 0.35);
  background: rgba(var(--颜色-警告-rgb), 0.14);
}
</style>
