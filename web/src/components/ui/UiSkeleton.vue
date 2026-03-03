<template>
  <div class="ui-skeleton" :style="style" />
</template>

<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    width?: string;
    height?: string;
    radius?: string;
  }>(),
  {
    width: "100%",
    height: "12px",
    radius: "8px"
  }
);

const style = computed(() => ({
  width: props.width,
  height: props.height,
  borderRadius: props.radius
}));
</script>

<style scoped>
.ui-skeleton {
  background: linear-gradient(
    90deg,
    rgba(255, 255, 255, 0.04),
    rgba(255, 255, 255, 0.1),
    rgba(255, 255, 255, 0.04)
  );
  background-size: 200% 100%;
  animation: ui-shimmer 1200ms var(--ease-强调) infinite;
}

@keyframes ui-shimmer {
  0% {
    background-position: 0% 0%;
  }
  100% {
    background-position: -200% 0%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .ui-skeleton {
    animation: none;
  }
}
</style>
