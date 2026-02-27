<template>
  <AppLayout title="告警" subtitle="列表筛选 + ACK 确认">
    <div class="卡片 面板">
      <div class="行">
        <label class="字段">
          <div class="字段标题">设备</div>
          <select v-model="筛选.uuid" class="输入框">
            <option value="">全部设备</option>
            <option v-for="d in 设备选项" :key="d.uuid" :value="d.uuid">{{ d.label }}</option>
          </select>
        </label>

        <label class="字段">
          <div class="字段标题">数量上限</div>
          <select v-model.number="筛选.limit" class="输入框">
            <option :value="50">50</option>
            <option :value="100">100</option>
            <option :value="200">200</option>
            <option :value="500">500</option>
          </select>
        </label>

        <label class="字段">
          <div class="字段标题">仅看未确认</div>
          <div class="行">
            <input id="onlyOpen" v-model="筛选.onlyOpen" type="checkbox" />
            <label for="onlyOpen" class="提示-次要 小字">status = 0</label>
          </div>
        </label>

        <button class="按钮 强调" type="button" :disabled="loading" @click="刷新">
          {{ loading ? "正在刷新..." : "刷新" }}
        </button>
      </div>

      <div v-if="错误信息" class="提示-错误" style="margin-top: 10px">{{ 错误信息 }}</div>
    </div>

    <div class="卡片 面板">
      <div class="表格容器">
        <table class="表格">
          <thead>
            <tr>
              <th>时间</th>
              <th>UUID</th>
              <th>类型</th>
              <th>等级</th>
              <th>状态</th>
              <th>信息</th>
              <th style="width: 120px">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="a in 过滤后列表" :key="String(a.id)">
              <td class="数字">{{ 格式化时间文本(a.time) }}</td>
              <td class="数字">{{ a.uuid }}</td>
              <td>{{ a.type }}</td>
              <td class="数字">{{ a.level }}</td>
              <td>
                <span class="徽章" :class="Number(a.status) === 1 ? '成功' : '危险'">
                  {{ Number(a.status) === 1 ? "已确认" : "未确认" }}
                </span>
              </td>
              <td style="white-space: normal">{{ a.info }}</td>
              <td>
                <button class="按钮" type="button" :disabled="Number(a.status) === 1 || ackingId === a.id" @click="确认(a.id)">
                  {{ ackingId === a.id ? "确认中..." : "ACK" }}
                </button>
              </td>
            </tr>
            <tr v-if="!过滤后列表.length">
              <td colspan="7" class="提示-次要">暂无数据</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
/**
 * 告警页脚本
 *
 * 功能点：
 * - 列表：展示最近告警（时间/类型/等级/状态/信息）；
 * - 筛选：按设备、是否仅未确认、数量上限；
 * - ACK：调用 /api/v1/alerts/{id}/ack 将 status 置为 1。
 *
 * 说明：
 * - 后端 list_alerts 当前只支持 uuid 与 limit，未内置 status 筛选；
 * - 因此“仅看未确认”在前端做二次过滤（不影响后端兼容性）。
 */

import { computed, onMounted, reactive, ref } from "vue";
import AppLayout from "@/layouts/AppLayout.vue";
import { api, ApiError } from "@/api/client";
import { 格式化时间文本 } from "@/utils/datetime";

type 告警行 = { id: number; uuid: string; type: string; level: number; status: number; info: string; time: string };
type 设备选项 = { uuid: string; label: string };

const loading = ref<boolean>(false);
const 错误信息 = ref<string>("");
const ackingId = ref<number | null>(null);

const 设备选项 = ref<设备选项[]>([]);
const 列表 = ref<告警行[]>([]);

const 筛选 = reactive<{ uuid: string; limit: number; onlyOpen: boolean }>({ uuid: "", limit: 100, onlyOpen: true });

const 过滤后列表 = computed(() => {
  let items = 列表.value;
  if (筛选.onlyOpen) {
    items = items.filter((a) => Number(a.status) !== 1);
  }
  return items;
});

async function 加载设备选项(): Promise<void> {
  const [devs, map] = await Promise.all([api.devicesList(), api.deviceMapping()]);
  const mapping = map.mapping || {};
  设备选项.value = (devs || [])
    .map((d) => d.uuid)
    .sort()
    .map((uuid) => {
      const m = mapping[uuid] || {};
      const name = String(m.name || "").trim();
      return { uuid, label: name ? `${name}（${uuid}）` : uuid };
    });
}

async function 刷新(): Promise<void> {
  loading.value = true;
  错误信息.value = "";
  try {
    const items = await api.alertsList({ uuid: 筛选.uuid || undefined, limit: 筛选.limit });
    列表.value = (items || []) as any;
  } catch (e) {
    错误信息.value = e instanceof ApiError ? e.message : "刷新失败：未知错误";
  } finally {
    loading.value = false;
  }
}

async function 确认(id: number): Promise<void> {
  ackingId.value = id;
  错误信息.value = "";
  try {
    await api.alertsAck(id);
    await 刷新();
  } catch (e) {
    错误信息.value = e instanceof ApiError ? e.message : "确认失败：未知错误";
  } finally {
    ackingId.value = null;
  }
}

onMounted(async () => {
  await 加载设备选项();
  await 刷新();
});
</script>

<style scoped>
.字段 {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 190px;
}

.字段标题 {
  font-size: 12px;
  color: var(--颜色-次要文本);
}
</style>

