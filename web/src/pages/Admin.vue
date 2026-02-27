<template>
  <AppLayout title="管理" subtitle="用户管理（仅管理员）">
    <div v-if="!是管理员" class="卡片 面板">
      <div class="提示-错误">无权限访问：该页面仅管理员可用。</div>
      <div class="提示-次要 小字 上间距-8">如需开通管理员权限，请使用管理员账号登录并调整用户角色。</div>
    </div>

    <template v-else>
      <div class="卡片 面板">
        <div class="区块头">
          <div>
            <div class="区块标题">用户列表</div>
            <div class="区块说明">仅管理员可查看/创建/修改/删除用户。</div>
          </div>
          <div class="行">
            <UiButton size="sm" :loading="loading" @click="刷新">{{ loading ? "正在加载..." : "刷新" }}</UiButton>
            <UiButton size="sm" variant="primary" @click="打开新增">新增用户</UiButton>
          </div>
        </div>

        <div v-if="错误信息" class="提示-错误 上间距-10">{{ 错误信息 }}</div>
        <div v-if="提示信息" class="提示-次要 小字 上间距-10">{{ 提示信息 }}</div>
      </div>

      <div class="卡片 面板">
        <div class="表格容器">
          <table class="表格">
            <thead>
              <tr>
                <th>ID</th>
                <th>用户名</th>
                <th>角色</th>
                <th class="列-操作宽">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="u in users" :key="u.id">
                <td class="数字">{{ u.id }}</td>
                <td>{{ u.username }}</td>
                <td>
                  <UiTag :tone="u.role === 'admin' ? 'primary' : 'default'">{{ u.role }}</UiTag>
                </td>
                <td class="行">
                  <UiButton size="sm" @click="打开编辑(u)">编辑</UiButton>
                  <UiButton size="sm" variant="danger" :loading="删除中 === u.id" @click="打开删除(u)">
                    {{ 删除中 === u.id ? "删除中..." : "删除" }}
                  </UiButton>
                </td>
              </tr>
              <tr v-if="!users.length">
                <td colspan="4" class="空态单元格">
                  <UiEmptyState title="暂无用户" description="你可以点击“新增用户”创建一个新账号。" />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <UiDialog
        v-model:open="弹窗显示"
        :title="编辑中 ? '编辑用户' : '新增用户'"
        confirm-text="保存"
        cancel-text="取消"
        :loading="保存中"
        confirm-variant="primary"
        @confirm="保存"
        @cancel="关闭弹窗"
      >
        <div class="提示-次要 小字">
          {{ 编辑中 ? "留空密码表示不修改密码。" : "请设置初始密码，用户可在“账户”页自行修改。" }}
        </div>

        <div class="分隔线" />

        <label class="字段 宽字段">
          <div class="字段标题">用户名</div>
          <UiInput v-model.trim="表单.username" placeholder="例如：user01" />
        </label>

        <label class="字段 宽字段">
          <div class="字段标题">密码</div>
          <UiInput v-model="表单.password" type="password" placeholder="请输入密码（编辑时可留空）" />
        </label>

        <label class="字段 宽字段">
          <div class="字段标题">角色</div>
          <UiSelect v-model="表单.role">
            <option value="user">user</option>
            <option value="admin">admin</option>
          </UiSelect>
        </label>

        <div v-if="弹窗错误" class="提示-错误 小字 上间距-10">{{ 弹窗错误 }}</div>
      </UiDialog>

      <UiDialog
        v-model:open="删除弹窗显示"
        title="确认删除用户"
        confirm-text="删除"
        cancel-text="取消"
        :loading="删除中 === 待删除用户?.id"
        confirm-variant="danger"
        @confirm="确认删除"
        @cancel="关闭删除"
      >
        <div>将删除用户：{{ 待删除用户?.username }}</div>
        <div class="提示-次要 小字 上间距-6">删除后不可恢复。</div>
      </UiDialog>
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
import UiButton from "@/components/ui/UiButton.vue";
import UiDialog from "@/components/ui/UiDialog.vue";
import UiEmptyState from "@/components/ui/UiEmptyState.vue";
import UiInput from "@/components/ui/UiInput.vue";
import UiSelect from "@/components/ui/UiSelect.vue";
import UiTag from "@/components/ui/UiTag.vue";
import { toastStore } from "@/stores/toast";

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
const 删除弹窗显示 = ref<boolean>(false);
const 待删除用户 = ref<用户 | null>(null);

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

function 打开删除(u: 用户): void {
  待删除用户.value = u;
  删除弹窗显示.value = true;
}

function 关闭删除(): void {
  删除弹窗显示.value = false;
  待删除用户.value = null;
}

async function 确认删除(): Promise<void> {
  if (!待删除用户.value) return;
  await 删除(待删除用户.value);
  关闭删除();
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
      toastStore.push("用户已更新", { tone: "success" });
    } else {
      if (!表单.password) {
        弹窗错误.value = "新增用户必须设置初始密码。";
        return;
      }
      await api.userCreate({ username, password: 表单.password, role: 表单.role });
      提示信息.value = "创建成功。";
      toastStore.push("用户已创建", { tone: "success" });
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
    toastStore.push("用户已删除", { tone: "success" });
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

