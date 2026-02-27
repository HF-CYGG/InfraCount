<template>
  <AppLayout title="数据库合并导入" subtitle="上传 SQLite .db → 预览差异 → 选择策略 → 执行合并（仅管理员）">
    <div v-if="!是管理员" class="卡片 面板">
      <div class="提示-错误">无权限访问：该页面仅管理员可用。</div>
      <div class="提示-次要 小字" style="margin-top: 8px">请使用管理员账号登录后再操作。</div>
    </div>

    <template v-else>
      <div class="卡片 面板">
        <div class="标题">1）上传 SQLite 数据库文件</div>
        <div class="提示-次要 小字" style="margin-top: 6px">
          支持 .db / .sqlite / .sqlite3。上传后会生成 import_id，用于后续预览与执行。
        </div>

        <div class="行" style="gap: 10px; margin-top: 12px; align-items: center; flex-wrap: wrap">
          <input class="输入框" type="file" accept=".db,.sqlite,.sqlite3" @change="选择文件" />
          <button class="按钮 强调" type="button" :disabled="上传中 || !选择的文件" @click="上传">
            {{ 上传中 ? "上传中..." : "上传" }}
          </button>
          <button class="按钮" type="button" :disabled="上传中 && !选择的文件 && !importId" @click="重置">
            重置
          </button>
        </div>

        <div v-if="上传错误" class="提示-错误" style="margin-top: 10px">{{ 上传错误 }}</div>

        <div v-if="importId" class="提示-次要 小字" style="margin-top: 10px; line-height: 1.8">
          <div>已上传：{{ 上传文件名 }}</div>
          <div>import_id：<span class="数字">{{ importId }}</span></div>
          <div>大小：<span class="数字">{{ 上传文件大小显示 }}</span></div>
        </div>
      </div>

      <div class="卡片 面板">
        <div class="标题">2）选择合并策略</div>
        <div class="提示-次要 小字" style="margin-top: 6px">
          说明：预览统计会按你选择的策略给出“预计插入/预计更新/预计跳过”。执行时也会严格按该策略落库。
        </div>

        <div class="行" style="gap: 12px; margin-top: 12px; flex-wrap: wrap">
          <label class="字段">
            <div class="字段标题">遇到重复时</div>
            <select v-model="策略.merge_mode" class="输入框">
              <option value="skip_existing">跳过已存在（skip_existing）</option>
              <option value="update_existing">更新已存在（update_existing）</option>
            </select>
          </label>

          <label class="字段">
            <div class="字段标题">字段冲突偏好（仅更新模式生效）</div>
            <select v-model="策略.conflict_preference" class="输入框">
              <option value="prefer_import">优先导入库（prefer_import）</option>
              <option value="prefer_current_non_empty">优先保留当前库非空字段（prefer_current_non_empty）</option>
            </select>
          </label>
        </div>
      </div>

      <div class="卡片 面板">
        <div class="标题">3）预览差异</div>
        <div class="提示-次要 小字" style="margin-top: 6px">
          预览会统计每张表：导入总数、可新增、冲突、无效行，并给出按策略计算的预计动作。
        </div>

        <div class="行" style="gap: 10px; margin-top: 12px; flex-wrap: wrap; align-items: center">
          <button class="按钮 强调" type="button" :disabled="预览中 || !importId" @click="预览">
            {{ 预览中 ? "预览中..." : "生成预览" }}
          </button>
          <div v-if="预览提示" class="提示-次要 小字">{{ 预览提示 }}</div>
        </div>

        <div v-if="预览错误" class="提示-错误" style="margin-top: 10px">{{ 预览错误 }}</div>

        <div v-if="预览结果" class="表格容器" style="margin-top: 12px">
          <table class="表格">
            <thead>
              <tr>
                <th>表</th>
                <th class="数字">导入总数</th>
                <th class="数字">可新增</th>
                <th class="数字">冲突</th>
                <th class="数字">无效</th>
                <th class="数字">预计插入</th>
                <th class="数字">预计更新</th>
                <th class="数字">预计跳过</th>
                <th>说明</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="it in 预览表格行" :key="it.table">
                <td>{{ it.table }}</td>
                <td class="数字">{{ it.total }}</td>
                <td class="数字">{{ it.new }}</td>
                <td class="数字">{{ it.conflict }}</td>
                <td class="数字">{{ it.invalid }}</td>
                <td class="数字">{{ it.planInsert }}</td>
                <td class="数字">{{ it.planUpdate }}</td>
                <td class="数字">{{ it.planSkip }}</td>
                <td class="提示-次要 小字" style="white-space: normal">{{ it.reason }}</td>
              </tr>
              <tr v-if="!预览表格行.length">
                <td colspan="9" class="提示-次要">暂无预览数据</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="卡片 面板">
        <div class="标题">4）执行合并</div>
        <div class="提示-次要 小字" style="margin-top: 6px">
          执行在事务中进行：任意表合并失败会整体回滚，不会产生“部分导入”的中间状态；并会写入 audit_logs 便于审计。
        </div>

        <div class="行" style="gap: 10px; margin-top: 12px; flex-wrap: wrap; align-items: center">
          <button class="按钮 强调" type="button" :disabled="执行中 || !importId || !预览结果" @click="执行">
            {{ 执行中 ? "执行中..." : "开始合并" }}
          </button>
          <div v-if="执行提示" class="提示-次要 小字">{{ 执行提示 }}</div>
        </div>

        <div v-if="执行错误" class="提示-错误" style="margin-top: 10px">{{ 执行错误 }}</div>

        <div v-if="任务状态" style="margin-top: 12px">
          <div class="提示-次要 小字" style="line-height: 1.8">
            <div>任务状态：<span class="数字">{{ 任务状态.status }}</span></div>
            <div v-if="任务状态.progress?.stage">阶段：<span class="数字">{{ 任务状态.progress.stage }}</span></div>
            <div v-if="任务状态.progress?.table">当前表：<span class="数字">{{ 任务状态.progress.table }}</span></div>
            <div v-if="typeof 任务状态.progress?.progress === 'number'">
              进度：<span class="数字">{{ Math.round(任务状态.progress.progress * 100) }}%</span>
            </div>
          </div>
        </div>

        <div v-if="任务结果表格行.length" class="表格容器" style="margin-top: 12px">
          <table class="表格">
            <thead>
              <tr>
                <th>表</th>
                <th class="数字">插入</th>
                <th class="数字">更新</th>
                <th class="数字">无效跳过</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="it in 任务结果表格行" :key="it.table">
                <td>{{ it.table }}</td>
                <td class="数字">{{ it.inserted }}</td>
                <td class="数字">{{ it.updated }}</td>
                <td class="数字">{{ it.skipped_invalid }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </AppLayout>
</template>

<script setup lang="ts">
/**
 * “数据库合并导入”页面
 *
 * 实现逻辑（端到端流程）：
 * 1) 管理员上传 SQLite 文件：POST /api/v1/admin/db-merge/upload
 *    - 服务端保存为临时文件并返回 import_id；
 * 2) 预览差异：POST /api/v1/admin/db-merge/preview
 *    - 服务端通过 ATTACH 导入库，按各表签名键统计新增/冲突/无效；
 * 3) 执行合并：POST /api/v1/admin/db-merge/execute
 *    - 服务端启动后台任务，事务合并并写入 audit_logs；
 * 4) 轮询进度/结果：GET /api/v1/admin/db-merge/status?job_id=...
 *
 * 界面目标：
 * - 全中文交互；
 * - 尽量把“发生了什么、将要做什么”以表格方式展示清楚；
 * - 执行时展示阶段、当前表、百分比进度与最终统计。
 */

import { computed, onBeforeUnmount, reactive, ref } from "vue";
import AppLayout from "@/layouts/AppLayout.vue";
import { authStore } from "@/stores/auth";
import { api, ApiError } from "@/api/client";

type 合并策略 = {
  merge_mode: "skip_existing" | "update_existing";
  conflict_preference: "prefer_current_non_empty" | "prefer_import";
};

const 是管理员 = computed(() => authStore.state.user?.role === "admin");

const 选择的文件 = ref<File | null>(null);
const 上传中 = ref<boolean>(false);
const 上传错误 = ref<string>("");
const 上传文件名 = ref<string>("");
const 上传文件大小 = ref<number>(0);
const importId = ref<string>("");

const 策略 = reactive<合并策略>({
  merge_mode: "skip_existing",
  conflict_preference: "prefer_import"
});

const 预览中 = ref<boolean>(false);
const 预览错误 = ref<string>("");
const 预览提示 = ref<string>("");
const 预览结果 = ref<any | null>(null);

const 执行中 = ref<boolean>(false);
const 执行错误 = ref<string>("");
const 执行提示 = ref<string>("");
const jobId = ref<string>("");
const 任务状态 = ref<any | null>(null);

let 轮询定时器: number | null = null;

const 上传文件大小显示 = computed(() => {
  const b = Number(上传文件大小.value || 0);
  if (!b) return "-";
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  if (b < 1024 * 1024 * 1024) return `${(b / 1024 / 1024).toFixed(1)} MB`;
  return `${(b / 1024 / 1024 / 1024).toFixed(2)} GB`;
});

const 预览表格行 = computed(() => {
  const t = 预览结果.value?.tables || {};
  const keys = Object.keys(t).sort();
  return keys.map((k) => {
    const row = t[k] || {};
    const plan = row.plan || {};
    return {
      table: k,
      total: Number(row.total || 0),
      invalid: Number(row.invalid || 0),
      new: Number(row.new || 0),
      conflict: Number(row.conflict || 0),
      planInsert: Number(plan.insert || 0),
      planUpdate: Number(plan.update || 0),
      planSkip: Number(plan.skip || 0),
      reason: String(row.reason || "")
    };
  });
});

const 任务结果表格行 = computed(() => {
  const tables = 任务状态.value?.result?.tables || {};
  const keys = Object.keys(tables).sort();
  return keys
    .map((k) => {
      const row = tables[k] || {};
      return {
        table: k,
        inserted: Number(row.inserted || 0),
        updated: Number(row.updated || 0),
        skipped_invalid: Number(row.skipped_invalid || 0)
      };
    })
    .filter((x) => x.table);
});

function 选择文件(e: Event): void {
  const input = e.target as HTMLInputElement;
  const f = input.files && input.files.length ? input.files[0] : null;
  选择的文件.value = f;
  上传错误.value = "";
  if (f) {
    上传文件名.value = f.name;
    上传文件大小.value = f.size;
  }
}

function 停止轮询(): void {
  if (轮询定时器) {
    window.clearInterval(轮询定时器);
    轮询定时器 = null;
  }
}

function 重置(): void {
  停止轮询();
  选择的文件.value = null;
  上传中.value = false;
  上传错误.value = "";
  上传文件名.value = "";
  上传文件大小.value = 0;
  importId.value = "";
  预览中.value = false;
  预览错误.value = "";
  预览提示.value = "";
  预览结果.value = null;
  执行中.value = false;
  执行错误.value = "";
  执行提示.value = "";
  jobId.value = "";
  任务状态.value = null;
}

async function 上传(): Promise<void> {
  if (!选择的文件.value) return;
  上传中.value = true;
  上传错误.value = "";
  预览结果.value = null;
  任务状态.value = null;
  try {
    const res = await api.dbMergeUpload(选择的文件.value);
    importId.value = String(res.import_id || "");
    上传文件名.value = String(res.filename || 上传文件名.value || "");
    上传文件大小.value = Number(res.size_bytes || 上传文件大小.value || 0);
  } catch (e) {
    上传错误.value = e instanceof ApiError ? e.message : "上传失败：未知错误";
  } finally {
    上传中.value = false;
  }
}

async function 预览(): Promise<void> {
  if (!importId.value) return;
  预览中.value = true;
  预览错误.value = "";
  预览提示.value = "";
  try {
    const res = await api.dbMergePreview({
      import_id: importId.value,
      merge_mode: 策略.merge_mode,
      conflict_preference: 策略.conflict_preference
    });
    预览结果.value = res;
    预览提示.value = "预览生成成功。请确认策略与统计结果后再执行合并。";
  } catch (e) {
    预览错误.value = e instanceof ApiError ? e.message : "预览失败：未知错误";
  } finally {
    预览中.value = false;
  }
}

async function 轮询任务(): Promise<void> {
  if (!jobId.value) return;
  try {
    const res = await api.dbMergeStatus(jobId.value);
    任务状态.value = res.job || null;

    const job: any = res.job as any;
    const st = String(job?.status || "");
    if (st === "done") {
      执行中.value = false;
      执行提示.value = "合并完成。已在审计日志中记录本次导入。";
      停止轮询();
    }
    if (st === "error") {
      执行中.value = false;
      执行错误.value = String(job?.error || job?.progress?.error || "合并失败：未知错误");
      停止轮询();
    }
  } catch (e) {
    执行错误.value = e instanceof ApiError ? e.message : "查询任务状态失败：未知错误";
    执行中.value = false;
    停止轮询();
  }
}

async function 执行(): Promise<void> {
  if (!importId.value) return;
  if (!预览结果.value) return;

  执行中.value = true;
  执行错误.value = "";
  执行提示.value = "";
  任务状态.value = null;
  停止轮询();

  try {
    const res = await api.dbMergeExecute({
      import_id: importId.value,
      merge_mode: 策略.merge_mode,
      conflict_preference: 策略.conflict_preference
    });
    jobId.value = String(res.job_id || "");
    执行提示.value = jobId.value ? `任务已启动：${jobId.value}，正在合并...` : "任务已启动，正在合并...";

    await 轮询任务();
    轮询定时器 = window.setInterval(() => {
      void 轮询任务();
    }, 1000);
  } catch (e) {
    执行错误.value = e instanceof ApiError ? e.message : "启动合并失败：未知错误";
    执行中.value = false;
  }
}

onBeforeUnmount(() => {
  停止轮询();
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
  min-width: 280px;
}

.字段标题 {
  font-size: 12px;
  color: var(--颜色-次要文本);
}
</style>

