<template>
  <div class="ui-loading" :class="[`ui-loading--${size}`]">
    <span class="ui-loading__spinner" aria-hidden="true" />
    <span v-if="text" class="ui-loading__text">{{ text }}</span>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    text?: string;
    size?: "sm" | "md";
  }>(),
  {
    text: "",
    size: "md"
  }
);
</script>

<style scoped>
.ui-loading {
  display: inline-flex;
  align-items: center;
  gap: var(--间距-10);
  color: var(--颜色-次要文本);
}

.ui-loading__spinner {
  border-radius: 999px;
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-top-color: rgba(var(--颜色-强调-rgb), 0.85);
  animation: ui-spin 700ms linear infinite;
}

.ui-loading--md .ui-loading__spinner {
  width: 18px;
  height: 18px;
}

.ui-loading--sm .ui-loading__spinner {
  width: 14px;
  height: 14px;
}

.ui-loading__text {
  font-size: var(--字号-13);
}

@keyframes ui-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .ui-loading__spinner {
    animation: none;
  }
}
</style>
