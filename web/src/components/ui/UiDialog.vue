<template>
  <Teleport to="body">
    <Transition name="ui-dialog" appear>
      <div v-if="open" class="ui-dialog__overlay" @click.self="cancel">
        <div class="ui-dialog" role="dialog" aria-modal="true" :aria-label="title">
          <div class="ui-dialog__header">
            <div class="ui-dialog__title">{{ title }}</div>
            <button class="ui-dialog__close" type="button" @click="cancel">×</button>
          </div>
          <div class="ui-dialog__body">
            <slot />
          </div>
          <div class="ui-dialog__footer">
            <slot name="footer">
              <UiButton v-if="showCancel" size="sm" :disabled="loading" @click="cancel">
                {{ cancelText }}
              </UiButton>
              <UiButton size="sm" :variant="confirmVariant" :loading="loading" @click="confirm">
                {{ confirmText }}
              </UiButton>
            </slot>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted } from "vue";
import UiButton from "@/components/ui/UiButton.vue";

const props = withDefaults(
  defineProps<{
    open: boolean;
    title: string;
    confirmText?: string;
    cancelText?: string;
    showCancel?: boolean;
    confirmVariant?: "default" | "primary" | "danger";
    loading?: boolean;
  }>(),
  {
    confirmText: "确认",
    cancelText: "取消",
    showCancel: true,
    confirmVariant: "primary",
    loading: false
  }
);

const emit = defineEmits<{
  (e: "update:open", value: boolean): void;
  (e: "confirm"): void;
  (e: "cancel"): void;
}>();

function cancel(): void {
  emit("update:open", false);
  emit("cancel");
}

function confirm(): void {
  emit("confirm");
}

function onKeyDown(e: KeyboardEvent): void {
  if (!props.open) return;
  if (e.key === "Escape") cancel();
}

onMounted(() => {
  window.addEventListener("keydown", onKeyDown);
});

onBeforeUnmount(() => {
  window.removeEventListener("keydown", onKeyDown);
});
</script>

<style scoped>
.ui-dialog-enter-active,
.ui-dialog-leave-active {
  transition: opacity var(--动效-中) var(--ease-标准);
}

.ui-dialog-enter-from,
.ui-dialog-leave-to {
  opacity: 0;
}

.ui-dialog-enter-active .ui-dialog,
.ui-dialog-leave-active .ui-dialog {
  transition: transform var(--动效-中) var(--ease-强调), opacity var(--动效-中) var(--ease-标准);
}

.ui-dialog-enter-from .ui-dialog,
.ui-dialog-leave-to .ui-dialog {
  transform: translateY(6px) scale(0.985);
  opacity: 0;
}

.ui-dialog__overlay {
  position: fixed;
  inset: 0;
  z-index: var(--z-对话框);
  display: grid;
  place-items: center;
  padding: var(--间距-14);
  background: rgba(0, 0, 0, 0.6);
}

.ui-dialog {
  width: min(560px, 100%);
  border-radius: var(--圆角-12);
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: var(--颜色-面板);
  box-shadow: var(--阴影);
  overflow: hidden;
}

.ui-dialog__header {
  display: flex;
  align-items: center;
  gap: var(--间距-10);
  padding: var(--间距-12) var(--间距-14);
  border-bottom: var(--边框-分隔);
}

.ui-dialog__title {
  font-weight: 800;
  font-size: var(--字号-16);
  flex: 1;
}

.ui-dialog__close {
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.04);
  color: rgba(255, 255, 255, 0.8);
  width: 32px;
  height: 32px;
  border-radius: var(--圆角-8);
  cursor: pointer;
  transition: background var(--动效-中) var(--ease-标准), border-color var(--动效-中) var(--ease-标准),
    transform var(--动效-快) var(--ease-标准);
}

.ui-dialog__close:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.18);
}

.ui-dialog__close:active {
  transform: translateY(1px);
}

.ui-dialog__body {
  padding: var(--间距-14);
  line-height: 1.6;
  color: var(--颜色-文本);
}

.ui-dialog__footer {
  padding: var(--间距-12) var(--间距-14);
  border-top: var(--边框-分隔);
  display: flex;
  justify-content: flex-end;
  gap: var(--间距-10);
}

@media (prefers-reduced-motion: reduce) {
  .ui-dialog-enter-active,
  .ui-dialog-leave-active,
  .ui-dialog-enter-active .ui-dialog,
  .ui-dialog-leave-active .ui-dialog,
  .ui-dialog__close {
    transition-duration: 1ms !important;
  }
}
</style>
