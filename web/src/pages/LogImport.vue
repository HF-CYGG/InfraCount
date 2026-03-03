<template>
  <AppLayout title="日志导入" subtitle="预览 + 分批导入（仅管理员）">
    <div v-if="!是管理员" class="卡片 面板">
      <div class="提示-错误">无权限访问：该页面仅管理员可用。</div>
    </div>

    <template v-else>
      <div class="卡片 面板">
        <div class="区块头">
          <div>
            <div class="区块标题">1) 选择日志文件</div>
            <div class="区块说明">
              支持 txt/log/json 等文本格式（后端会自动识别并解析）。建议先“预览”，确认识别无误再导入。
            </div>
          </div>
          <div class="提示-次要 小字">已选：{{ 选中文件?.name || "-" }}</div>
        </div>

        <div class="分隔线" />

        <div class="行">
          <UiInput type="file" @change="选择文件" />
          <UiButton :loading="预览中" :disabled="!选中文件" @click="预览">{{ 预览中 ? "正在解析..." : "预览" }}</UiButton>
          <UiButton variant="primary" :loading="导入中" :disabled="!可导入" @click="开始导入">
            {{ 导入中 ? "正在导入..." : "开始导入" }}
          </UiButton>
          <UiButton :disabled="!导入中" @click="取消导入">取消导入</UiButton>
        </div>

        <div v-if="错误信息" class="提示-错误 上间距-10">{{ 错误信息 }}</div>
        <div v-if="提示信息" class="提示-次要 小字 上间距-10">{{ 提示信息 }}</div>
      </div>

      <div v-if="预览结果" class="卡片 面板">
        <div class="区块头">
          <div>
            <div class="区块标题">2) 解析预览</div>
            <div class="区块说明">
              文件：{{ 预览结果.filename || "-" }}；识别格式：{{ 预览结果.detected_format }}；总记录数：{{ 预览结果.total_records }}
            </div>
          </div>
        </div>

        <div class="分隔线" />

        <div class="子标题">按设备汇总</div>
        <div class="表格容器 上间距-10">
          <table class="表格">
            <thead>
              <tr>
                <th>UUID</th>
                <th>场地名称</th>
                <th>书院/分类</th>
                <th>记录数</th>
                <th>开始时间</th>
                <th>结束时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="d in 预览结果.devices" :key="String(d.uuid)">
                <td class="数字">{{ d.uuid }}</td>
                <td>{{ d.name || "" }}</td>
                <td>{{ d.category || "" }}</td>
                <td class="数字">{{ d.count }}</td>
                <td class="数字">{{ 格式化时间文本(d.start) }}</td>
                <td class="数字">{{ 格式化时间文本(d.end) }}</td>
              </tr>
              <tr v-if="!预览结果.devices.length">
                <td colspan="6" class="空态单元格">
                  <UiEmptyState title="无设备数据" description="该文件未解析出设备维度的记录。" />
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="分隔线" />

        <div class="子标题">样例记录（前 30 条）</div>
        <div class="表格容器 上间距-10">
          <table class="表格">
            <thead>
              <tr>
                <th>UUID</th>
                <th>时间</th>
                <th>IN</th>
                <th>OUT</th>
                <th>电量</th>
                <th>Tx电量</th>
                <th>记录类型</th>
                <th>告警</th>
                <th>活动类型</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(r, idx) in 预览结果.sample" :key="idx">
                <td class="数字">{{ r.uuid }}</td>
                <td class="数字">{{ 格式化时间文本(r.time) }}</td>
                <td class="数字">{{ r.in_count }}</td>
                <td class="数字">{{ r.out_count }}</td>
                <td class="数字">{{ r.battery }}</td>
                <td class="数字">{{ r.btx }}</td>
                <td class="数字">{{ r.rec_type }}</td>
                <td class="数字">{{ r.warn_status }}</td>
                <td>{{ r.activity_type }}</td>
              </tr>
              <tr v-if="!预览结果.sample.length">
                <td colspan="9" class="空态单元格">
                  <UiEmptyState title="无样例数据" description="该文件未解析出可展示的样例记录。" />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div v-if="导入中 || 导入完成" class="卡片 面板">
        <div class="区块头">
          <div>
            <div class="区块标题">3) 导入进度</div>
            <div class="区块说明">已导入 {{ 导入进度.imported }} / {{ 导入进度.total }}（{{ 导入百分比 }}%）</div>
          </div>
        </div>

        <div class="进度条外壳">
          <div class="进度条内" :style="{ width: 导入百分比 + '%' }" />
        </div>

        <div v-if="导入完成" class="提示-次要 小字 上间距-10">导入完成。你可以前往“历史”页面查看结果。</div>
      </div>
    </template>
  </AppLayout>
</template>

<script setup lang="ts">
/**
 * 日志导入页脚本
 *
 * 功能点：
 * - 预览：上传文件到 /api/v1/admin/device-log/preview，后端解析后返回 import_id 与样例；
 * - 分批导入：循环调用 /api/v1/admin/device-log/import，每次导入一段 offset/limit；
 * - 取消导入：前端停止循环（已提交到后端的批次无法回滚，但不会继续提交后续批次）。
 *
 * 体验优化：
 * - 预览阶段展示“按设备汇总”，便于快速确认文件覆盖范围；
 * - 导入阶段提供进度条，避免用户误以为卡死；
 * - 导入条数上限由后端控制（默认每次 500），前端按后端返回的 next_offset 推进。
 */

import AppLayout from "@/layouts/AppLayout.vue";
import { computed, ref } from "vue";
import { authStore } from "@/stores/auth";
import { api, ApiError } from "@/api/client";
import UiButton from "@/components/ui/UiButton.vue";
import UiEmptyState from "@/components/ui/UiEmptyState.vue";
import UiInput from "@/components/ui/UiInput.vue";
import { 格式化时间文本 } from "@/utils/datetime";
import { toastStore } from "@/stores/toast";

const 是管理员 = computed(() => authStore.state.user?.role === "admin");

const 文件输入 = ref<HTMLInputElement | null>(null);
const 选中文件 = ref<File | null>(null);

const 预览中 = ref<boolean>(false);
const 导入中 = ref<boolean>(false);
const 导入完成 = ref<boolean>(false);
const 取消标记 = ref<boolean>(false);

const 错误信息 = ref<string>("");
const 提示信息 = ref<string>("");

const 预览结果 = ref<null | {
  import_id: string;
  filename: string | null;
  detected_format: string;
  total_records: number;
  devices: Array<Record<string, any>>;
  sample: Array<Record<string, any>>;
}>(null);

const 导入进度 = ref<{ imported: number; total: number }>({ imported: 0, total: 0 });
const 导入百分比 = computed(() => {
  const total = 导入进度.value.total || 0;
  if (!total) return 0;
  return Math.min(100, Math.round((导入进度.value.imported / total) * 100));
});

const 可导入 = computed(() => Boolean(预览结果.value?.import_id) && (预览结果.value?.total_records || 0) > 0);

function 选择文件(e: Event): void {
  const input = e.target as HTMLInputElement;
  const f = input.files?.[0] || null;
  选中文件.value = f;
  预览结果.value = null;
  导入完成.value = false;
  导入进度.value = { imported: 0, total: 0 };
  错误信息.value = "";
  提示信息.value = f ? `已选择文件：${f.name}` : "";
  if (提示信息.value) toastStore.push(提示信息.value, { tone: "success" });
}

async function 预览(): Promise<void> {
  if (!选中文件.value) return;
  预览中.value = true;
  错误信息.value = "";
  提示信息.value = "";
  try {
    const res = await api.deviceLogPreview(选中文件.value);
    预览结果.value = res as any;
    导入进度.value = { imported: 0, total: Number(res.total_records || 0) };
    提示信息.value = "预览解析完成。";
    toastStore.push("预览解析完成", { tone: "success" });
  } catch (e) {
    错误信息.value = e instanceof ApiError ? e.message : "预览失败：未知错误";
  } finally {
    预览中.value = false;
  }
}

async function 开始导入(): Promise<void> {
  const ctx = 预览结果.value;
  if (!ctx) return;

  导入中.value = true;
  导入完成.value = false;
  取消标记.value = false;
  错误信息.value = "";
  提示信息.value = "";

  try {
    const importId = ctx.import_id;
    const total = Number(ctx.total_records || 0);
    const limit = 500;
    let offset = 0;
    let imported = 0;

    while (offset < total) {
      if (取消标记.value) {
        提示信息.value = "已取消导入（不会继续提交后续批次）。";
        toastStore.push(提示信息.value, { tone: "warning" });
        break;
      }

      const res = await api.deviceLogImportChunk({ import_id: importId, offset, limit });
      imported += Number(res.imported || 0);
      offset = Number(res.next_offset || offset + limit);
      导入进度.value = { imported, total };

      if (res.done) break;
      if (res.imported <= 0) break;
    }

    if (!取消标记.value) {
      导入完成.value = true;
      提示信息.value = `导入完成：共处理 ${导入进度.value.imported} 条。`;
      toastStore.push("导入完成", { tone: "success" });
    }
  } catch (e) {
    错误信息.value = e instanceof ApiError ? e.message : "导入失败：未知错误";
  } finally {
    导入中.value = false;
  }
}

function 取消导入(): void {
  取消标记.value = true;
}
</script>

<style scoped>
.进度条外壳 {
  margin-top: var(--间距-10);
  height: 10px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.04);
  overflow: hidden;
}

.进度条内 {
  height: 100%;
  background: rgba(var(--颜色-强调-rgb), 0.9);
}
</style>

