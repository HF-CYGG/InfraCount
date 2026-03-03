<template>
  <AppLayout title="活动" subtitle="筛选列表 + 聚合统计 + CSV/Excel 导入 + 散客同步预览">
    <div class="卡片 面板 筛选区">
      <div class="筛选行">
        <label class="字段">
          <div class="字段标题">开始日期</div>
          <UiInput v-model="筛选.start_date" type="date" />
        </label>
        <label class="字段">
          <div class="字段标题">结束日期</div>
          <UiInput v-model="筛选.end_date" type="date" />
        </label>

        <label class="字段 宽字段">
          <div class="字段标题">地点（多选）</div>
          <UiSelect v-model="筛选.locations" class="多选" multiple>
            <option v-for="x in 选项.locations" :key="x" :value="x">{{ x }}</option>
          </UiSelect>
        </label>

        <label class="字段 宽字段">
          <div class="字段标题">活动类型（多选）</div>
          <UiSelect v-model="筛选.types" class="多选" multiple>
            <option v-for="x in 选项.types" :key="x" :value="x">{{ x }}</option>
          </UiSelect>
        </label>

        <label class="字段 宽字段">
          <div class="字段标题">书院（多选）</div>
          <UiSelect v-model="筛选.academies" class="多选" multiple>
            <option v-for="x in 选项.academies" :key="x" :value="x">{{ x }}</option>
          </UiSelect>
        </label>

        <label class="字段">
          <div class="字段标题">周几（多选）</div>
          <UiSelect v-model="筛选.weekdays" class="多选" multiple>
            <option v-for="x in 选项.weekdays" :key="x" :value="x">{{ x }}</option>
          </UiSelect>
        </label>

        <label class="字段">
          <div class="字段标题">起始时间（多选）</div>
          <UiSelect v-model="筛选.start_times" class="多选" multiple>
            <option v-for="x in 选项.times" :key="x" :value="x">{{ x }}</option>
          </UiSelect>
        </label>

        <label class="字段">
          <div class="字段标题">每页条数</div>
          <UiSelect v-model.number="分页.page_size">
            <option :value="20">20</option>
            <option :value="50">50</option>
            <option :value="100">100</option>
          </UiSelect>
        </label>

        <div class="筛选操作">
          <UiButton variant="primary" :loading="loading" @click="查询(1)">
            {{ loading ? "正在查询..." : "查询" }}
          </UiButton>
          <UiButton :disabled="loading" :loading="导出中" @click="导出CSV">
            {{ 导出中 ? "正在导出..." : "导出 CSV（当前页）" }}
          </UiButton>
        </div>
      </div>

      <div v-if="错误信息" class="提示-错误 上间距-10">{{ 错误信息 }}</div>
      <div v-if="提示信息" class="提示-次要 小字 上间距-10">{{ 提示信息 }}</div>
    </div>

    <div class="两列栅格">
      <div class="卡片 面板">
        <div class="区块头">
          <div>
            <div class="区块标题">聚合统计</div>
            <div class="区块说明">基于当前筛选条件统计（KPI + Top 列表）。</div>
          </div>
        </div>

        <div class="分隔线" />

        <div class="三列栅格">
          <div class="卡片 面板 子卡片">
            <div class="卡片标题">活动场次</div>
            <div class="卡片数字 数字">{{ 聚合.kpis.total_events ?? 0 }}</div>
          </div>
          <div class="卡片 面板 子卡片">
            <div class="卡片标题">受众人数合计</div>
            <div class="卡片数字 数字">{{ 聚合.kpis.total_audience ?? 0 }}</div>
          </div>
          <div class="卡片 面板 子卡片">
            <div class="卡片标题">平均受众</div>
            <div class="卡片数字 数字">{{ 聚合.kpis.avg_audience ?? 0 }}</div>
          </div>
        </div>

        <div class="分隔线" />

        <div class="子标题">地点 Top（前 10）</div>
        <div class="区块说明">按场次数量降序。</div>
        <div class="表格容器 上间距-10">
          <table class="表格 小表格">
            <thead>
              <tr>
                <th>地点</th>
                <th>场次</th>
                <th>受众</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="x in (聚合.location_top || []).slice(0, 10)" :key="String(x.location)">
                <td>{{ x.location }}</td>
                <td class="数字">{{ x.count }}</td>
                <td class="数字">{{ x.audience }}</td>
              </tr>
              <tr v-if="!(聚合.location_top || []).length">
                <td colspan="3" class="空态单元格">
                  <UiEmptyState title="暂无统计数据" description="请调整筛选条件或先导入活动数据。" />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="卡片 面板">
        <div class="区块头">
          <div>
            <div class="区块标题">CSV / Excel 导入</div>
            <div class="区块说明">导入后会自动刷新列表与聚合统计。</div>
          </div>
        </div>

        <div class="分隔线" />

        <div class="行">
          <label class="字段 宽字段">
            <div class="字段标题">CSV 文件（/api/v1/activity/upload）</div>
            <UiInput type="file" accept=".csv" @change="选择CSV" />
          </label>
          <UiButton :disabled="!导入.csv" :loading="导入中 && 导入.类型 === 'csv'" @click="导入CSV">
            {{ 导入中 && 导入.类型 === "csv" ? "导入中..." : "导入 CSV" }}
          </UiButton>
        </div>

        <div class="行 上间距-12">
          <label class="字段 宽字段">
            <div class="字段标题">Excel 文件（/api/v1/activity/import-excel）</div>
            <UiInput type="file" accept=".xls,.xlsx" @change="选择Excel" />
          </label>
          <UiButton :disabled="!导入.excel" :loading="导入中 && 导入.类型 === 'excel'" @click="导入Excel">
            {{ 导入中 && 导入.类型 === "excel" ? "导入中..." : "导入 Excel" }}
          </UiButton>
        </div>
      </div>
    </div>

    <div class="卡片 面板">
      <div class="区块头">
        <div>
          <div class="区块标题">活动列表</div>
          <div class="区块说明">按当前筛选条件展示。</div>
        </div>
        <div class="提示-次要 小字">共 {{ 分页.total }} 条；第 {{ 分页.page }} / {{ 总页数 }} 页</div>
      </div>

      <div class="分隔线" />

      <div class="表格容器">
        <table class="表格">
          <thead>
            <tr>
              <th>日期</th>
              <th>周几</th>
              <th>起始</th>
              <th>结束</th>
              <th>书院</th>
              <th>地点</th>
              <th>活动名称</th>
              <th>类型</th>
              <th>受众</th>
              <th>备注</th>
            </tr>
          </thead>
          <Transition name="ui-fade" mode="out-in" appear>
            <tbody :key="loading ? 'loading' : 'data'">
              <template v-if="loading">
                <tr v-for="i in 8" :key="i">
                  <td><UiSkeleton width="90px" height="12px" /></td>
                  <td><UiSkeleton width="56px" height="12px" /></td>
                  <td><UiSkeleton width="56px" height="12px" /></td>
                  <td><UiSkeleton width="56px" height="12px" /></td>
                  <td><UiSkeleton width="96px" height="12px" /></td>
                  <td><UiSkeleton width="140px" height="12px" /></td>
                  <td><UiSkeleton width="220px" height="12px" /></td>
                  <td><UiSkeleton width="96px" height="12px" /></td>
                  <td><UiSkeleton width="56px" height="12px" /></td>
                  <td><UiSkeleton width="220px" height="12px" /></td>
                </tr>
              </template>
              <template v-else>
                <tr v-for="it in 列表" :key="String(it.id ?? `${it.date}-${it.start_time}-${it.location}-${it.activity_name}`)">
                  <td class="数字">{{ it.date }}</td>
                  <td>{{ it.weekday }}</td>
                  <td class="数字">{{ it.start_time }}</td>
                  <td class="数字">{{ it.end_time }}</td>
                  <td>{{ it.academy }}</td>
                  <td>{{ it.location }}</td>
                  <td>{{ it.activity_name }}</td>
                  <td>{{ it.activity_type }}</td>
                  <td class="数字">{{ it.audience_count }}</td>
                  <td class="可换行">{{ it.notes }}</td>
                </tr>
                <tr v-if="!列表.length">
                  <td colspan="10" class="空态单元格">
                    <UiEmptyState title="暂无活动" description="请调整筛选条件或先导入活动数据。" />
                  </td>
                </tr>
              </template>
            </tbody>
          </Transition>
        </table>
      </div>

      <div class="分页栏">
        <UiButton size="sm" :disabled="分页.page <= 1 || loading" @click="查询(分页.page - 1)">上一页</UiButton>
        <div class="提示-次要 小字">第 {{ 分页.page }} / {{ 总页数 }} 页</div>
        <UiButton size="sm" :disabled="分页.page >= 总页数 || loading" @click="查询(分页.page + 1)">下一页</UiButton>
      </div>
    </div>

    <div class="卡片 面板">
      <div class="区块头">
        <div>
          <div class="区块标题">散客同步预览</div>
          <div class="区块说明">
            从设备 records 统计散客访问（30 分钟粒度），预览后可写入 activity_events（类型：散客访问）。
          </div>
        </div>
        <div class="提示-次要 小字">预览 {{ 散客预览全量.length }} 条</div>
      </div>

      <div class="分隔线" />

      <div class="行">
        <label class="字段 宽字段">
          <div class="字段标题">选择设备（多选）</div>
          <UiSelect v-model="散客.devices" class="多选" multiple>
            <option v-for="d in 设备选项" :key="d.uuid" :value="d.uuid">{{ d.label }}</option>
          </UiSelect>
        </label>

        <UiButton :loading="散客加载中" :disabled="!散客.devices.length" @click="加载可用日期">
          {{ 散客加载中 ? "加载中..." : "加载可用日期" }}
        </UiButton>

        <label class="字段 宽字段">
          <div class="字段标题">选择日期（多选）</div>
          <UiSelect v-model="散客.dates" class="多选" multiple>
            <option v-for="d in 散客可用日期" :key="d" :value="d">{{ d }}</option>
          </UiSelect>
        </label>

        <UiButton :loading="散客预览中" :disabled="!散客.devices.length || !散客.dates.length" @click="散客预览">
          {{ 散客预览中 ? "预览中..." : "预览" }}
        </UiButton>

        <label class="字段">
          <div class="字段标题">同步模式</div>
          <UiSelect v-model="散客.mode">
            <option value="skip">跳过重复（skip）</option>
            <option value="overwrite">覆盖重复（overwrite）</option>
          </UiSelect>
        </label>

        <UiButton
          variant="primary"
          :loading="散客同步中"
          :disabled="!散客预览全量.length"
          @click="散客同步"
        >
          {{ 散客同步中 ? "同步中..." : "同步写入" }}
        </UiButton>
      </div>

      <div v-if="散客提示" class="提示-次要 小字 上间距-10">{{ 散客提示 }}</div>

      <div class="表格容器 上间距-12">
        <table class="表格">
          <thead>
            <tr>
              <th>日期</th>
              <th>起始</th>
              <th>结束</th>
              <th>书院</th>
              <th>地点</th>
              <th>人数</th>
              <th>备注</th>
            </tr>
          </thead>
          <Transition name="ui-fade" mode="out-in" appear>
            <tbody :key="散客预览中 ? 'loading' : 'data'">
              <template v-if="散客预览中">
                <tr v-for="i in 6" :key="i">
                  <td><UiSkeleton width="90px" height="12px" /></td>
                  <td><UiSkeleton width="56px" height="12px" /></td>
                  <td><UiSkeleton width="56px" height="12px" /></td>
                  <td><UiSkeleton width="96px" height="12px" /></td>
                  <td><UiSkeleton width="160px" height="12px" /></td>
                  <td><UiSkeleton width="56px" height="12px" /></td>
                  <td><UiSkeleton width="220px" height="12px" /></td>
                </tr>
              </template>
              <template v-else>
                <tr v-for="(it, idx) in 散客预览列表" :key="idx">
                  <td class="数字">{{ it.date }}</td>
                  <td class="数字">{{ it.start_time }}</td>
                  <td class="数字">{{ it.end_time }}</td>
                  <td>{{ it.academy }}</td>
                  <td>{{ it.location }}</td>
                  <td class="数字">{{ it.audience_count }}</td>
                  <td class="可换行">{{ it.notes }}</td>
                </tr>
                <tr v-if="!散客预览全量.length">
                  <td colspan="7" class="空态单元格">
                    <UiEmptyState title="暂无预览数据" description="先选择设备与日期后点击“预览”。" />
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
 * 活动页脚本
 *
 * 功能点：
 * - 筛选：日期范围 + 多维度（地点/类型/书院/周几/起始时间）；
 * - 列表：分页展示活动明细；
 * - 聚合：KPI + Top（来自 /api/v1/activity/aggregations）；
 * - 导入：CSV/Excel 上传导入；
 * - 散客同步：选择设备与日期，预览生成的散客活动后再写入。
 *
 * 实现逻辑：
 * 1) 初始化加载 options（用于筛选下拉）；
 * 2) 查询时并行拉取 events 与 aggregations；
 * 3) 导入成功后刷新（避免用户手动点查询）；
 * 4) 散客同步走“预览 -> 写入”两步，降低误操作风险。
 */

import { computed, onMounted, reactive, ref } from "vue";
import AppLayout from "@/layouts/AppLayout.vue";
import { api, ApiError } from "@/api/client";
import UiButton from "@/components/ui/UiButton.vue";
import UiEmptyState from "@/components/ui/UiEmptyState.vue";
import UiInput from "@/components/ui/UiInput.vue";
import UiSelect from "@/components/ui/UiSelect.vue";
import UiSkeleton from "@/components/ui/UiSkeleton.vue";
import { 生成CSV文本 } from "@/utils/csv";
import { 触发文本下载 } from "@/utils/download";
import { toastStore } from "@/stores/toast";
import { useChunkedList } from "@/utils/chunkedList";

type 设备选项 = { uuid: string; label: string };

const loading = ref<boolean>(false);
const 导出中 = ref<boolean>(false);
const 导入中 = ref<boolean>(false);
const 错误信息 = ref<string>("");
const 提示信息 = ref<string>("");

const 设备选项 = ref<设备选项[]>([]);

const 选项 = reactive<{ locations: string[]; types: string[]; academies: string[]; weekdays: string[]; times: string[] }>({
  locations: [],
  types: [],
  academies: [],
  weekdays: [],
  times: []
});

const 筛选 = reactive<{
  start_date: string;
  end_date: string;
  locations: string[];
  types: string[];
  academies: string[];
  weekdays: string[];
  start_times: string[];
}>({
  start_date: "",
  end_date: "",
  locations: [],
  types: [],
  academies: [],
  weekdays: [],
  start_times: []
});

const 分页 = reactive<{ page: number; page_size: number; total: number }>({ page: 1, page_size: 50, total: 0 });
const 列表全量 = ref<Array<Record<string, any>>>([]);
const { visible: 列表, setSource: 设置列表 } = useChunkedList<Record<string, any>>({ chunkSize: 50 });

const 聚合 = reactive<any>({ kpis: {}, location_top: [] });

const 总页数 = computed(() => Math.max(1, Math.ceil((分页.total || 0) / (分页.page_size || 1))));

const 导入 = reactive<{ csv: File | null; excel: File | null; 类型: "csv" | "excel" | "" }>({ csv: null, excel: null, 类型: "" });

const 散客加载中 = ref<boolean>(false);
const 散客预览中 = ref<boolean>(false);
const 散客同步中 = ref<boolean>(false);
const 散客提示 = ref<string>("");

const 散客 = reactive<{ devices: string[]; dates: string[]; mode: "skip" | "overwrite" }>({ devices: [], dates: [], mode: "skip" });
const 散客可用日期 = ref<string[]>([]);
const 散客预览全量 = ref<Array<Record<string, any>>>([]);
const { visible: 散客预览列表, setSource: 设置散客预览列表 } = useChunkedList<Record<string, any>>({ chunkSize: 60 });

function joinOrUndefined(arr: string[]): string | undefined {
  const v = (arr || []).map((x) => String(x || "").trim()).filter(Boolean);
  return v.length ? v.join(",") : undefined;
}

async function 加载基础数据(): Promise<void> {
  const [opts, devs, map] = await Promise.all([api.activityOptions(), api.devicesList(), api.deviceMapping()]);
  选项.locations = opts.locations || [];
  选项.types = opts.types || [];
  选项.academies = opts.academies || [];
  选项.weekdays = opts.weekdays || [];
  选项.times = opts.times || [];

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

async function 查询(page: number): Promise<void> {
  loading.value = true;
  错误信息.value = "";
  提示信息.value = "";
  try {
    分页.page = Math.max(1, page);

    const query = {
      start_date: 筛选.start_date || undefined,
      end_date: 筛选.end_date || undefined,
      locations: joinOrUndefined(筛选.locations),
      types: joinOrUndefined(筛选.types),
      academies: joinOrUndefined(筛选.academies),
      weekdays: joinOrUndefined(筛选.weekdays),
      start_times: joinOrUndefined(筛选.start_times)
    };

    const [events, aggs] = await Promise.all([
      api.activityEvents({ ...query, page: 分页.page, page_size: 分页.page_size }),
      api.activityAggregations(query)
    ]);

    列表全量.value = (events.items || []) as any[];
    设置列表(列表全量.value);
    分页.total = Number(events.total || 0);

    const a = aggs as any;
    聚合.kpis = a.kpis || {};
    聚合.location_top = a.location_top || [];
  } catch (e) {
    错误信息.value = e instanceof ApiError ? e.message : "查询失败：未知错误";
  } finally {
    loading.value = false;
  }
}

async function 导出CSV(): Promise<void> {
  导出中.value = true;
  错误信息.value = "";
  提示信息.value = "";
  try {
    if (!列表全量.value.length) {
      提示信息.value = "当前页没有可导出的数据。";
      toastStore.push(提示信息.value, { tone: "warning" });
      return;
    }

    const headers = ["日期", "周几", "起始时间", "结束时间", "书院", "地点", "活动名称", "活动类型", "受众学生数", "备注"];
    const rows = 列表全量.value.map((it: Record<string, any>) => [
      it.date,
      it.weekday,
      it.start_time,
      it.end_time,
      it.academy,
      it.location,
      it.activity_name,
      it.activity_type,
      it.audience_count,
      it.notes
    ]);
    const csv = 生成CSV文本({ headers, rows, withBom: true });
    const ts = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
    触发文本下载({ filename: `活动列表_第${分页.page}页_${ts}.csv`, text: csv, mime: "text/csv;charset=utf-8" });
    toastStore.push("已导出 CSV（当前页）", { tone: "success" });
  } catch (e) {
    错误信息.value = e instanceof ApiError ? e.message : "导出失败：未知错误";
  } finally {
    导出中.value = false;
  }
}

function 选择CSV(e: Event): void {
  const input = e.target as HTMLInputElement;
  导入.csv = input.files?.[0] || null;
  导入.类型 = "csv";
}

function 选择Excel(e: Event): void {
  const input = e.target as HTMLInputElement;
  导入.excel = input.files?.[0] || null;
  导入.类型 = "excel";
}

async function 导入CSV(): Promise<void> {
  if (!导入.csv) return;
  导入中.value = true;
  错误信息.value = "";
  提示信息.value = "";
  try {
    const res = await api.activityUploadCsv(导入.csv);
    提示信息.value = `CSV 导入完成：导入 ${res.imported} 条。`;
    toastStore.push(提示信息.value, { tone: "success" });
    await 查询(1);
  } catch (e) {
    错误信息.value = e instanceof ApiError ? e.message : "CSV 导入失败：未知错误";
  } finally {
    导入中.value = false;
  }
}

async function 导入Excel(): Promise<void> {
  if (!导入.excel) return;
  导入中.value = true;
  错误信息.value = "";
  提示信息.value = "";
  try {
    const res = await api.activityImportExcel(导入.excel);
    提示信息.value = `Excel 导入完成：写入 ${res.count} 条。`;
    toastStore.push(提示信息.value, { tone: "success" });
    await 查询(1);
  } catch (e) {
    错误信息.value = e instanceof ApiError ? e.message : "Excel 导入失败：未知错误";
  } finally {
    导入中.value = false;
  }
}

async function 加载可用日期(): Promise<void> {
  散客加载中.value = true;
  散客提示.value = "";
  try {
    const res = await api.walkinDates({ devices: 散客.devices.join(",") });
    散客可用日期.value = res.dates || [];
    散客提示.value = `可用日期：${散客可用日期.value.length} 天。`;
    toastStore.push(散客提示.value, { tone: "success" });
  } catch (e) {
    散客提示.value = e instanceof ApiError ? e.message : "加载可用日期失败：未知错误";
  } finally {
    散客加载中.value = false;
  }
}

async function 散客预览(): Promise<void> {
  散客预览中.value = true;
  散客提示.value = "";
  try {
    const res = await api.walkinPreviewDates({ devices: 散客.devices, dates: 散客.dates });
    散客预览全量.value = (res.items || []) as any[];
    设置散客预览列表(散客预览全量.value);
    散客提示.value = `预览生成 ${散客预览全量.value.length} 条散客活动。`;
    toastStore.push(散客提示.value, { tone: "success" });
  } catch (e) {
    散客提示.value = e instanceof ApiError ? e.message : "预览失败：未知错误";
  } finally {
    散客预览中.value = false;
  }
}

async function 散客同步(): Promise<void> {
  散客同步中.value = true;
  散客提示.value = "";
  try {
    const res = await api.walkinSync({ items: 散客预览全量.value, mode: 散客.mode });
    const count = Number((res as any).count || 0);
    const inserted = Number((res as any).inserted || 0);
    const updated = Number((res as any).updated || 0);
    散客提示.value = `同步完成：写入 ${count} 条（inserted=${inserted}, updated=${updated}）。`;
    toastStore.push("散客同步完成", { tone: "success" });
    await 查询(1);
  } catch (e) {
    散客提示.value = e instanceof ApiError ? e.message : "同步失败：未知错误";
  } finally {
    散客同步中.value = false;
  }
}

onMounted(async () => {
  await 加载基础数据();
  await 查询(1);
});
</script>

