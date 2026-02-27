/**
 * 前端路由配置（Vue Router）
 *
 * 页面规划（均为占位骨架，可逐步补齐业务能力）：
 * - /login            登录页（公开）
 * - /dashboard        看板
 * - /devices          设备
 * - /history          历史
 * - /activity         活动
 * - /alerts           告警
 * - /locations        场地（标准库/纠错）
 * - /account          账户
 * - /admin            管理（占位）
 * - /log-import       日志导入（占位）
 * - /system-status    系统状态（示例调用后端接口）
 *
 * 鉴权策略：
 * - 绝大多数页面需要登录（requiresAuth: true）；
 * - 路由守卫会在首次进入时尝试调用 authStore.init() 恢复登录态；
 * - 如果仍未登录，则跳转到 /login，并带上 redirect 参数用于登录后返回。
 */

import { createRouter, createWebHistory, type RouteRecordRaw, type RouteLocationNormalized } from "vue-router";
import { authStore } from "@/stores/auth";

const routes: RouteRecordRaw[] = [
  {
    path: "/",
    redirect: "/dashboard"
  },
  {
    path: "/login",
    name: "登录",
    component: () => import("@/pages/Login.vue"),
    meta: { requiresAuth: false }
  },
  {
    path: "/dashboard",
    name: "看板",
    component: () => import("@/pages/Dashboard.vue"),
    meta: { requiresAuth: true }
  },
  {
    path: "/devices",
    name: "设备",
    component: () => import("@/pages/Devices.vue"),
    meta: { requiresAuth: true }
  },
  {
    path: "/history",
    name: "历史",
    component: () => import("@/pages/History.vue"),
    meta: { requiresAuth: true }
  },
  {
    path: "/activity",
    name: "活动",
    component: () => import("@/pages/Activity.vue"),
    meta: { requiresAuth: true }
  },
  {
    path: "/alerts",
    name: "告警",
    component: () => import("@/pages/Alerts.vue"),
    meta: { requiresAuth: true }
  },
  {
    path: "/locations",
    name: "场地",
    component: () => import("@/pages/Locations.vue"),
    meta: { requiresAuth: true }
  },
  {
    path: "/account",
    name: "账户",
    component: () => import("@/pages/Account.vue"),
    meta: { requiresAuth: true }
  },
  {
    path: "/admin",
    name: "管理",
    component: () => import("@/pages/Admin.vue"),
    meta: { requiresAuth: true }
  },
  {
    path: "/log-import",
    name: "日志导入",
    component: () => import("@/pages/LogImport.vue"),
    meta: { requiresAuth: true }
  },
  {
    path: "/db-merge",
    name: "数据库合并导入",
    component: () => import("@/pages/DbMergeImport.vue"),
    meta: { requiresAuth: true }
  },
  {
    path: "/system-status",
    name: "系统状态",
    component: () => import("@/pages/SystemStatus.vue"),
    meta: { requiresAuth: true }
  },
  {
    path: "/:pathMatch(.*)*",
    name: "未找到",
    component: () => import("@/pages/NotFound.vue"),
    meta: { requiresAuth: false }
  }
];

export const router = createRouter({
  /**
   * 这里使用 createWebHistory，并使用 import.meta.env.BASE_URL 作为 base：
   * - 生产托管时 Vite base 配置为 /spa/，因此 BASE_URL 会是 /spa/；
   * - 开发态也同样遵循该 base，确保路由与资源路径一致；
   * - 这样路由地址就是 /spa/dashboard、/spa/devices 等（符合后端挂载路径）。
   */
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
});

router.beforeEach(async (to: RouteLocationNormalized) => {
  /**
   * 第一次路由进入时，尝试恢复登录态：
   * - 如果用户已有 Cookie，会直接拿到当前用户；
   * - 如果没有 Cookie 或已过期，user 仍为 null。
   */
  await authStore.init();

  const requiresAuth = Boolean(to.meta.requiresAuth);
  if (!requiresAuth) return true;

  if (authStore.isLoggedIn()) return true;

  /**
   * 未登录访问受保护页面：
   * - 跳到 /login
   * - 把原目标地址通过 redirect 参数带上，登录成功后跳回
   */
  return {
    path: "/login",
    query: { redirect: to.fullPath }
  };
});

