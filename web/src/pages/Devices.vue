<template>
  <AppLayout title="设备" subtitle="设备列表 + 映射编辑（场地名称/书院分类）">
    <div class="卡片 面板 筛选区">
      <div class="筛选行">
        <label class="字段">
          <div class="字段标题">搜索</div>
          <UiInput v-model.trim="搜索词" placeholder="按 UUID / 场地名称 / 书院筛选" />
        </label>

        <div class="筛选操作">
          <UiButton variant="primary" :loading="loading" @click="刷新">
            {{ loading ? "正在加载..." : "刷新" }}
          </UiButton>
          <div class="提示-次要 小字">共 {{ 过滤后总数 }} 台设备；已绑定场地 {{ 已绑定数量 }} 台</div>
        </div>
      </div>

      <div v-if="错误信息" class="提示-错误 上间距-10">{{ 错误信息 }}</div>
    </div>

    <div class="卡片 面板">
      <div class="表格容器">
        <table class="表格">
          <thead>
            <tr>
              <th>UUID</th>
              <th>场地名称</th>
              <th>书院/分类</th>
              <th class="列-操作">操作</th>
            </tr>
          </thead>
          <Transition name="ui-fade" mode="out-in" appear>
            <tbody :key="loading ? 'loading' : 'data'">
              <template v-if="loading">
                <tr v-for="i in 8" :key="i">
                  <td><UiSkeleton width="220px" height="12px" /></td>
                  <td><UiSkeleton width="180px" height="12px" /></td>
                  <td><UiSkeleton width="120px" height="12px" /></td>
                  <td><UiSkeleton width="72px" height="12px" /></td>
                </tr>
              </template>
              <template v-else>
                <tr v-for="d in 过滤后列表" :key="d.uuid">
                  <td class="数字">{{ d.uuid }}</td>
                  <td>
                    <span v-if="d.name">{{ d.name }}</span>
                    <span v-else class="提示-次要">未绑定</span>
                  </td>
                  <td>
                    <UiTag :tone="d.category ? 'primary' : 'default'">{{ d.category || "未分类" }}</UiTag>
                  </td>
                  <td>
                    <UiButton size="sm" @click="打开编辑(d)">编辑</UiButton>
                  </td>
                </tr>
                <tr v-if="!过滤后列表.length">
                  <td colspan="4" class="空态单元格">
                    <UiEmptyState title="暂无设备" description="请尝试调整搜索条件或刷新列表。" />
                  </td>
                </tr>
              </template>
            </tbody>
          </Transition>
        </table>
      </div>
    </div>

    <UiDialog
      v-model:open="编辑弹窗显示"
      title="编辑设备映射"
      confirm-text="保存"
      cancel-text="取消"
      :loading="保存中"
      confirm-variant="primary"
      @confirm="保存编辑"
      @cancel="关闭编辑"
    >
      <div class="提示-次要 小字">建议先维护“场地标准库”，再给设备绑定场地，可自动带出书院。</div>
      <div class="分隔线" />

      <label class="字段 宽字段">
        <div class="字段标题">UUID</div>
        <UiInput :model-value="编辑.uuid" disabled />
      </label>

      <label class="字段 宽字段">
        <div class="字段标题">场地名称</div>
        <UiSelect v-model="编辑.name">
          <option value="">未绑定</option>
          <option v-for="loc in 标准场地列表" :key="loc" :value="loc">{{ loc }}</option>
        </UiSelect>
        <div v-if="编辑.name && !标准场地映射[编辑.name]" class="提示-次要 小字 上间距-6">
          当前场地不在标准库中：不会自动匹配书院（建议去“场地”页补齐标准库）。
        </div>
      </label>

      <label class="字段 宽字段">
        <div class="字段标题">书院/分类</div>
        <UiSelect v-model="编辑.category">
          <option value="">未分类</option>
          <option v-for="a in 书院列表" :key="a" :value="a">{{ a }}</option>
        </UiSelect>
      </label>
    </UiDialog>
  </AppLayout>
</template>

<script setup lang="ts">
/**
 * 设备页脚本
 *
 * 功能点（对齐 templates/devices.html 的核心能力，并贴合 SPA 的页面划分）：
 * - 展示设备列表（uuid + 绑定的场地名称 + 书院分类）；
 * - 支持搜索过滤；
 * - 支持编辑映射（写入 registry：name/category）。
 *
 * 依赖数据源：
 * - 设备列表：GET /api/v1/devices
 * - 映射：GET /api/v1/devices/mapping
 * - 标准场地库（用于“场地名称”下拉）：GET /api/v1/locations/mapping
 * - 写入映射：POST /api/v1/admin/registry
 */

import { computed, onMounted, reactive, ref, watch } from "vue";
import AppLayout from "@/layouts/AppLayout.vue";
import { api, ApiError } from "@/api/client";
import UiButton from "@/components/ui/UiButton.vue";
import UiDialog from "@/components/ui/UiDialog.vue";
import UiEmptyState from "@/components/ui/UiEmptyState.vue";
import UiInput from "@/components/ui/UiInput.vue";
import UiSelect from "@/components/ui/UiSelect.vue";
import UiSkeleton from "@/components/ui/UiSkeleton.vue";
import UiTag from "@/components/ui/UiTag.vue";
import { toastStore } from "@/stores/toast";
import { useChunkedList } from "@/utils/chunkedList";

type 设备行 = { uuid: string; name: string; category: string };

const loading = ref<boolean>(false);
const 错误信息 = ref<string>("");
const 搜索词 = ref<string>("");

const 设备列表全量 = ref<设备行[]>([]);
const 标准场地映射 = ref<Record<string, string>>({});
const 书院列表 = ref<string[]>([]);

const 标准场地列表 = computed(() => Object.keys(标准场地映射.value || {}).sort());

const 已绑定数量 = computed(() => 设备列表全量.value.filter((d: 设备行) => Boolean(d.name)).length);

const 过滤后列表全量 = computed(() => {
  const q = 搜索词.value.trim().toLowerCase();
  if (!q) return 设备列表全量.value;
  return 设备列表全量.value.filter((d: 设备行) => {
    return (
      d.uuid.toLowerCase().includes(q) ||
      (d.name || "").toLowerCase().includes(q) ||
      (d.category || "").toLowerCase().includes(q)
    );
  });
});

const { visible: 过滤后列表, setSource: 设置过滤后列表 } = useChunkedList<设备行>({ chunkSize: 100 });
const 过滤后总数 = computed(() => 过滤后列表全量.value.length);

const 编辑弹窗显示 = ref<boolean>(false);
const 保存中 = ref<boolean>(false);
const 编辑 = reactive<{ uuid: string; name: string; category: string }>({ uuid: "", name: "", category: "" });

async function 刷新(): Promise<void> {
  loading.value = true;
  错误信息.value = "";
  try {
    const [devs, mappingRes, locMapRes, academies] = await Promise.all([
      api.devicesList(),
      api.deviceMapping(),
      api.locationsMapping(),
      api.academiesList()
    ]);

    const mapping = mappingRes.mapping || {};
    设备列表全量.value = (devs || [])
      .map((d) => d.uuid)
      .sort()
      .map((uuid) => {
        const m = mapping[uuid] || {};
        return {
          uuid,
          name: String(m.name || "").trim(),
          category: String(m.category || "").trim()
        };
      });

    标准场地映射.value = locMapRes.mapping || {};
    书院列表.value = (academies || []).map((a) => a.name).filter(Boolean);
    设置过滤后列表(过滤后列表全量.value);
  } catch (e) {
    错误信息.value = e instanceof ApiError ? e.message : "加载失败：未知错误";
  } finally {
    loading.value = false;
  }
}

function 打开编辑(d: 设备行): void {
  编辑.uuid = d.uuid;
  编辑.name = d.name || "";
  编辑.category = d.category || "";
  编辑弹窗显示.value = true;
}

function 关闭编辑(): void {
  编辑弹窗显示.value = false;
}

watch(
  () => 编辑.name,
  (name: string) => {
    const academy = 标准场地映射.value[name || ""];
    if (academy) {
      编辑.category = academy;
    }
  }
);

async function 保存编辑(): Promise<void> {
  保存中.value = true;
  错误信息.value = "";
  try {
    await api.adminRegistryUpsert({
      uuid: 编辑.uuid,
      name: 编辑.name || "",
      category: 编辑.category || ""
    });
    关闭编辑();
    await 刷新();
    toastStore.push("已保存设备映射", { tone: "success" });
  } catch (e) {
    错误信息.value = e instanceof ApiError ? e.message : "保存失败：未知错误";
  } finally {
    保存中.value = false;
  }
}

onMounted(() => {
watch(
  [() => 搜索词.value, () => 设备列表全量.value],
  () => {
    设置过滤后列表(过滤后列表全量.value);
  },
  { immediate: true }
);

  void 刷新();
});
</script>


