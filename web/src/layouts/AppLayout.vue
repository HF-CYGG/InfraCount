<!--
  应用主布局

  布局结构：
  - 左侧：导航栏（固定宽度）
  - 右侧：内容区（顶部标题栏 + 页面内容）

  设计目的：
  - 所有业务页面共用一致的框架，避免每个页面重复写导航与退出按钮；
  - 页面只需要关心自己的“内容区域”即可。
-->
<template>
  <div class="布局">
    <aside class="侧栏 卡片">
      <div class="侧栏标题">
        <div class="应用名">InfraCount</div>
        <div class="应用副标题">管理后台（SPA）</div>
      </div>

      <nav class="导航">
        <RouterLink class="导航项" to="/dashboard">看板</RouterLink>
        <RouterLink class="导航项" to="/devices">设备</RouterLink>
        <RouterLink class="导航项" to="/history">历史</RouterLink>
        <RouterLink class="导航项" to="/activity">活动</RouterLink>
        <RouterLink class="导航项" to="/alerts">告警</RouterLink>
        <RouterLink class="导航项" to="/locations">场地</RouterLink>
        <RouterLink class="导航项" to="/account">账户</RouterLink>
        <RouterLink v-if="是管理员" class="导航项" to="/admin">管理</RouterLink>
        <RouterLink v-if="是管理员" class="导航项" to="/log-import">日志导入</RouterLink>
        <RouterLink v-if="是管理员" class="导航项" to="/db-merge">数据库合并导入</RouterLink>
        <RouterLink class="导航项" to="/system-status">系统状态</RouterLink>
        <a class="导航项" href="/legacy/" target="_blank" rel="noreferrer">旧版页面（/legacy）</a>
      </nav>

      <div class="侧栏底部">
        <div class="用户信息">
          <div class="用户名称">{{ 用户名 }}</div>
          <div class="用户角色 提示-次要">角色：{{ 角色 }}</div>
        </div>
        <button class="按钮" type="button" @click="退出登录">退出登录</button>
      </div>
    </aside>

    <main class="内容区">
      <header class="顶部栏 卡片">
        <div class="页面标题">
          <div class="标题">{{ title }}</div>
          <div v-if="subtitle" class="副标题 提示-次要">{{ subtitle }}</div>
        </div>
      </header>

      <section class="页面内容">
        <slot />
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
/**
 * 主布局脚本
 *
 * 关键逻辑：
 * - 读取 authStore 里的用户信息显示在侧栏；
 * - 点击“退出登录”时：
 *   1) 调用后端 /api/v1/auth/logout 清理会话；
 *   2) 跳转到 /login；
 */

import { computed } from "vue";
import { useRouter } from "vue-router";
import { authStore } from "@/stores/auth";

const props = defineProps<{
  title: string;
  subtitle?: string;
}>();

const router = useRouter();

const 用户名 = computed(() => authStore.state.user?.username || "未登录");
const 角色 = computed(() => authStore.state.user?.role || "未知");
const 是管理员 = computed(() => authStore.state.user?.role === "admin");

async function 退出登录(): Promise<void> {
  await authStore.logout();
  await router.push({ path: "/login" });
}
</script>

<style scoped>
.布局 {
  display: grid;
  grid-template-columns: 260px 1fr;
  gap: 14px;
  padding: 14px;
  min-height: 100vh;
}

.侧栏 {
  padding: 14px;
  position: sticky;
  top: 14px;
  height: calc(100vh - 28px);
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.侧栏标题 {
  padding: 12px 12px 4px 12px;
}

.应用名 {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.5px;
}

.应用副标题 {
  margin-top: 6px;
  font-size: 12px;
  color: var(--颜色-次要文本);
}

.导航 {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.导航项 {
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid transparent;
  color: var(--颜色-次要文本);
}

.导航项:hover {
  background: rgba(255, 255, 255, 0.06);
  color: var(--颜色-文本);
}

.导航项.router-link-active {
  background: rgba(78, 161, 255, 0.14);
  border-color: rgba(78, 161, 255, 0.35);
  color: var(--颜色-文本);
}

.侧栏底部 {
  margin-top: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.用户信息 {
  padding: 10px 12px;
  border: 1px solid var(--颜色-边框);
  border-radius: 10px;
  background: rgba(0, 0, 0, 0.14);
}

.用户名称 {
  font-weight: 700;
}

.用户角色 {
  margin-top: 6px;
  font-size: 12px;
}

.内容区 {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
}

.顶部栏 {
  padding: 14px;
}

.页面标题 {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.标题 {
  font-size: 18px;
  font-weight: 700;
}

.副标题 {
  font-size: 12px;
}

.页面内容 {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

@media (max-width: 920px) {
  .布局 {
    grid-template-columns: 1fr;
  }
  .侧栏 {
    position: relative;
    height: auto;
  }
}
</style>

