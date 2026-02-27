<template>
  <AppLayout title="管理" subtitle="用户管理（仅管理员）">
    <div v-if="!是管理员" class="卡片 面板">
      <div class="提示-错误">无权限访问：该页面仅管理员可用。</div>
      <div class="提示-次要 小字" style="margin-top: 8px">如需开通管理员权限，请使用管理员账号登录并调整用户角色。</div>
    </div>

    <template v-else>
      <div class="卡片 面板">
        <div class="行" style="justify-content: space-between">
          <div>
            <div class="标题">用户列表</div>
            <div class="提示-次要 小字" style="margin-top: 6px">仅管理员可查看/创建/修改/删除用户。</div>
          </div>
          <div class="行">
            <button class="按钮" type="button" :disabled="loading" @click="刷新">
              {{ loading ? "正在加载..." : "刷新" }}
            </button>
            <button class="按钮 强调" type="button" @click="打开新增">新增用户</button>
          </div>
        </div>

        <div v-if="错误信息" class="提示-错误" style="margin-top: 10px">{{ 错误信息 }}</div>
        <div v-if="提示信息" class="提示-次要 小字" style="margin-top: 10px">{{ 提示信息 }}</div>
      </div>

      <div class="卡片 面板">
        <div class="表格容器">
          <table class="表格">
            <thead>
              <tr>
                <th>ID</th>
                <th>用户名</th>
                <th>角色</th>
                <th style="width: 220px">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="u in users" :key="u.id">
                <td class="数字">{{ u.id }}</td>
                <td>{{ u.username }}</td>
                <td>
                  <span class="徽章" :class="u.role === 'admin' ? '强调' : ''">{{ u.role }}</span>
                </td>
                <td class="行">
                  <button class="按钮" type="button" @click="打开编辑(u)">编辑</button>
                  <button class="按钮" type="button" :disabled="删除中 === u.id" @click="删除(u)">
                    {{ 删除中 === u.id ? "删除中..." : "删除" }}
                  </button>
                </td>
              </tr>
              <tr v-if="!users.length">
                <td colspan="4" class="提示-次要">暂无数据</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div v-if="弹窗显示" class="遮罩" @click.self="关闭弹窗">
        <div class="弹窗 卡片">
          <div class="弹窗标题">{{ 编辑中 ? "编辑用户" : "新增用户" }}</div>
          <div class="提示-次要 小字" style="margin-top: 6px">
            {{ 编辑中 ? "留空密码表示不修改密码。" : "请设置初始密码，用户可在“账户”页自行修改。" }}
          </div>

          <div class="分隔线" />

          <label class="字段">
            <div class="字段标题">用户名</div>
            <input v-model.trim="表单.username" class="输入框" placeholder="例如：user01" />
          </label>

          <label class="字段">
            <div class="字段标题">密码</div>
            <input v-model="表单.password" class="输入框" type="password" placeholder="请输入密码（编辑时可留空）" />
          </label>

          <label class="字段">
            <div class="字段标题">角色</div>
            <select v-model="表单.role" class="输入框">
              <option value="user">user</option>
              <option value="admin">admin</option>
            </select>
          </label>

          <div v-if="弹窗错误" class="提示-错误 小字" style="margin-top: 10px">{{ 弹窗错误 }}</div>

          <div class="行" style="justify-content: flex-end; margin-top: 14px">
            <button class="按钮" type="button" @click="关闭弹窗">取消</button>
            <button class="按钮 强调" type="button" :disabled="保存中" @click="保存">
              {{ 保存中 ? "保存中..." : "保存" }}
            </button>
          </div>
        </div>
      </div>
    </template>
  </AppLayout>
</template>

<script setup lang="ts">
/**
 * 管理页脚本：用户管理（仅管理员）
 *
 * 功能点：
 * - 列表：GET /api/v1/users
 * - 新增：POST /api/v1/users
 * - 修改：PUT /api/v1/users/{id}
 * - 删除：DELETE /api/v1/users/{id}
 *
 * 权限策略：
 * - 后端已强制 admin 校验；
 * - 前端额外做“入口隐藏 + 页面内提示”，提升体验。
 */

import { computed, onMounted, reactive, ref } from "vue";
import AppLayout from "@/layouts/AppLayout.vue";
import { authStore } from "@/stores/auth";
import { api, ApiError } from "@/api/client";

type 用户 = { id: number; username: string; role: string };

const 是管理员 = computed(() => authStore.state.user?.role === "admin");

const loading = ref<boolean>(false);
const 保存中 = ref<boolean>(false);
const 删除中 = ref<number | null>(null);
const 错误信息 = ref<string>("");
const 提示信息 = ref<string>("");

const users = ref<用户[]>([]);

const 弹窗显示 = ref<boolean>(false);
const 编辑中 = ref<用户 | null>(null);
const 弹窗错误 = ref<string>("");

const 表单 = reactive<{ username: string; password: string; role: string }>({ username: "", password: "", role: "user" });

async function 刷新(): Promise<void> {
  if (!是管理员.value) return;
  loading.value = true;
  错误信息.value = "";
  提示信息.value = "";
  try {
    const res = await api.usersList();
    users.value = res.users || [];
  } catch (e) {
    错误信息.value = e instanceof ApiError ? e.message : "加载失败：未知错误";
  } finally {
    loading.value = false;
  }
}

function 打开新增(): void {
  编辑中.value = null;
  表单.username = "";
  表单.password = "";
  表单.role = "user";
  弹窗错误.value = "";
  弹窗显示.value = true;
}

function 打开编辑(u: 用户): void {
  编辑中.value = u;
  表单.username = u.username;
  表单.password = "";
  表单.role = u.role;
  弹窗错误.value = "";
  弹窗显示.value = true;
}

function 关闭弹窗(): void {
  弹窗显示.value = false;
}

async function 保存(): Promise<void> {
  保存中.value = true;
  弹窗错误.value = "";
  try {
    const username = 表单.username.trim();
    if (!username) {
      弹窗错误.value = "用户名不能为空。";
      return;
    }

    if (编辑中.value) {
      await api.userUpdate(编辑中.value.id, {
        username,
        role: 表单.role,
        ...(表单.password ? { password: 表单.password } : {})
      });
      提示信息.value = "更新成功。";
    } else {
      if (!表单.password) {
        弹窗错误.value = "新增用户必须设置初始密码。";
        return;
      }
      await api.userCreate({ username, password: 表单.password, role: 表单.role });
      提示信息.value = "创建成功。";
    }

    关闭弹窗();
    await 刷新();
  } catch (e) {
    弹窗错误.value = e instanceof ApiError ? e.message : "保存失败：未知错误";
  } finally {
    保存中.value = false;
  }
}

async function 删除(u: 用户): Promise<void> {
  删除中.value = u.id;
  错误信息.value = "";
  提示信息.value = "";
  try {
    await api.userDelete(u.id);
    提示信息.value = "删除成功。";
    await 刷新();
  } catch (e) {
    错误信息.value = e instanceof ApiError ? e.message : "删除失败：未知错误";
  } finally {
    删除中.value = null;
  }
}

onMounted(() => {
  void 刷新();
});
</script>

<style scoped>
.标题 {
  font-size: 16px;
  font-weight: 900;
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

.遮罩 {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  display: grid;
  place-items: center;
  padding: 14px;
  z-index: 50;
}

.弹窗 {
  width: min(520px, 100%);
  padding: 14px;
}

.弹窗标题 {
  font-size: 16px;
  font-weight: 900;
}
</style>

