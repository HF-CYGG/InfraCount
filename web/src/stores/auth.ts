/**
 * 轻量级登录态 Store（不引入 Pinia）
 *
 * 设计目标：
 * - 只解决“是否登录/当前用户是谁/如何登录登出”的最小问题；
 * - 由后端通过 Cookie（session_token）维持会话；
 * - 前端在需要时调用 /api/v1/auth/me 来恢复登录态。
 *
 * 为什么不用 LocalStorage 存 token：
 * - 当前后端登录态基于 HttpOnly Cookie（更安全，JS 读不到）；
 * - 前端只需携带 Cookie 请求即可（在 apiRequest 内统一 credentials: "include"）。
 */

import { reactive } from "vue";
import { ApiError, api } from "@/api/client";

export type 当前用户 = {
  id: number;
  username: string;
  role: string;
};

type AuthState = {
  /**
   * initFinished 用于标记“是否已进行过一次登录态自检”
   * - 路由守卫在第一次判断时可触发 init()；
   * - 避免每次路由跳转都重复请求 /auth/me。
   */
  initFinished: boolean;
  user: 当前用户 | null;
  lastError: string | null;
};

const state = reactive<AuthState>({
  initFinished: false,
  user: null,
  lastError: null
});

async function refreshMeSilently(): Promise<void> {
  try {
    const res = await api.authMe();
    state.user = res.user;
    state.lastError = null;
  } catch (e) {
    /**
     * /auth/me 失败是“正常情况”（例如未登录/会话过期），因此这里不做 console.error
     * - 只把 user 置空，交由页面或路由守卫决定下一步（例如跳到 /login）。
     */
    state.user = null;
    state.lastError = e instanceof ApiError ? e.message : "读取登录态失败";
  }
}

export const authStore = {
  state,

  /**
   * 初始化：尝试恢复登录态
   *
   * 实现逻辑：
   * - 只做一次（通过 initFinished 标识），避免无意义的重复请求；
   * - 若后端 Cookie 仍有效，则 user 会被填充；
   * - 若无效/未登录，则 user 保持 null。
   */
  async init(): Promise<void> {
    if (state.initFinished) return;
    state.initFinished = true;
    await refreshMeSilently();
  },

  /**
   * 登录
   *
   * 实现逻辑：
   * 1) 调用后端 /auth/login；
   * 2) 后端写入 session_token Cookie（HttpOnly）；
   * 3) 前端将返回的 user 写入 state，供界面显示；
   */
  async login(username: string, password: string): Promise<void> {
    state.lastError = null;
    const res = await api.authLogin(username, password);
    state.user = res.user;
  },

  /**
   * 退出登录
   *
   * 实现逻辑：
   * 1) 调用后端 /auth/logout 清理会话；
   * 2) 清空前端 user；
   */
  async logout(): Promise<void> {
    try {
      await api.authLogout();
    } finally {
      state.user = null;
    }
  },

  /**
   * 主动刷新登录态（用于路由守卫/关键页面）
   */
  async refreshMe(): Promise<void> {
    await refreshMeSilently();
  },

  isLoggedIn(): boolean {
    return !!state.user;
  }
};

