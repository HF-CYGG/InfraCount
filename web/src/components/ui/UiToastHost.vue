<template>
  <TransitionGroup class="ui-toast-host" tag="div" name="ui-toast" aria-live="polite" aria-relevant="additions">
    <div v-for="t in toastStore.state.toasts" :key="t.id" class="ui-toast" :class="[`ui-toast--${t.tone}`]">
      <div class="ui-toast__message">{{ t.message }}</div>
      <button class="ui-toast__close" type="button" @click="toastStore.remove(t.id)">×</button>
    </div>
  </TransitionGroup>
</template>

<script setup lang="ts">
import { toastStore } from "@/stores/toast";
</script>

<style scoped>
.ui-toast-host {
  position: fixed;
  right: var(--间距-14);
  bottom: var(--间距-14);
  z-index: var(--z-Toast);
  display: flex;
  flex-direction: column;
  gap: var(--间距-10);
  pointer-events: none;
}

.ui-toast {
  pointer-events: auto;
  min-width: min(360px, calc(100vw - 28px));
  border-radius: var(--圆角-12);
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(15, 23, 41, 0.92);
  backdrop-filter: blur(10px);
  box-shadow: var(--阴影);
  padding: var(--间距-10) var(--间距-12);
  display: flex;
  align-items: flex-start;
  gap: var(--间距-10);
}

.ui-toast__message {
  flex: 1;
  line-height: 1.5;
  font-size: var(--字号-13);
}

.ui-toast__close {
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.8);
  width: 28px;
  height: 28px;
  border-radius: var(--圆角-8);
  cursor: pointer;
}

.ui-toast--success {
  border-color: rgba(51, 214, 159, 0.28);
}

.ui-toast--danger {
  border-color: rgba(255, 90, 95, 0.28);
}

.ui-toast--primary {
  border-color: rgba(78, 161, 255, 0.28);
}

.ui-toast--warning {
  border-color: rgba(255, 176, 32, 0.28);
}
</style>
