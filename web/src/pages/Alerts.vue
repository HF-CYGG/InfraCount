<template>
  <AppLayout title="告警" subtitle="列表筛选 + ACK 确认">
    <div class="卡片 面板 筛选区">
      <div class="筛选行">
        <label class="字段">
          <div class="字段标题">设备</div>
          <UiSelect v-model="筛选.uuid">
            <option value="">全部设备</option>
            <option v-for="d in 设备选项" :key="d.uuid" :value="d.uuid">{{ d.label }}</option>
          </UiSelect>
        </label>

        <label class="字段">
          <div class="字段标题">数量上限</div>
          <UiSelect v-model.number="筛选.limit">
            <option :value="50">50</option>
            <option :value="100">100</option>
            <option :value="200">200</option>
            <option :value="500">500</option>
          </UiSelect>
        </label>

        <label class="字段 开关字段">
          <div class="字段标题">仅看未确认</div>
          <div class="行">
            <input id="onlyOpen" v-model="筛选.onlyOpen" type="checkbox" />
            <label for="onlyOpen" class="提示-次要 小字">status = 0</label>
          </div>
        </label>

        <div class="筛选操作">
          <UiButton variant="primary" :loading="loading" @click="刷新">
            {{ loading ? "正在刷新..." : "刷新" }}
          </UiButton>
        </div>
      </div>

      <div v-if="错误信息" class="提示-错误 上间距-10">{{ 错误信息 }}</div>
    </div>

    <div class="卡片 面板">
      <div class="区块头">
        <div>
          <div class="区块标题">告警列表</div>
          <div class="区块说明">
            当前展示 {{ 过滤后列表.length }} 条（{{ 筛选.onlyOpen ? "仅未确认" : "全部" }}）
          </div>
        </div>
      </div>

      <div class="分隔线" />

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
              <th class="列-操作">操作</th>
            </tr>
          </thead>
          <Transition name="ui-fade" mode="out-in" appear>
            <tbody :key="loading ? 'loading' : 'data'">
              <template v-if="loading">
                <tr v-for="i in 8" :key="i">
                  <td><UiSkeleton width="160px" height="12px" /></td>
                  <td><UiSkeleton width="220px" height="12px" /></td>
                  <td><UiSkeleton width="96px" height="12px" /></td>
                  <td><UiSkeleton width="40px" height="12px" /></td>
                  <td><UiSkeleton width="56px" height="12px" /></td>
                  <td><UiSkeleton width="260px" height="12px" /></td>
                  <td><UiSkeleton width="72px" height="12px" /></td>
                </tr>
              </template>
              <template v-else>
                <tr v-for="a in 过滤后列表" :key="String(a.id)">
                  <td class="数字">{{ 格式化时间文本(a.time) }}</td>
                  <td class="数字">{{ a.uuid }}</td>
                  <td>{{ a.type }}</td>
                  <td class="数字">{{ a.level }}</td>
                  <td>
                    <UiTag :tone="Number(a.status) === 1 ? 'success' : 'danger'">
                      {{ Number(a.status) === 1 ? "已确认" : "未确认" }}
                    </UiTag>
                  </td>
                  <td class="可换行">{{ a.info }}</td>
                  <td>
                    <UiButton
                      size="sm"
                      :loading="ackingId === a.id"
                      :disabled="Number(a.status) === 1"
                      @click="确认(a.id)"
                    >
                      {{ ackingId === a.id ? "确认中..." : "ACK" }}
                    </UiButton>
                  </td>
                </tr>
                <tr v-if="!过滤后列表.length">
                  <td colspan="7" class="空态单元格">
                    <UiEmptyState title="暂无告警" description="请尝试调整筛选条件或刷新列表。" />
                  </td>
                </tr>
              </template>
            </tbody>
          </Transition>
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
import UiButton from "@/components/ui/UiButton.vue";
import UiEmptyState from "@/components/ui/UiEmptyState.vue";
import UiSelect from "@/components/ui/UiSelect.vue";
import UiSkeleton from "@/components/ui/UiSkeleton.vue";
import UiTag from "@/components/ui/UiTag.vue";
import { 格式化时间文本 } from "@/utils/datetime";
import { toastStore } from "@/stores/toast";

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
    items = items.filter((a: 告警行) => Number(a.status) !== 1);
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
    toastStore.push("已确认告警", { tone: "success" });
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

