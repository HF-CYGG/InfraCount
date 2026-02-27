import { onBeforeUnmount, shallowRef, type Ref } from "vue";

export type ChunkedListOptions = {
  chunkSize?: number;
};

export function useChunkedList<T>(options?: ChunkedListOptions): {
  visible: Ref<T[]>;
  setSource: (items: T[]) => void;
  cancel: () => void;
} {
  const visible = shallowRef<T[]>([]);
  const chunkSize = Math.max(1, Number(options?.chunkSize ?? 60));

  let rafId: number | null = null;
  let token = 0;

  function cancel(): void {
    token += 1;
    if (rafId !== null) window.cancelAnimationFrame(rafId);
    rafId = null;
  }

  function setSource(items: T[]): void {
    cancel();
    visible.value = [];
    const localToken = token;
    const src = Array.isArray(items) ? items : [];
    if (!src.length) return;

    const first = src.slice(0, chunkSize);
    visible.value = first;
    let cursor = first.length;
    if (cursor >= src.length) return;

    const step = () => {
      if (token !== localToken) return;
      const next = src.slice(cursor, cursor + chunkSize);
      if (!next.length) return;
      visible.value = [...visible.value, ...next];
      cursor += next.length;
      if (cursor < src.length) rafId = window.requestAnimationFrame(step);
      else rafId = null;
    };
    rafId = window.requestAnimationFrame(step);
  }

  onBeforeUnmount(() => {
    cancel();
  });

  return { visible, setSource, cancel };
}

