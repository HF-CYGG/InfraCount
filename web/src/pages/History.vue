<template>
  <AppLayout title="历史" subtitle="筛选 + 分页 + 排序 + CSV 导出">
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
          <div class="字段标题">开始日期</div>
          <input v-model="筛选.start" class="输入框" type="date" />
        </label>

        <label class="字段">
          <div class="字段标题">结束日期</div>
          <input v-model="筛选.end" class="输入框" type="date" />
        </label>

        <label class="字段">
          <div class="字段标题">告警状态</div>
          <select v-model="筛选.warn" class="输入框">
            <option value="">全部</option>
            <option value="0">正常（0）</option>
            <option value="1">告警（1）</option>
          </select>
        </label>

        <label class="字段">
          <div class="字段标题">记录类型</div>
          <select v-model="筛选.rec_type" class="输入框">
            <option value="">全部</option>
            <option value="1">实时（1）</option>
            <option value="2">历史（2）</option>
          </select>
        </label>

        <label class="字段">
          <div class="字段标题">Tx 电量（最小）</div>
          <input v-model.trim="筛选.btx_min" class="输入框" inputmode="numeric" placeholder="例如 0" />
        </label>

        <label class="字段">
          <div class="字段标题">Tx 电量（最大）</div>
          <input v-model.trim="筛选.btx_max" class="输入框" inputmode="numeric" placeholder="例如 100" />
        </label>

        <label class="字段">
          <div class="字段标题">排序字段</div>
          <select v-model="筛选.sort_by" class="输入框">
            <option value="time">time（业务时间）</option>
            <option value="created_at">created_at（入库时间）</option>
          </select>
        </label>

        <label class="字段">
          <div class="字段标题">排序方向</div>
          <select v-model="筛选.order" class="输入框">
            <option value="desc">从新到旧</option>
            <option value="asc">从旧到新</option>
          </select>
        </label>

        <label class="字段">
          <div class="字段标题">每页条数</div>
          <select v-model.number="分页.size" class="输入框">
            <option :value="20">20</option>
            <option :value="50">50</option>
            <option :value="100">100</option>
            <option :value="200">200</option>
          </select>
        </label>

        <button class="按钮 强调" type="button" :disabled="loading" @click="查询(1)">
          {{ loading ? "正在查询..." : "查询" }}
        </button>

        <button class="按钮" type="button" :disabled="导出中 || loading" @click="导出CSV">
          {{ 导出中 ? "正在导出..." : "导出 CSV" }}
        </button>
      </div>

      <div class="提示-次要 小字" style="margin-top: 10px">
        共 {{ 分页.total }} 条；当前第 {{ 分页.page }} / {{ 总页数 }} 页
      </div>

      <div v-if="错误信息" class="提示-错误" style="margin-top: 10px">{{ 错误信息 }}</div>
      <div v-if="导出提示" class="提示-次要 小字" style="margin-top: 10px">{{ 导出提示 }}</div>
    </div>

    <div class="卡片 面板">
      <div class="表格容器">
        <table class="表格">
          <thead>
            <tr>
              <th>UUID</th>
              <th>时间</th>
              <th>IN</th>
              <th>OUT</th>
              <th>电量</th>
              <th>告警</th>
              <th>Tx 电量</th>
              <th>记录类型</th>
              <th>活动类型</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in 列表" :key="String(r.id ?? r.time ?? Math.random())">
              <td class="数字">{{ r.uuid }}</td>
              <td class="数字">{{ 格式化时间文本(r.time) }}</td>
              <td class="数字">{{ r.in_count ?? "" }}</td>
              <td class="数字">{{ r.out_count ?? "" }}</td>
              <td class="数字">{{ r.battery ?? "" }}</td>
              <td>
                <span class="徽章" :class="Number(r.warn_status) === 1 ? '危险' : '成功'">
                  {{ Number(r.warn_status) === 1 ? "告警" : "正常" }}
                </span>
              </td>
              <td class="数字">{{ r.btx ?? "" }}</td>
              <td class="数字">{{ r.rec_type ?? "" }}</td>
              <td>{{ r.activity_type ?? "" }}</td>
            </tr>
            <tr v-if="!列表.length">
              <td colspan="9" class="提示-次要">暂无数据</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="行" style="justify-content: space-between; margin-top: 12px">
        <button class="按钮" type="button" :disabled="分页.page <= 1 || loading" @click="查询(分页.page - 1)">上一页</button>
        <div class="提示-次要 小字">第 {{ 分页.page }} / {{ 总页数 }} 页</div>
        <button class="按钮" type="button" :disabled="分页.page >= 总页数 || loading" @click="查询(分页.page + 1)">下一页</button>
      </div>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
/**
 * 历史页脚本
 *
 * 功能点：
 * - 筛选：设备、日期范围、告警状态、记录类型、Tx 电量范围；
 * - 分页：page/size + total；
 * - 排序：time/created_at + asc/desc；
 * - CSV 导出：按当前筛选条件导出（必要时分批拉取分页数据）。
 *
 * 关键实现逻辑：
 * 1) 使用 /api/v1/admin/records 获取分页数据（items + total）；
 * 2) 导出时按 size=500 分页循环拉取，拼接成 CSV 文本后触发下载；
 * 3) 为避免浏览器卡死，导出做最大条数保护，并给出提示。
 */

import { computed, onMounted, reactive, ref } from "vue";
import AppLayout from "@/layouts/AppLayout.vue";
import { api, ApiError } from "@/api/client";
import { 日期起始时间, 日期结束时间, 格式化时间文本 } from "@/utils/datetime";
import { 生成CSV文本 } from "@/utils/csv";
import { 触发文本下载 } from "@/utils/download";

type 设备选项 = { uuid: string; label: string };

const loading = ref<boolean>(false);
const 导出中 = ref<boolean>(false);
const 错误信息 = ref<string>("");
const 导出提示 = ref<string>("");

const 设备选项 = ref<设备选项[]>([]);

const 筛选 = reactive<{
  uuid: string;
  start: string;
  end: string;
  warn: string;
  rec_type: string;
  btx_min: string;
  btx_max: string;
  order: "asc" | "desc";
  sort_by: "time" | "created_at";
}>({
  uuid: "",
  start: "",
  end: "",
  warn: "",
  rec_type: "",
  btx_min: "",
  btx_max: "",
  order: "desc",
  sort_by: "time"
});

const 分页 = reactive<{ page: number; size: number; total: number }>({ page: 1, size: 50, total: 0 });
const 列表 = ref<Array<Record<string, any>>>([]);

const 总页数 = computed(() => Math.max(1, Math.ceil((分页.total || 0) / (分页.size || 1))));

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

function 解析整数(v: string): number | undefined {
  const s = (v || "").trim();
  if (!s) return undefined;
  const n = Number(s);
  if (!Number.isFinite(n)) return undefined;
  return Math.trunc(n);
}

async function 查询(page: number): Promise<void> {
  loading.value = true;
  错误信息.value = "";
  导出提示.value = "";
  try {
    分页.page = Math.max(1, page);

    const res = await api.adminRecordsList({
      page: 分页.page,
      size: 分页.size,
      uuid: 筛选.uuid || undefined,
      start: 筛选.start ? 日期起始时间(筛选.start) : undefined,
      end: 筛选.end ? 日期结束时间(筛选.end) : undefined,
      warn: 解析整数(筛选.warn),
      rec_type: 解析整数(筛选.rec_type),
      btx_min: 解析整数(筛选.btx_min),
      btx_max: 解析整数(筛选.btx_max),
      order: 筛选.order,
      sort_by: 筛选.sort_by
    });

    列表.value = (res.items || []) as any[];
    分页.total = Number(res.total || 0);
  } catch (e) {
    错误信息.value = e instanceof ApiError ? e.message : "查询失败：未知错误";
  } finally {
    loading.value = false;
  }
}

async function 导出CSV(): Promise<void> {
  导出中.value = true;
  错误信息.value = "";
  导出提示.value = "";
  try {
    const total = 分页.total || 0;
    if (total <= 0) {
      导出提示.value = "当前筛选条件下没有可导出的数据。";
      return;
    }

    const 最大导出条数 = 50_000;
    const 目标条数 = Math.min(total, 最大导出条数);
    if (total > 最大导出条数) {
      导出提示.value = `提示：当前共有 ${total} 条，为避免浏览器卡顿，仅导出前 ${最大导出条数} 条。`;
    }

    const headers = ["UUID", "时间", "IN", "OUT", "电量", "告警", "Tx电量", "记录类型", "活动类型"];
    const rows: Array<Array<unknown>> = [];

    const size = 500;
    let page = 1;
    let fetched = 0;

    while (fetched < 目标条数) {
      const res = await api.adminRecordsList({
        page,
        size,
        uuid: 筛选.uuid || undefined,
        start: 筛选.start ? 日期起始时间(筛选.start) : undefined,
        end: 筛选.end ? 日期结束时间(筛选.end) : undefined,
        warn: 解析整数(筛选.warn),
        rec_type: 解析整数(筛选.rec_type),
        btx_min: 解析整数(筛选.btx_min),
        btx_max: 解析整数(筛选.btx_max),
        order: 筛选.order,
        sort_by: 筛选.sort_by
      });

      const items = (res.items || []) as any[];
      if (!items.length) break;

      for (const r of items) {
        if (fetched >= 目标条数) break;
        rows.push([
          r.uuid ?? "",
          格式化时间文本(r.time),
          r.in_count ?? "",
          r.out_count ?? "",
          r.battery ?? "",
          r.warn_status ?? "",
          r.btx ?? "",
          r.rec_type ?? "",
          r.activity_type ?? ""
        ]);
        fetched += 1;
      }

      page += 1;
      if (items.length < size) break;
    }

    const csv = 生成CSV文本({ headers, rows, withBom: true });
    const ts = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
    触发文本下载({ filename: `历史记录_${ts}.csv`, text: csv, mime: "text/csv;charset=utf-8" });
  } catch (e) {
    错误信息.value = e instanceof ApiError ? e.message : "导出失败：未知错误";
  } finally {
    导出中.value = false;
  }
}

onMounted(async () => {
  await 加载设备选项();
  await 查询(1);
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

