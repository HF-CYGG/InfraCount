<template>
  <AppLayout title="看板" subtitle="设备选择 + 汇总卡片 + 日/小时趋势 + 自动刷新">
    <div class="卡片 面板 筛选区">
      <div class="筛选行">
        <label class="字段">
          <div class="字段标题">设备</div>
          <UiSelect v-model="选中设备">
            <option value="">全部设备（汇总）</option>
            <option v-for="d in 设备选项" :key="d.uuid" :value="d.uuid">
              {{ d.label }}
            </option>
          </UiSelect>
        </label>

        <label class="字段">
          <div class="字段标题">小时趋势日期</div>
          <UiInput v-model="小时日期" type="date" />
        </label>

        <label class="字段">
          <div class="字段标题">日趋势范围（起）</div>
          <UiInput v-model="日范围起" type="date" />
        </label>

        <label class="字段">
          <div class="字段标题">日趋势范围（止）</div>
          <UiInput v-model="日范围止" type="date" />
        </label>

        <label class="字段 开关字段">
          <div class="字段标题">自动刷新</div>
          <div class="行">
            <input id="autoRefresh" v-model="自动刷新" type="checkbox" />
            <label for="autoRefresh" class="提示-次要 小字">开启后将按间隔自动刷新</label>
          </div>
        </label>

        <label class="字段">
          <div class="字段标题">刷新间隔</div>
          <UiSelect v-model.number="刷新间隔秒">
            <option :value="5">5 秒</option>
            <option :value="10">10 秒</option>
            <option :value="20">20 秒</option>
            <option :value="30">30 秒</option>
            <option :value="60">60 秒</option>
          </UiSelect>
        </label>

        <div class="筛选操作">
          <UiButton variant="primary" :loading="loading" @click="刷新全部">
            {{ loading ? "正在刷新..." : "手动刷新" }}
          </UiButton>
        </div>
      </div>

      <div class="提示-次要 小字 上间距-10">
        {{ 选中设备 ? `当前设备：${当前设备标签}` : "当前为全部设备汇总" }}
        <span v-if="汇总?.last_time">；最后数据时间：{{ 汇总?.last_time }}</span>
      </div>

      <div v-if="错误信息" class="提示-错误 上间距-10">{{ 错误信息 }}</div>
    </div>

    <div class="三列栅格">
      <div class="卡片 面板">
        <div class="卡片标题">累计进入</div>
        <div class="卡片数字 数字">{{ 汇总?.in ?? 0 }}</div>
      </div>
      <div class="卡片 面板">
        <div class="卡片标题">累计离开</div>
        <div class="卡片数字 数字">{{ 汇总?.out ?? 0 }}</div>
      </div>
      <div class="卡片 面板">
        <div class="卡片标题">设备数量</div>
        <div class="卡片数字 数字">{{ 设备选项.length }}</div>
      </div>
    </div>

    <SimpleLineChart
      title="日趋势（IN/OUT）"
      subtitle="按天汇总（可用于观察近一段时间的整体变化）"
      :labels="日趋势标签"
      :series="日趋势序列"
    />

    <SimpleLineChart
      title="小时趋势（IN/OUT）"
      subtitle="按小时汇总（用于观察当天或最近数据的波动）"
      :labels="小时趋势标签"
      :series="小时趋势序列"
    />
  </AppLayout>
</template>

<script setup lang="ts">
/**
 * 看板页脚本
 *
 * 功能点（对齐 templates/dashboard.html 并提升体验）：
 * - 设备选择：支持“全部设备汇总”与“单设备视图”；
 * - 统计卡片：展示累计 IN/OUT 与最后更新时间；
 * - 趋势图：日趋势（可选范围）+ 小时趋势（可选日期）；
 * - 自动刷新：可开启/关闭，每 10 秒刷新一次。
 *
 * 实现逻辑（整体思路）：
 * 1) 页面初始化时加载设备列表与映射，拼出“可读标签”（name + uuid）；
 * 2) 根据选中设备 uuid 分别请求：
 *    - /api/v1/stats/summary
 *    - /api/v1/stats/daily
 *    - /api/v1/stats/hourly
 * 3) 自动刷新只复用同一套“刷新函数”，避免散落多个 setInterval。
 */

import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import AppLayout from "@/layouts/AppLayout.vue";
import SimpleLineChart, { type 折线序列 } from "@/components/SimpleLineChart.vue";
import UiButton from "@/components/ui/UiButton.vue";
import UiInput from "@/components/ui/UiInput.vue";
import UiSelect from "@/components/ui/UiSelect.vue";
import { api, apiRequest, ApiError } from "@/api/client";
import { 本地日期 } from "@/utils/datetime";

type 设备选项 = { uuid: string; label: string };

const 设备选项 = ref<设备选项[]>([]);
const 选中设备 = ref<string>("");

const 小时日期 = ref<string>(本地日期());
const 日范围止 = ref<string>(本地日期());
const 日范围起 = ref<string>("");

const 自动刷新 = ref<boolean>(false);
const 刷新间隔秒 = ref<number>(10);
const loading = ref<boolean>(false);
const 错误信息 = ref<string>("");

const 汇总 = ref<{ in: number; out: number; last_time: string | null } | null>(null);
const 日趋势 = ref<Array<{ date: string; in: number; out: number }>>([]);
const 小时趋势 = ref<Array<{ hour: string; in: number; out: number }>>([]);

const 当前设备标签 = computed(() => {
  if (!选中设备.value) return "全部设备";
  return 设备选项.value.find((d: { uuid: string; label: string }) => d.uuid === 选中设备.value)?.label || 选中设备.value;
});

const 日趋势标签 = computed(() => 日趋势.value.map((x: any) => x.date));
const 小时趋势标签 = computed(() => 小时趋势.value.map((x: any) => x.hour));

const 日趋势序列 = computed<折线序列[]>(() => [
  { name: "IN", color: "#33d69f", values: 日趋势.value.map((x: any) => Number(x.in || 0)) },
  { name: "OUT", color: "#4ea1ff", values: 日趋势.value.map((x: any) => Number(x.out || 0)) }
]);

const 小时趋势序列 = computed<折线序列[]>(() => [
  { name: "IN", color: "#33d69f", values: 小时趋势.value.map((x: any) => Number(x.in || 0)) },
  { name: "OUT", color: "#4ea1ff", values: 小时趋势.value.map((x: any) => Number(x.out || 0)) }
]);

let 自动刷新定时器: number | null = null;

function 当前自动刷新间隔Ms(): number {
  const base = Math.max(1, Math.trunc(Number(刷新间隔秒.value || 10))) * 1000;
  return document.hidden ? base * 6 : base;
}

async function 加载设备选项(): Promise<void> {
  const [devs, map] = await Promise.all([api.devicesList(), api.deviceMapping()]);
  const mapping = map.mapping || {};

  设备选项.value = (devs || [])
    .map((d) => d.uuid)
    .sort()
    .map((uuid) => {
      const m = mapping[uuid] || {};
      const name = String(m.name || "").trim();
      const label = name ? `${name}（${uuid}）` : uuid;
      return { uuid, label };
    });
}

async function 刷新全部(): Promise<void> {
  loading.value = true;
  错误信息.value = "";
  try {
    const uuid = 选中设备.value || undefined;

    const [summary, daily, hourly] = await Promise.all([
      apiRequest<{ in: number; out: number; last_time: string | null }>({
        method: "GET",
        path: "/api/v1/stats/summary",
        query: { uuid },
        dedupe: "takeLatest",
        cancelKey: "dashboard:summary",
        retry: { count: 1 },
        toastOnError: false
      }),
      apiRequest<Array<{ date: string; in: number; out: number }>>({
        method: "GET",
        path: "/api/v1/stats/daily",
        query: {
          uuid,
          start: 日范围起.value ? `${日范围起.value} 00:00:00` : undefined,
          end: 日范围止.value ? `${日范围止.value} 23:59:59` : undefined
        },
        dedupe: "takeLatest",
        cancelKey: "dashboard:daily",
        retry: { count: 1 },
        toastOnError: false
      }),
      apiRequest<Array<{ hour: string; in: number; out: number }>>({
        method: "GET",
        path: "/api/v1/stats/hourly",
        query: {
          uuid,
          date: 小时日期.value ? `${小时日期.value} 00:00:00` : undefined
        },
        dedupe: "takeLatest",
        cancelKey: "dashboard:hourly",
        retry: { count: 1 },
        toastOnError: false
      })
    ]);

    汇总.value = summary;
    日趋势.value = daily || [];
    小时趋势.value = hourly || [];
  } catch (e) {
    if (e instanceof ApiError) {
      错误信息.value = e.message;
    } else {
      错误信息.value = "刷新失败：未知错误";
    }
  } finally {
    loading.value = false;
  }
}

function 启动自动刷新(): void {
  停止自动刷新();
  自动刷新定时器 = window.setTimeout(() => {
    void (async () => {
      if (!自动刷新.value) return;
      if (!loading.value) await 刷新全部();
      启动自动刷新();
    })();
  }, 当前自动刷新间隔Ms());
}

function 停止自动刷新(): void {
  if (自动刷新定时器 === null) return;
  window.clearTimeout(自动刷新定时器);
  自动刷新定时器 = null;
}

const onVisibilityChange = () => {
  if (自动刷新.value) 启动自动刷新();
};

watch(
  [自动刷新, 刷新间隔秒],
  ([enabled]: [boolean, any]) => {
    if (enabled) 启动自动刷新();
    else 停止自动刷新();
  },
  { immediate: true }
);

watch([选中设备, 小时日期, 日范围起, 日范围止], () => {
  void 刷新全部();
});

onMounted(async () => {
  if (!日范围起.value) {
    const d = new Date();
    d.setDate(d.getDate() - 6);
    日范围起.value = 本地日期(d);
  }
  document.addEventListener("visibilitychange", onVisibilityChange);
  await 加载设备选项();
  await 刷新全部();
});

onBeforeUnmount(() => {
  document.removeEventListener("visibilitychange", onVisibilityChange);
  停止自动刷新();
});
</script>

