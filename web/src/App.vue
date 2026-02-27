<!--
  根组件

  设计说明：
  - 单页应用（SPA）通常只在根组件里放一个 <RouterView />；
  - 这里额外做一层“登录态自检”，避免页面首次进入时闪烁：
    1) 先尝试向后端请求 /api/v1/auth/me；
    2) 再由路由守卫决定跳转到登录页或业务页。
-->
<template>
  <RouterView />
</template>

<script setup lang="ts">
/**
 * 根组件脚本
 *
 * 为什么在这里做一次“预热加载”：
 * - 如果用户之前已经登录（浏览器里有 session_token Cookie），
 *   我们希望首次进入 SPA 就能直接进业务页，而不是先跳到 /login 再跳回来。
 * - authStore.init() 会尽可能“温和”地尝试读取当前用户，不会弹窗打扰。
 */

import { onMounted } from "vue";
import { authStore } from "@/stores/auth";

onMounted(() => {
  void authStore.init();
});
</script>

