<!--
  登录页

  功能：
  - 提供用户名/密码输入；
  - 调用后端 /api/v1/auth/login；
  - 登录成功后跳转：
    1) 若 URL 上带 redirect 参数，则返回原先要去的页面；
    2) 否则默认进入 /dashboard。
-->
<template>
  <div class="容器">
    <div class="卡片 登录卡片">
      <div class="标题区">
        <img
          class="登录-LCP图"
          :src="lcpLogoUrl"
          width="240"
          height="240"
          alt="InfraCount"
          decoding="async"
          fetchpriority="high"
        />
        <div class="区块标题">InfraCount</div>
        <div class="区块说明">管理后台（SPA） · 请先登录以继续</div>
      </div>

      <form class="表单" @submit.prevent="提交登录">
        <label class="字段">
          <div class="字段标题">用户名</div>
          <UiInput v-model.trim="username" autocomplete="username" placeholder="请输入用户名" />
        </label>

        <label class="字段">
          <div class="字段标题">密码</div>
          <UiInput v-model="password" type="password" autocomplete="current-password" placeholder="请输入密码" />
        </label>

        <div v-if="错误信息" class="提示-错误">{{ 错误信息 }}</div>
        <div class="提示-次要">默认账号：admin / admin（首次启动自动创建）</div>

        <UiButton class="登录按钮" variant="primary" type="submit" :loading="loading">
          {{ loading ? "正在登录..." : "登录" }}
        </UiButton>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 登录页脚本
 *
 * 关键实现逻辑：
 * - 登录按钮触发提交；
 * - authStore.login() 会调用后端并写入 Cookie；
 * - 登录成功后读取 redirect 参数跳转；
 * - 若已经登录，则直接跳转到 /dashboard，避免重复登录。
 */

import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ApiError } from "@/api/client";
import { authStore } from "@/stores/auth";
import UiButton from "@/components/ui/UiButton.vue";
import UiInput from "@/components/ui/UiInput.vue";

const lcpLogoUrl =
  "data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A//www.w3.org/2000/svg%22%20width%3D%22512%22%20height%3D%22512%22%3E%3Cdefs%3E%3ClinearGradient%20id%3D%22g%22%20x1%3D%220%22%20y1%3D%220%22%20x2%3D%221%22%20y2%3D%221%22%3E%3Cstop%20stop-color%3D%22%237c5cff%22/%3E%3Cstop%20offset%3D%221%22%20stop-color%3D%22%230b0f17%22/%3E%3C/linearGradient%3E%3C/defs%3E%3Crect%20width%3D%22512%22%20height%3D%22512%22%20rx%3D%2296%22%20fill%3D%22url(%23g)%22/%3E%3C/svg%3E";

const router = useRouter();
const route = useRoute();

const username = ref("admin");
const password = ref("admin");
const loading = ref(false);
const error = ref<string | null>(null);

const 错误信息 = computed(() => error.value);

onMounted(async () => {
  await authStore.init();
  if (authStore.isLoggedIn()) {
    await router.replace({ path: "/dashboard" });
  }
});

async function 提交登录(): Promise<void> {
  error.value = null;
  loading.value = true;
  try {
    if (!username.value.trim() || !password.value) {
      error.value = "请输入用户名和密码。";
      return;
    }

    await authStore.login(username.value.trim(), password.value);

    const redirect = typeof route.query.redirect === "string" ? route.query.redirect : null;
    await router.replace(redirect ? { path: redirect } : { path: "/dashboard" });
  } catch (e) {
    if (e instanceof ApiError) {
      error.value = e.message || "登录失败，请检查用户名或密码。";
    } else {
      error.value = "登录失败，请稍后重试。";
    }
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.容器 {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: var(--间距-14);
}

.登录卡片 {
  width: min(420px, 100%);
  padding: var(--间距-18);
}

.标题区 {
  margin-bottom: var(--间距-14);
  text-align: center;
}

.登录-LCP图 {
  width: 240px;
  height: 240px;
  display: block;
  margin: 0 auto var(--间距-12);
}

.登录按钮 {
  width: 100%;
}
</style>

