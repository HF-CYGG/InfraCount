import { reactive } from "vue";

export type ToastTone = "default" | "success" | "danger" | "primary" | "warning";

export type ToastItem = {
  id: string;
  message: string;
  tone: ToastTone;
  durationMs: number;
};

type ToastState = {
  toasts: ToastItem[];
};

const state = reactive<ToastState>({
  toasts: []
});

function remove(id: string): void {
  const idx = state.toasts.findIndex((t) => t.id === id);
  if (idx >= 0) state.toasts.splice(idx, 1);
}

function push(
  message: string,
  options?: {
    tone?: ToastTone;
    durationMs?: number;
  }
): string {
  const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const item: ToastItem = {
    id,
    message,
    tone: options?.tone ?? "default",
    durationMs: options?.durationMs ?? 2600
  };

  state.toasts.push(item);

  window.setTimeout(() => {
    remove(id);
  }, item.durationMs);

  return id;
}

export const toastStore = {
  state,
  push,
  remove
};

