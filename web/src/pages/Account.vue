<template>
  <AppLayout title="账户" subtitle="修改密码">
    <div class="卡片 面板">
      <div class="标题">当前用户</div>
      <div class="提示-次要 小字" style="margin-top: 6px">
        用户名：{{ 当前用户?.username || "-" }}；角色：{{ 当前用户?.role || "-" }}
      </div>
    </div>

    <div class="卡片 面板">
      <div class="标题">修改密码</div>
      <div class="提示-次要 小字" style="margin-top: 6px">密码会立即生效。建议使用强密码并妥善保管。</div>

      <div class="分隔线" />

      <form class="表单" @submit.prevent="提交">
        <label class="字段">
          <div class="字段标题">新密码</div>
          <input v-model="新密码" class="输入框" type="password" autocomplete="new-password" placeholder="请输入新密码" />
        </label>

        <label class="字段">
          <div class="字段标题">确认新密码</div>
          <input
            v-model="确认密码"
            class="输入框"
            type="password"
            autocomplete="new-password"
            placeholder="请再次输入新密码"
          />
        </label>

        <div v-if="提示信息" class="提示-次要 小字">{{ 提示信息 }}</div>
        <div v-if="错误信息" class="提示-错误 小字">{{ 错误信息 }}</div>

        <div class="行" style="justify-content: flex-end; margin-top: 12px">
          <button class="按钮 强调" type="submit" :disabled="loading">
            {{ loading ? "正在提交..." : "确认修改" }}
          </button>
        </div>
      </form>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
/**
 * 账户页脚本
 *
 * 功能点：
 * - 展示当前登录用户信息；
 * - 提供修改密码表单（POST /api/v1/auth/password）。
 *
 * 说明：
 * - 后端鉴权基于 HttpOnly Cookie（session_token），前端只需携带 Cookie 即可；
 * - 修改密码接口仅需要 new_password，不要求旧密码（与 templates/account.html 保持一致）。
 */

import { computed, ref } from "vue";
import AppLayout from "@/layouts/AppLayout.vue";
import { authStore } from "@/stores/auth";
import { api, ApiError } from "@/api/client";

const 当前用户 = computed(() => authStore.state.user);

const 新密码 = ref<string>("");
const 确认密码 = ref<string>("");
const loading = ref<boolean>(false);
const 错误信息 = ref<string>("");
const 提示信息 = ref<string>("");

async function 提交(): Promise<void> {
  错误信息.value = "";
  提示信息.value = "";

  if (!新密码.value.trim()) {
    错误信息.value = "请输入新密码。";
    return;
  }
  if (新密码.value !== 确认密码.value) {
    错误信息.value = "两次输入的密码不一致。";
    return;
  }

  loading.value = true;
  try {
    await api.authChangePassword(新密码.value);
    新密码.value = "";
    确认密码.value = "";
    提示信息.value = "密码已修改成功。";
  } catch (e) {
    错误信息.value = e instanceof ApiError ? e.message : "修改失败：未知错误";
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.标题 {
  font-size: 16px;
  font-weight: 900;
}

.表单 {
  display: grid;
  gap: 12px;
  margin-top: 12px;
}

.字段 {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 260px;
}

.字段标题 {
  font-size: 12px;
  color: var(--颜色-次要文本);
}
</style>

