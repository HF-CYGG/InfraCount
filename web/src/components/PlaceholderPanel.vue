<!--
  通用占位面板组件

  目的：
  - 让“尚未实现”的页面也能有统一的展示风格；
  - 页面只需要传入标题/说明/后续规划即可。
-->
<template>
  <div class="卡片 面板">
    <div class="面板标题">{{ title }}</div>
    <div class="面板说明 提示-次要">{{ description }}</div>
    <ul v-if="nextSteps.length" class="面板列表">
      <li v-for="(it, idx) in nextSteps" :key="idx">{{ it }}</li>
    </ul>
    <slot />
  </div>
</template>

<script setup lang="ts">
/**
 * 占位面板脚本
 *
 * 参数说明：
 * - title：面板标题
 * - description：当前页面的“占位说明”
 * - nextSteps：后续可实现的功能点（纯展示，不做逻辑）
 */

withDefaults(
  defineProps<{
    title: string;
    description: string;
    nextSteps?: string[];
  }>(),
  {
    nextSteps: () => []
  }
);
</script>

<style scoped>
.面板 {
  padding: 16px;
}

.面板标题 {
  font-size: 16px;
  font-weight: 800;
}

.面板说明 {
  margin-top: 8px;
  line-height: 1.6;
}

.面板列表 {
  margin: 12px 0 0 0;
  padding: 0 0 0 18px;
  color: var(--颜色-次要文本);
}
</style>

