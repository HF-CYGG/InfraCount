<template>
  <AppLayout title="历史" subtitle="筛选 + 分页 + 排序 + 批量操作 + CSV 导出">
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
          <div class="字段标题">开始日期</div>
          <UiInput v-model="筛选.start" type="date" />
        </label>

        <label class="字段">
          <div class="字段标题">结束日期</div>
          <UiInput v-model="筛选.end" type="date" />
        </label>

        <label class="字段">
          <div class="字段标题">告警状态</div>
          <UiSelect v-model="筛选.warn">
            <option value="">全部</option>
            <option value="0">正常（0）</option>
            <option value="1">告警（1）</option>
          </UiSelect>
        </label>

        <label class="字段">
          <div class="字段标题">记录类型</div>
          <UiSelect v-model="筛选.rec_type">
            <option value="">全部</option>
            <option value="1">实时（1）</option>
            <option value="2">历史（2）</option>
          </UiSelect>
        </label>

        <label class="字段">
          <div class="字段标题">Tx 电量（最小）</div>
          <UiInput v-model.trim="筛选.btx_min" inputmode="numeric" placeholder="例如 0" />
        </label>

        <label class="字段">
          <div class="字段标题">Tx 电量（最大）</div>
          <UiInput v-model.trim="筛选.btx_max" inputmode="numeric" placeholder="例如 100" />
        </label>

        <label class="字段">
          <div class="字段标题">排序字段</div>
          <UiSelect v-model="筛选.sort_by">
            <option value="time">time（业务时间）</option>
            <option value="created_at">created_at（入库时间）</option>
          </UiSelect>
        </label>

        <label class="字段">
          <div class="字段标题">排序方向</div>
          <UiSelect v-model="筛选.order">
            <option value="desc">从新到旧</option>
            <option value="asc">从旧到新</option>
          </UiSelect>
        </label>

        <label class="字段">
          <div class="字段标题">每页条数</div>
          <UiSelect v-model.number="分页.size">
            <option :value="20">20</option>
            <option :value="50">50</option>
            <option :value="100">100</option>
            <option :value="200">200</option>
          </UiSelect>
        </label>

        <div class="筛选操作">
          <UiButton variant="primary" :loading="loading" @click="查询(1)">
            {{ loading ? "正在查询..." : "查询" }}
          </UiButton>
          <UiButton :disabled="loading" :loading="导出中" @click="导出CSV">
            {{ 导出中 ? "正在导出..." : "导出 CSV" }}
          </UiButton>
        </div>
      </div>

      <div class="筛选行 上间距-10">
        <div class="行">
          <UiButton variant="primary" @click="打开新增">添加记录</UiButton>
          <UiButton @click="打开批量编辑">批量修改</UiButton>
          <UiButton variant="danger" @click="打开范围删除">批量删除（时间段）</UiButton>
        </div>
        <div class="提示-次要 小字">已选 {{ 已选数量 }} 条</div>
      </div>

      <div class="提示-次要 小字 上间距-10">
        共 {{ 分页.total }} 条；当前第 {{ 分页.page }} / {{ 总页数 }} 页
      </div>

      <div v-if="错误信息" class="提示-错误 上间距-10">{{ 错误信息 }}</div>
      <div v-if="导出提示" class="提示-次要 小字 上间距-10">{{ 导出提示 }}</div>
    </div>

    <div class="卡片 面板">
      <div class="表格容器">
        <table class="表格">
          <thead>
            <tr>
              <th class="列-选择">
                <input type="checkbox" :checked="全选中" @change="切换全选($event)" />
              </th>
              <th>UUID</th>
              <th>时间</th>
              <th>IN</th>
              <th>OUT</th>
              <th>电量</th>
              <th>告警</th>
              <th>Tx 电量</th>
              <th>记录类型</th>
              <th>活动类型</th>
              <th class="列-操作">操作</th>
            </tr>
          </thead>
          <Transition name="ui-fade" mode="out-in" appear>
            <tbody :key="loading ? 'loading' : 'data'">
              <template v-if="loading">
                <tr v-for="i in 8" :key="i">
                  <td><UiSkeleton width="28px" height="12px" /></td>
                  <td><UiSkeleton width="220px" height="12px" /></td>
                  <td><UiSkeleton width="160px" height="12px" /></td>
                  <td><UiSkeleton width="48px" height="12px" /></td>
                  <td><UiSkeleton width="48px" height="12px" /></td>
                  <td><UiSkeleton width="48px" height="12px" /></td>
                  <td><UiSkeleton width="56px" height="12px" /></td>
                  <td><UiSkeleton width="56px" height="12px" /></td>
                  <td><UiSkeleton width="56px" height="12px" /></td>
                  <td><UiSkeleton width="96px" height="12px" /></td>
                  <td><UiSkeleton width="120px" height="12px" /></td>
                </tr>
              </template>
              <template v-else>
                <tr v-for="r in 列表" :key="String(r.id ?? r.time ?? Math.random())">
                  <td class="列-选择">
                    <input type="checkbox" :disabled="!可选中(r)" :checked="是否选中(r)" @change="切换选中(r)" />
                  </td>
                  <td class="数字">{{ r.uuid }}</td>
                  <td class="数字">{{ 格式化时间文本(r.time) }}</td>
                  <td class="数字">{{ r.in_count ?? "" }}</td>
                  <td class="数字">{{ r.out_count ?? "" }}</td>
                  <td class="数字">{{ r.battery ?? "" }}</td>
                  <td>
                    <UiTag :tone="Number(r.warn_status) === 1 ? 'danger' : 'success'">
                      {{ Number(r.warn_status) === 1 ? "告警" : "正常" }}
                    </UiTag>
                  </td>
                  <td class="数字">{{ r.btx ?? "" }}</td>
                  <td class="数字">{{ r.rec_type ?? "" }}</td>
                  <td>{{ r.activity_type ?? "" }}</td>
                  <td class="行">
                    <UiButton size="sm" :disabled="!可选中(r)" @click="打开编辑(r)">编辑</UiButton>
                    <UiButton size="sm" variant="danger" :disabled="!可选中(r)" :loading="删除中 === 取记录id(r)" @click="打开删除确认(r)">
                      删除
                    </UiButton>
                  </td>
                </tr>
                <tr v-if="!列表.length">
                  <td colspan="11" class="空态单元格">
                    <UiEmptyState title="暂无记录" description="请尝试调整筛选条件后重新查询。" />
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

    <UiDialog
      v-model:open="编辑弹窗显示"
      :title="编辑标题"
      confirm-text="保存"
      cancel-text="取消"
      :loading="保存中"
      confirm-variant="primary"
      @confirm="保存记录"
      @cancel="关闭编辑"
    >
      <div class="行 上间距-6">
        <label class="字段 宽字段">
          <div class="字段标题">设备 UUID</div>
          <UiSelect v-model="编辑表单.uuid">
            <option value="">请选择</option>
            <option v-for="d in 设备选项" :key="d.uuid" :value="d.uuid">{{ d.label }}</option>
          </UiSelect>
        </label>
        <label class="字段 宽字段">
          <div class="字段标题">时间</div>
          <UiInput v-model="编辑表单.time" type="datetime-local" />
        </label>
      </div>

      <div class="分隔线" />

      <div class="网格-3">
        <label class="字段">
          <div class="字段标题">IN</div>
          <UiInput v-model.trim="编辑表单.in_count" inputmode="numeric" placeholder="留空则不修改" />
        </label>
        <label class="字段">
          <div class="字段标题">OUT</div>
          <UiInput v-model.trim="编辑表单.out_count" inputmode="numeric" placeholder="留空则不修改" />
        </label>
        <label class="字段">
          <div class="字段标题">电量</div>
          <UiInput v-model.trim="编辑表单.battery" inputmode="numeric" placeholder="留空则不修改" />
        </label>
      </div>

      <div class="网格-3 上间距-10">
        <label class="字段">
          <div class="字段标题">Tx 电量</div>
          <UiInput v-model.trim="编辑表单.btx" inputmode="numeric" placeholder="留空则不修改" />
        </label>
        <label class="字段">
          <div class="字段标题">告警状态</div>
          <UiSelect v-model="编辑表单.warn_status">
            <option value="">保持不变</option>
            <option value="0">正常（0）</option>
            <option value="1">告警（1）</option>
          </UiSelect>
        </label>
        <label class="字段">
          <div class="字段标题">记录类型</div>
          <UiSelect v-model="编辑表单.rec_type">
            <option value="">保持不变</option>
            <option value="1">实时（1）</option>
            <option value="2">历史（2）</option>
          </UiSelect>
        </label>
      </div>

      <div class="上间距-10">
        <label class="字段">
          <div class="字段标题">活动类型</div>
          <UiSelect v-model="编辑表单.activity_type">
            <option value="">保持不变</option>
            <option v-for="t in 活动类型选项" :key="t" :value="t">{{ t }}</option>
          </UiSelect>
        </label>
      </div>

      <div v-if="编辑错误" class="提示-错误 小字 上间距-10">{{ 编辑错误 }}</div>
    </UiDialog>

    <UiDialog
      v-model:open="删除确认显示"
      title="确认删除"
      confirm-text="删除"
      cancel-text="取消"
      confirm-variant="danger"
      :loading="删除中 !== null"
      @confirm="确认删除"
      @cancel="关闭删除确认"
    >
      <div>将删除选中的历史记录，删除后不可恢复。</div>
    </UiDialog>

    <UiDialog
      v-model:open="批量弹窗显示"
      title="批量修改/删除"
      confirm-text="提交"
      cancel-text="取消"
      :loading="批量操作中"
      confirm-variant="primary"
      @confirm="执行批量操作"
      @cancel="关闭批量编辑"
    >
      <div class="区块说明">可以基于“当前勾选”或“筛选条件”进行批量修改或删除。</div>

      <div class="分隔线" />

      <div class="行">
        <label class="字段">
          <div class="字段标题">范围</div>
          <UiSelect v-model="批量范围">
            <option value="selection">当前勾选（{{ 已选数量 }} 条）</option>
            <option value="filter">按条件筛选</option>
          </UiSelect>
        </label>
      </div>

      <div v-if="批量范围 === 'filter'" class="上间距-10">
        <div class="网格-3">
          <label class="字段">
            <div class="字段标题">开始时间</div>
            <UiInput v-model="批量筛选.start" type="datetime-local" />
          </label>
          <label class="字段">
            <div class="字段标题">结束时间</div>
            <UiInput v-model="批量筛选.end" type="datetime-local" />
          </label>
          <label class="字段">
            <div class="字段标题">设备（可选）</div>
            <UiSelect v-model="批量筛选.uuid">
              <option value="">全部设备</option>
              <option v-for="d in 设备选项" :key="d.uuid" :value="d.uuid">{{ d.label }}</option>
            </UiSelect>
          </label>
        </div>
        <div class="行 上间距-10">
          <UiButton size="sm" :loading="批量查询中" @click="查询批量匹配数量">查询匹配数量</UiButton>
          <div class="提示-次要 小字">匹配 {{ 批量匹配数量 ?? "-" }} 条</div>
        </div>
      </div>

      <div class="分隔线" />

      <div class="网格-3">
        <label class="字段">
          <div class="字段标题">IN</div>
          <UiInput v-model.trim="批量表单.in_count" inputmode="numeric" placeholder="保持原值" />
        </label>
        <label class="字段">
          <div class="字段标题">OUT</div>
          <UiInput v-model.trim="批量表单.out_count" inputmode="numeric" placeholder="保持原值" />
        </label>
        <label class="字段">
          <div class="字段标题">电量</div>
          <UiInput v-model.trim="批量表单.battery" inputmode="numeric" placeholder="保持原值" />
        </label>
      </div>

      <div class="网格-3 上间距-10">
        <label class="字段">
          <div class="字段标题">Tx 电量</div>
          <UiInput v-model.trim="批量表单.btx" inputmode="numeric" placeholder="保持原值" />
        </label>
        <label class="字段">
          <div class="字段标题">告警状态</div>
          <UiSelect v-model="批量表单.warn_status">
            <option value="">保持原值</option>
            <option value="0">正常（0）</option>
            <option value="1">告警（1）</option>
          </UiSelect>
        </label>
        <label class="字段">
          <div class="字段标题">记录类型</div>
          <UiSelect v-model="批量表单.rec_type">
            <option value="">保持原值</option>
            <option value="1">实时（1）</option>
            <option value="2">历史（2）</option>
          </UiSelect>
        </label>
      </div>

      <div class="上间距-10">
        <label class="字段">
          <div class="字段标题">活动类型</div>
          <UiSelect v-model="批量表单.activity_type">
            <option value="">保持原值</option>
            <option v-for="t in 活动类型选项" :key="t" :value="t">{{ t }}</option>
          </UiSelect>
        </label>
      </div>

      <div class="上间距-10">
        <label class="字段">
          <div class="字段标题">批量删除</div>
          <div class="行">
            <input v-model="批量删除标记" type="checkbox" />
            <span class="提示-次要 小字">勾选后将删除匹配记录</span>
          </div>
        </label>
      </div>

      <div v-if="批量错误" class="提示-错误 小字 上间距-10">{{ 批量错误 }}</div>
    </UiDialog>

    <UiDialog
      v-model:open="范围删除弹窗显示"
      title="批量删除（时间段）"
      confirm-text="删除"
      cancel-text="取消"
      confirm-variant="danger"
      :loading="范围删除中"
      @confirm="确认删除范围"
      @cancel="关闭范围删除"
    >
      <div class="网格-2">
        <label class="字段">
          <div class="字段标题">起始时间</div>
          <UiInput v-model="范围删除.start" type="datetime-local" />
        </label>
        <label class="字段">
          <div class="字段标题">结束时间</div>
          <UiInput v-model="范围删除.end" type="datetime-local" />
        </label>
      </div>
      <div v-if="范围删除错误" class="提示-错误 小字 上间距-10">{{ 范围删除错误 }}</div>
    </UiDialog>
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
import UiButton from "@/components/ui/UiButton.vue";
import UiDialog from "@/components/ui/UiDialog.vue";
import UiEmptyState from "@/components/ui/UiEmptyState.vue";
import UiInput from "@/components/ui/UiInput.vue";
import UiSelect from "@/components/ui/UiSelect.vue";
import UiSkeleton from "@/components/ui/UiSkeleton.vue";
import UiTag from "@/components/ui/UiTag.vue";
import { 日期起始时间, 日期结束时间, 格式化时间文本, 本地日期时间 } from "@/utils/datetime";
import { 生成CSV文本 } from "@/utils/csv";
import { 触发文本下载 } from "@/utils/download";
import { useChunkedList } from "@/utils/chunkedList";
import { toastStore } from "@/stores/toast";

type 设备选项 = { uuid: string; label: string };

const loading = ref<boolean>(false);
const 导出中 = ref<boolean>(false);
const 错误信息 = ref<string>("");
const 导出提示 = ref<string>("");

const 设备选项 = ref<设备选项[]>([]);
const 活动类型选项 = [
  "班团活动",
  "公益/志愿活动",
  "会议活动",
  "培训活动",
  "其他活动",
  "全生异科导师活动",
  "散客访问",
  "社团活动",
  "书院活动",
  "体育活动",
  "项目工坊活动",
  "艺术活动",
  "项目工坊"
];

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
const { visible: 列表, setSource: 设置列表 } = useChunkedList<Record<string, any>>({ chunkSize: 50 });

const 总页数 = computed(() => Math.max(1, Math.ceil((分页.total || 0) / (分页.size || 1))));
const 已选id = ref<Set<number>>(new Set());
const 已选数量 = computed(() => 已选id.value.size);
const 当前页id列表 = computed<number[]>(() =>
  (列表.value || [])
    .map((r) => (Number.isFinite(Number((r as any).id)) ? Number((r as any).id) : null))
    .filter((x): x is number => x !== null)
);
const 全选中 = computed(() => {
  const ids = 当前页id列表.value;
  if (!ids.length) return false;
  return ids.every((id) => 已选id.value.has(id));
});

const 编辑弹窗显示 = ref<boolean>(false);
const 编辑模式 = ref<"create" | "edit">("create");
const 编辑记录id = ref<number | null>(null);
const 编辑错误 = ref<string>("");
const 保存中 = ref<boolean>(false);
const 编辑表单 = reactive<{
  uuid: string;
  time: string;
  in_count: string;
  out_count: string;
  battery: string;
  btx: string;
  warn_status: string;
  rec_type: string;
  activity_type: string;
}>({
  uuid: "",
  time: "",
  in_count: "",
  out_count: "",
  battery: "",
  btx: "",
  warn_status: "",
  rec_type: "",
  activity_type: ""
});
const 编辑标题 = computed(() => (编辑模式.value === "create" ? "添加记录" : "编辑记录"));

const 删除确认显示 = ref<boolean>(false);
const 删除目标 = ref<Record<string, any> | null>(null);
const 删除中 = ref<number | null>(null);

const 批量弹窗显示 = ref<boolean>(false);
const 批量范围 = ref<"selection" | "filter">("selection");
const 批量筛选 = reactive<{ start: string; end: string; uuid: string }>({ start: "", end: "", uuid: "" });
const 批量查询中 = ref<boolean>(false);
const 批量匹配数量 = ref<number | null>(null);
const 批量匹配ids = ref<number[]>([]);
const 批量表单 = reactive<{
  in_count: string;
  out_count: string;
  battery: string;
  btx: string;
  warn_status: string;
  rec_type: string;
  activity_type: string;
}>({
  in_count: "",
  out_count: "",
  battery: "",
  btx: "",
  warn_status: "",
  rec_type: "",
  activity_type: ""
});
const 批量删除标记 = ref<boolean>(false);
const 批量错误 = ref<string>("");
const 批量操作中 = ref<boolean>(false);

const 范围删除弹窗显示 = ref<boolean>(false);
const 范围删除 = reactive<{ start: string; end: string }>({ start: "", end: "" });
const 范围删除错误 = ref<string>("");
const 范围删除中 = ref<boolean>(false);

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

function 转为后端时间(v: string): string {
  const s = (v || "").trim();
  if (!s) return "";
  if (s.includes("T")) {
    const [d, t] = s.split("T");
    if (!t) return d;
    const tt = t.length === 5 ? `${t}:00` : t;
    return `${d} ${tt}`;
  }
  if (s.includes(" ")) {
    return s.length === 16 ? `${s}:00` : s;
  }
  return s;
}

function 转为输入时间(v: unknown): string {
  const s = 格式化时间文本(v);
  if (!s) return "";
  if (s.includes(" ")) {
    const [d, t] = s.split(" ");
    return `${d}T${(t || "").slice(0, 5)}`;
  }
  if (s.includes("T")) return s.slice(0, 16);
  return "";
}

function 取记录id(r: Record<string, any>): number | null {
  const id = Number(r?.id);
  return Number.isFinite(id) ? id : null;
}

function 可选中(r: Record<string, any>): boolean {
  return 取记录id(r) !== null;
}

function 是否选中(r: Record<string, any>): boolean {
  const id = 取记录id(r);
  if (id === null) return false;
  return 已选id.value.has(id);
}

function 切换选中(r: Record<string, any>): void {
  const id = 取记录id(r);
  if (id === null) return;
  const next = new Set(已选id.value);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  已选id.value = next;
}

function 切换全选(e: Event): void {
  const checked = (e.target as HTMLInputElement)?.checked;
  const ids = 当前页id列表.value;
  const next = new Set(已选id.value);
  if (checked) {
    ids.forEach((id) => next.add(id));
  } else {
    ids.forEach((id) => next.delete(id));
  }
  已选id.value = next;
}

function 清空选中(): void {
  已选id.value = new Set();
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

    设置列表(((res.items || []) as any[]) || []);
    清空选中();
    分页.total = Number(res.total || 0);
  } catch (e) {
    错误信息.value = e instanceof ApiError ? e.message : "查询失败：未知错误";
  } finally {
    loading.value = false;
  }
}

function 重置编辑表单(): void {
  编辑表单.uuid = 筛选.uuid || "";
  编辑表单.time = "";
  编辑表单.in_count = "";
  编辑表单.out_count = "";
  编辑表单.battery = "";
  编辑表单.btx = "";
  编辑表单.warn_status = "";
  编辑表单.rec_type = "";
  编辑表单.activity_type = "";
}

function 打开新增(): void {
  编辑模式.value = "create";
  编辑记录id.value = null;
  编辑错误.value = "";
  重置编辑表单();
  编辑表单.time = 转为输入时间(本地日期时间());
  编辑弹窗显示.value = true;
}

function 打开编辑(r: Record<string, any>): void {
  const id = 取记录id(r);
  if (id === null) return;
  编辑模式.value = "edit";
  编辑记录id.value = id;
  编辑错误.value = "";
  编辑表单.uuid = String(r.uuid || "");
  编辑表单.time = 转为输入时间(r.time);
  编辑表单.in_count = String(r.in_count ?? "");
  编辑表单.out_count = String(r.out_count ?? "");
  编辑表单.battery = String(r.battery ?? "");
  编辑表单.btx = String(r.btx ?? "");
  编辑表单.warn_status = r.warn_status !== undefined && r.warn_status !== null ? String(r.warn_status) : "";
  编辑表单.rec_type = r.rec_type !== undefined && r.rec_type !== null ? String(r.rec_type) : "";
  编辑表单.activity_type = String(r.activity_type ?? "");
  编辑弹窗显示.value = true;
}

function 关闭编辑(): void {
  编辑弹窗显示.value = false;
}

function 构造记录更新(): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  const time = 转为后端时间(编辑表单.time);
  if (time) out.time = time;
  if (编辑表单.uuid) out.uuid = 编辑表单.uuid;
  if (编辑表单.in_count.trim() !== "") out.in_count = 解析整数(编辑表单.in_count);
  if (编辑表单.out_count.trim() !== "") out.out_count = 解析整数(编辑表单.out_count);
  if (编辑表单.battery.trim() !== "") out.battery = 解析整数(编辑表单.battery);
  if (编辑表单.btx.trim() !== "") out.btx = 解析整数(编辑表单.btx);
  if (编辑表单.warn_status.trim() !== "") out.warn_status = 解析整数(编辑表单.warn_status);
  if (编辑表单.rec_type.trim() !== "") out.rec_type = 解析整数(编辑表单.rec_type);
  if (编辑表单.activity_type.trim() !== "") out.activity_type = 编辑表单.activity_type;
  return out;
}

async function 保存记录(): Promise<void> {
  保存中.value = true;
  编辑错误.value = "";
  try {
    const payload = 构造记录更新();
    if (!payload.uuid) {
      编辑错误.value = "请选择设备。";
      return;
    }
    if (!payload.time) {
      编辑错误.value = "请填写时间。";
      return;
    }

    if (编辑模式.value === "create") {
      await api.adminRecordCreate(payload);
      toastStore.push("记录已添加", { tone: "success" });
    } else {
      if (编辑记录id.value === null) {
        编辑错误.value = "缺少记录 ID。";
        return;
      }
      await api.adminRecordUpdate(编辑记录id.value, payload);
      toastStore.push("记录已更新", { tone: "success" });
    }
    编辑弹窗显示.value = false;
    await 查询(分页.page);
  } catch (e) {
    编辑错误.value = e instanceof ApiError ? e.message : "保存失败：未知错误";
  } finally {
    保存中.value = false;
  }
}

function 打开删除确认(r: Record<string, any>): void {
  const id = 取记录id(r);
  if (id === null) return;
  删除目标.value = r;
  删除确认显示.value = true;
}

function 关闭删除确认(): void {
  删除确认显示.value = false;
  删除目标.value = null;
}

async function 确认删除(): Promise<void> {
  const id = 删除目标.value ? 取记录id(删除目标.value) : null;
  if (id === null) return;
  删除中.value = id;
  try {
    await api.adminRecordDelete(id);
    toastStore.push("记录已删除", { tone: "success" });
    删除确认显示.value = false;
    删除目标.value = null;
    await 查询(分页.page);
  } catch (e) {
    错误信息.value = e instanceof ApiError ? e.message : "删除失败：未知错误";
  } finally {
    删除中.value = null;
  }
}

function 打开批量编辑(): void {
  批量范围.value = 已选数量.value > 0 ? "selection" : "filter";
  批量筛选.start = "";
  批量筛选.end = "";
  批量筛选.uuid = "";
  批量匹配数量.value = null;
  批量匹配ids.value = [];
  批量表单.in_count = "";
  批量表单.out_count = "";
  批量表单.battery = "";
  批量表单.btx = "";
  批量表单.warn_status = "";
  批量表单.rec_type = "";
  批量表单.activity_type = "";
  批量删除标记.value = false;
  批量错误.value = "";
  批量弹窗显示.value = true;
}

function 关闭批量编辑(): void {
  批量弹窗显示.value = false;
}

async function 查询批量匹配数量(): Promise<void> {
  批量查询中.value = true;
  批量错误.value = "";
  try {
    const start = 转为后端时间(批量筛选.start);
    const end = 转为后端时间(批量筛选.end);
    if (!start || !end) {
      批量错误.value = "请填写开始与结束时间。";
      return;
    }
    const res = await api.adminRecordsIds({
      uuid: 批量筛选.uuid || undefined,
      start,
      end
    });
    const ids = (res.ids || []).map((x) => Number(x)).filter((x) => Number.isFinite(x));
    批量匹配ids.value = ids;
    批量匹配数量.value = ids.length;
  } catch (e) {
    批量错误.value = e instanceof ApiError ? e.message : "查询失败：未知错误";
  } finally {
    批量查询中.value = false;
  }
}

function 构造批量更新(): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  if (批量表单.in_count.trim() !== "") out.in_count = 解析整数(批量表单.in_count);
  if (批量表单.out_count.trim() !== "") out.out_count = 解析整数(批量表单.out_count);
  if (批量表单.battery.trim() !== "") out.battery = 解析整数(批量表单.battery);
  if (批量表单.btx.trim() !== "") out.btx = 解析整数(批量表单.btx);
  if (批量表单.warn_status.trim() !== "") out.warn_status = 解析整数(批量表单.warn_status);
  if (批量表单.rec_type.trim() !== "") out.rec_type = 解析整数(批量表单.rec_type);
  if (批量表单.activity_type.trim() !== "") out.activity_type = 批量表单.activity_type;
  return out;
}

async function 执行批量操作(): Promise<void> {
  批量操作中.value = true;
  批量错误.value = "";
  try {
    const ids =
      批量范围.value === "selection" ? Array.from(已选id.value) : (批量匹配ids.value || []).slice();
    if (!ids.length) {
      批量错误.value = "没有可操作的记录。";
      return;
    }
    if (批量删除标记.value) {
      await api.adminRecordsBatchDelete({ ids });
      toastStore.push("批量删除完成", { tone: "success" });
      批量弹窗显示.value = false;
      await 查询(分页.page);
      return;
    }

    const updates = 构造批量更新();
    if (!Object.keys(updates).length) {
      批量错误.value = "请至少填写一个修改字段。";
      return;
    }
    await api.adminRecordsBatchUpdate({ ids, updates });
    toastStore.push("批量修改完成", { tone: "success" });
    批量弹窗显示.value = false;
    await 查询(分页.page);
  } catch (e) {
    批量错误.value = e instanceof ApiError ? e.message : "批量操作失败：未知错误";
  } finally {
    批量操作中.value = false;
  }
}

function 打开范围删除(): void {
  范围删除.start = "";
  范围删除.end = "";
  范围删除错误.value = "";
  范围删除弹窗显示.value = true;
}

function 关闭范围删除(): void {
  范围删除弹窗显示.value = false;
}

async function 确认删除范围(): Promise<void> {
  范围删除中.value = true;
  范围删除错误.value = "";
  try {
    const start = 转为后端时间(范围删除.start);
    const end = 转为后端时间(范围删除.end);
    if (!start || !end) {
      范围删除错误.value = "请填写起始与结束时间。";
      return;
    }
    await api.adminRecordsDeleteRange({ start, end });
    toastStore.push("范围删除完成", { tone: "success" });
    范围删除弹窗显示.value = false;
    await 查询(分页.page);
  } catch (e) {
    范围删除错误.value = e instanceof ApiError ? e.message : "删除失败：未知错误";
  } finally {
    范围删除中.value = false;
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

