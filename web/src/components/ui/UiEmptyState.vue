<template>
  <div class="ui-empty">
    <div class="ui-empty__title">{{ title }}</div>
    <div v-if="description" class="ui-empty__desc">{{ description }}</div>
    <div v-if="$slots.action" class="ui-empty__action">
      <slot name="action" />
    </div>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    title?: string;
    description?: string;
  }>(),
  {
    title: "暂无数据",
    description: ""
  }
);
</script>

<style scoped>
.ui-empty {
  padding: var(--间距-16);
  text-align: center;
  border-radius: var(--圆角-12);
  border: 1px dashed rgba(255, 255, 255, 0.12);
  background: var(--颜色-面板2);
  color: var(--颜色-次要文本);
}

.ui-empty__title {
  font-weight: 800;
  font-size: var(--字号-14);
}

.ui-empty__desc {
  margin-top: var(--间距-8);
  font-size: var(--字号-12);
  color: var(--颜色-次要文本);
  line-height: 1.6;
}

.ui-empty__action {
  margin-top: var(--间距-12);
  display: flex;
  justify-content: center;
}
</style>
