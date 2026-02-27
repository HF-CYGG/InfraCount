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
        <div class="标题">InfraCount 管理后台</div>
        <div class="副标题 提示-次要">请先登录以继续</div>
      </div>

      <form class="表单" @submit.prevent="提交登录">
        <label class="字段">
          <div class="字段标题">用户名</div>
          <input v-model.trim="username" class="输入框" autocomplete="username" placeholder="请输入用户名" />
        </label>

        <label class="字段">
          <div class="字段标题">密码</div>
          <input
            v-model="password"
            class="输入框"
            type="password"
            autocomplete="current-password"
            placeholder="请输入密码"
          />
        </label>

        <div v-if="错误信息" class="提示-错误">{{ 错误信息 }}</div>
        <div class="提示-次要">默认账号：admin / admin（首次启动自动创建）</div>

        <button class="按钮 强调" type="submit" :disabled="loading">
          {{ loading ? "正在登录..." : "登录" }}
        </button>
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
  padding: 14px;
}

.登录卡片 {
  width: min(420px, 100%);
  padding: 18px;
}

.标题区 {
  margin-bottom: 14px;
}

.标题 {
  font-size: 20px;
  font-weight: 900;
  letter-spacing: 0.5px;
}

.副标题 {
  margin-top: 8px;
  font-size: 13px;
}

.表单 {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.字段 {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.字段标题 {
  font-size: 13px;
  color: var(--颜色-次要文本);
}

.按钮 {
  width: 100%;
}

.按钮:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}
</style>

