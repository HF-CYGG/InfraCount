<!--
  系统状态页面（示例页面）

  目的：
  - 演示“基础 API Client（withCredentials）”的实际使用方式；
  - 演示如何展示后端返回的 JSON；
  - 该接口在后端要求管理员权限：/api/v1/system/status
    因此非管理员登录时会返回 403。
-->
<template>
  <AppLayout title="系统状态" subtitle="示例：调用后端 /api/v1/system/status 并展示 JSON">
    <div class="卡片 面板">
      <div class="面板标题">接口调用结果</div>
      <div class="面板说明 提示-次要">
        {{ 说明文本 }}
      </div>

      <div class="操作区">
        <button class="按钮 强调" type="button" @click="刷新" :disabled="loading">
          {{ loading ? "正在刷新..." : "刷新" }}
        </button>
      </div>

      <div v-if="错误信息" class="提示-错误">{{ 错误信息 }}</div>

      <pre v-if="data" class="结果">{{ prettyJson }}</pre>
      <div v-else class="提示-次要">暂无数据。</div>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
/**
 * 系统状态页脚本
 *
 * 实现逻辑：
 * 1) 页面加载时自动请求 systemStatus；
 * 2) 点击“刷新”重新请求；
 * 3) 使用 JSON.stringify 做格式化输出；
 * 4) 根据错误码提示更友好的中文信息。
 */

import { computed, onMounted, ref } from "vue";
import AppLayout from "@/layouts/AppLayout.vue";
import { ApiError, api } from "@/api/client";

const loading = ref(false);
const data = ref<Record<string, unknown> | null>(null);
const error = ref<string | null>(null);

const 错误信息 = computed(() => error.value);

const prettyJson = computed(() => {
  return data.value ? JSON.stringify(data.value, null, 2) : "";
});

const 说明文本 = computed(() => {
  if (loading.value) return "正在从后端读取系统状态，请稍候。";
  if (error.value) return "请求失败，可能是权限不足或后端未启动。";
  return "该接口主要用于运维查看：进程信息、数据库连接、任务运行状态与功能开关等。";
});

async function 刷新(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    data.value = await api.systemStatus();
  } catch (e) {
    data.value = null;
    if (e instanceof ApiError) {
      if (e.status === 401) {
        error.value = "未登录或登录已过期，请重新登录。";
      } else if (e.status === 403) {
        error.value = "权限不足：该接口仅管理员可访问。";
      } else {
        error.value = e.message || `请求失败（HTTP ${e.status}）`;
      }
    } else {
      error.value = "请求失败，请检查后端服务是否已启动。";
    }
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void 刷新();
});
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

.操作区 {
  margin-top: 12px;
  display: flex;
  gap: 10px;
  align-items: center;
}

.结果 {
  margin-top: 12px;
  padding: 12px;
  border-radius: 10px;
  border: 1px solid var(--颜色-边框);
  background: rgba(0, 0, 0, 0.22);
  overflow: auto;
  max-height: 60vh;
}
</style>

