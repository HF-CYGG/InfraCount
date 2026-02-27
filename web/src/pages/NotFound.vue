<!--
  404 页面
-->
<template>
  <div class="容器">
    <div class="卡片 面板">
      <div class="标题">页面未找到</div>
      <div class="说明 提示-次要">你访问的地址不存在，可能已被移动或删除。</div>
      <div class="操作区">
        <RouterLink class="按钮 强调" to="/dashboard">返回看板</RouterLink>
        <RouterLink class="按钮" to="/login">去登录页</RouterLink>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 404 页脚本（占位）
 * - 无业务逻辑，仅用于路由兜底展示。
 */
</script>

<style scoped>
.容器 {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 14px;
}

.面板 {
  padding: 18px;
  width: min(520px, 100%);
}

.标题 {
  font-size: 20px;
  font-weight: 900;
}

.说明 {
  margin-top: 10px;
  line-height: 1.6;
}

.操作区 {
  margin-top: 14px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
</style>

