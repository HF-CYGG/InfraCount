<template>
  <AppLayout title="场地" subtitle="标准库维护 + 候选/扫描 + 批量纠错">
    <div class="两列栅格">
      <div class="卡片 面板">
        <div class="区块头">
          <div>
            <div class="区块标题">标准场地库（Location → Academy）</div>
            <div class="区块说明">
              标准库用于：设备场地绑定联动书院、CSV 导入时的智能归属、散客同步时的归属推断等。
            </div>
          </div>
          <div class="提示-次要 小字">共 {{ 标准库过滤后列表.length }} 条</div>
        </div>

        <div class="分隔线" />

        <div class="筛选行">
          <label class="字段 宽字段">
            <div class="字段标题">搜索</div>
            <UiInput v-model.trim="标准库.search" placeholder="按场地名称/书院筛选" />
          </label>

          <label class="字段">
            <div class="字段标题">书院筛选</div>
            <UiSelect v-model="标准库.filterAcademy">
              <option value="">全部</option>
              <option v-for="a in 书院列表" :key="a" :value="a">{{ a }}</option>
            </UiSelect>
          </label>

          <div class="筛选操作">
            <UiButton :loading="loading" @click="刷新">{{ loading ? "正在刷新..." : "刷新" }}</UiButton>
          </div>
        </div>

        <div class="分隔线" />

        <div class="行">
          <label class="字段 宽字段">
            <div class="字段标题">标准场地名称</div>
            <UiInput v-model.trim="标准库.newLocation" placeholder="例如：Hello会客厅(Y1-103)" />
          </label>
          <label class="字段">
            <div class="字段标题">归属书院</div>
            <UiSelect v-model="标准库.newAcademy">
              <option value="">请选择</option>
              <option v-for="a in 书院列表" :key="a" :value="a">{{ a }}</option>
            </UiSelect>
          </label>
          <UiButton
            variant="primary"
            :loading="操作中"
            :disabled="!标准库.newLocation || !标准库.newAcademy"
            @click="添加标准库"
          >
            {{ 操作中 ? "处理中..." : "添加" }}
          </UiButton>
        </div>

        <div v-if="错误信息" class="提示-错误 上间距-10">{{ 错误信息 }}</div>
        <div v-if="提示信息" class="提示-次要 小字 上间距-10">{{ 提示信息 }}</div>

        <div class="表格容器 上间距-12 限高-520">
          <table class="表格 中表格">
            <thead>
              <tr>
                <th>标准场地名称</th>
                <th>归属书院</th>
                <th class="列-操作中">操作</th>
              </tr>
            </thead>
            <Transition name="ui-fade" mode="out-in" appear>
              <tbody :key="loading ? 'loading' : 'data'">
                <template v-if="loading">
                  <tr v-for="i in 8" :key="i">
                    <td><UiSkeleton width="220px" height="12px" /></td>
                    <td><UiSkeleton width="120px" height="12px" /></td>
                    <td><UiSkeleton width="120px" height="12px" /></td>
                  </tr>
                </template>
                <template v-else>
                  <tr v-for="it in 标准库过滤后列表" :key="it.location">
                    <td>{{ it.location }}</td>
                    <td>
                      <UiTag tone="primary">{{ it.academy }}</UiTag>
                    </td>
                    <td class="行">
                      <UiButton size="sm" @click="打开编辑(it)">编辑</UiButton>
                      <UiButton size="sm" variant="danger" :loading="操作中" @click="打开确认删除标准库(it.location)">
                        删除
                      </UiButton>
                    </td>
                  </tr>
                  <tr v-if="!标准库过滤后列表.length">
                    <td colspan="3" class="空态单元格">
                      <UiEmptyState title="暂无标准场地" description="先添加一个标准场地，后续可用于设备绑定与纠错。" />
                    </td>
                  </tr>
                </template>
              </tbody>
            </Transition>
          </table>
        </div>
      </div>

      <div class="卡片 面板">
        <div class="区块头">
          <div>
            <div class="区块标题">书院分类维护</div>
            <div class="区块说明">用于设备分类、标准库归属、统计维度等。</div>
          </div>
          <div class="提示-次要 小字">共 {{ 书院对象列表.length }} 条</div>
        </div>

        <div class="分隔线" />

        <div class="行">
          <label class="字段 宽字段">
            <div class="字段标题">新增书院名称</div>
            <UiInput v-model.trim="书院新增" placeholder="例如：至善书院" />
          </label>
          <UiButton variant="primary" :loading="操作中" :disabled="!书院新增" @click="添加书院">
            {{ 操作中 ? "处理中..." : "添加" }}
          </UiButton>
        </div>

        <div class="表格容器 上间距-12 限高-520">
          <table class="表格 小表格">
            <thead>
              <tr>
                <th>顺序</th>
                <th>书院名称</th>
                <th class="列-操作宽">操作</th>
              </tr>
            </thead>
            <Transition name="ui-fade" mode="out-in" appear>
              <tbody :key="loading ? 'loading' : 'data'">
                <template v-if="loading">
                  <tr v-for="i in 8" :key="i">
                    <td><UiSkeleton width="40px" height="12px" /></td>
                    <td><UiSkeleton width="160px" height="12px" /></td>
                    <td><UiSkeleton width="180px" height="12px" /></td>
                  </tr>
                </template>
                <template v-else>
                  <tr v-for="(a, idx) in 书院对象列表" :key="a.id">
                    <td class="数字">{{ idx + 1 }}</td>
                    <td>{{ a.name }}</td>
                    <td class="行">
                      <UiButton size="sm" :disabled="idx === 0 || 操作中" @click="移动书院(idx, -1)">上移</UiButton>
                      <UiButton
                        size="sm"
                        :disabled="idx === 书院对象列表.length - 1 || 操作中"
                        @click="移动书院(idx, 1)"
                      >
                        下移
                      </UiButton>
                      <UiButton size="sm" variant="danger" :loading="操作中" @click="打开确认删除书院(a.id, a.name)">删除</UiButton>
                    </td>
                  </tr>
                  <tr v-if="!书院对象列表.length">
                    <td colspan="3" class="空态单元格">
                      <UiEmptyState title="暂无书院" description="添加书院后，可用于设备分类与场地归属。" />
                    </td>
                  </tr>
                </template>
              </tbody>
            </Transition>
          </table>
        </div>
      </div>
    </div>

    <div class="卡片 面板">
      <div class="区块头">
        <div>
          <div class="区块标题">候选/扫描与批量纠错</div>
          <div class="区块说明">
            通过候选匹配或自动扫描，把非标准场地合并到标准场地，并统一书院归属。
          </div>
        </div>
        <div class="提示-次要 小字">候选 {{ 纠错.candidates.length }} 条</div>
      </div>

      <div class="分隔线" />

      <div class="行">
        <label class="字段 宽字段">
          <div class="字段标题">目标标准场地</div>
          <UiSelect v-model="纠错.target">
            <option value="">请选择</option>
            <option v-for="it in 标准库列表" :key="it.location" :value="it.location">{{ it.location }}</option>
          </UiSelect>
        </label>

        <UiButton :loading="操作中" :disabled="!纠错.target" @click="加载候选">{{ 操作中 ? "处理中..." : "获取候选" }}</UiButton>

        <UiButton
          variant="primary"
          :loading="操作中"
          :disabled="!纠错.target || !纠错.selectedSources.length"
          @click="打开确认纠错"
        >
          {{ 操作中 ? "处理中..." : "确认纠错" }}
        </UiButton>

        <UiButton :loading="扫描中" @click="自动扫描">{{ 扫描中 ? "扫描中..." : "自动扫描" }}</UiButton>

        <UiButton variant="primary" :loading="操作中" :disabled="!批量可提交" @click="打开确认批量纠错">
          {{ 操作中 ? "处理中..." : "提交批量纠错" }}
        </UiButton>
      </div>

      <div class="提示-次要 小字 上间距-10">
        候选纠错：选择目标标准场地后，可从候选列表选择要合并的原始场地（会重命名为目标场地）。
      </div>

      <div class="表格容器 上间距-12 限高-320">
        <table class="表格">
          <thead>
            <tr>
              <th class="列-选择">选择</th>
              <th>候选原始场地</th>
              <th>匹配提示</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in 纠错.candidates" :key="c">
              <td>
                <input v-model="纠错.selectedSources" :value="c" type="checkbox" />
              </td>
              <td>{{ c }}</td>
              <td class="提示-次要">将合并到：{{ 纠错.target }}</td>
            </tr>
            <tr v-if="!纠错.candidates.length">
              <td colspan="3" class="空态单元格">
                <UiEmptyState title="暂无候选数据" description="请先选择目标标准场地并点击“获取候选”。" />
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="分隔线" />

      <div class="子标题">自动扫描结果</div>
      <div class="区块说明">
        高置信度可直接批量提交；低置信度建议先人工确认再提交。
      </div>

      <div class="两列栅格 上间距-12">
        <div class="卡片 面板 子卡片">
          <div class="子标题">高置信度（≥90）</div>
          <div class="表格容器 上间距-10 限高-320">
            <table class="表格">
              <thead>
                <tr>
                  <th class="列-选择">选择</th>
                  <th>目标标准场地</th>
                  <th>原始场地</th>
                  <th>分数</th>
                  <th>归属书院</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(it, idx) in 扫描结果.high_confidence" :key="idx">
                  <td><input v-model="批量选择" :value="`H-${idx}`" type="checkbox" /></td>
                  <td>{{ it.target }}</td>
                  <td>{{ it.source }}</td>
                  <td class="数字">{{ it.score }}</td>
                  <td>{{ it.academy || 标准库映射[it.target] || "" }}</td>
                </tr>
                <tr v-if="!扫描结果.high_confidence.length">
                  <td colspan="5" class="空态单元格">
                    <UiEmptyState title="暂无数据" description="点击“自动扫描”生成建议列表。" />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="卡片 面板 子卡片">
          <div class="子标题">需人工确认（60~89）</div>
          <div class="表格容器 上间距-10 限高-320">
            <table class="表格">
              <thead>
                <tr>
                  <th class="列-选择">选择</th>
                  <th>目标标准场地</th>
                  <th>原始场地</th>
                  <th>分数</th>
                  <th>归属书院</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(it, idx) in 扫描结果.manual_review" :key="idx">
                  <td><input v-model="批量选择" :value="`M-${idx}`" type="checkbox" /></td>
                  <td>{{ it.target }}</td>
                  <td>{{ it.source }}</td>
                  <td class="数字">{{ it.score }}</td>
                  <td>{{ it.academy || 标准库映射[it.target] || "" }}</td>
                </tr>
                <tr v-if="!扫描结果.manual_review.length">
                  <td colspan="5" class="空态单元格">
                    <UiEmptyState title="暂无数据" description="点击“自动扫描”生成建议列表。" />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>

    <UiDialog
      v-model:open="编辑弹窗显示"
      title="编辑标准场地"
      confirm-text="保存"
      cancel-text="取消"
      :loading="操作中"
      confirm-variant="primary"
      @confirm="保存编辑"
      @cancel="关闭编辑"
    >
      <div class="提示-次要 小字">如修改了场地名称，会自动执行“删除旧项 + 新增新项”。</div>

      <div class="分隔线" />

      <label class="字段 宽字段">
        <div class="字段标题">标准场地名称</div>
        <UiInput v-model.trim="编辑表单.location" />
      </label>
      <label class="字段">
        <div class="字段标题">归属书院</div>
        <UiSelect v-model="编辑表单.academy">
          <option value="">请选择</option>
          <option v-for="a in 书院列表" :key="a" :value="a">{{ a }}</option>
        </UiSelect>
      </label>

      <div v-if="编辑错误" class="提示-错误 小字 上间距-10">{{ 编辑错误 }}</div>
    </UiDialog>

    <UiDialog
      v-model:open="确认弹窗显示"
      :title="确认标题"
      :confirm-text="确认按钮文本"
      cancel-text="取消"
      :confirm-variant="确认变体"
      :loading="操作中"
      @confirm="执行确认动作"
      @cancel="关闭确认弹窗"
    >
      <div>{{ 确认描述 }}</div>
    </UiDialog>
  </AppLayout>
</template>

<script setup lang="ts">
/**
 * 场地页脚本
 *
 * 功能点：
 * - 标准库维护：增删改查 Location-Academy 映射；
 * - 候选：按目标标准场地获取相似候选，并合并/纠错；
 * - 自动扫描：批量发现“可能应合并”的场地，并支持批量提交纠错；
 * - 书院分类维护：增删与排序（用于多处下拉选项）。
 *
 * 关键实现逻辑：
 * 1) 刷新时同时拉取：标准库映射 + 书院列表；
 * 2) “编辑标准场地”若改名，按“delete old + upsert new”实现（后端当前为 upsert 接口）；
 * 3) 批量纠错提交前按 target 聚合 sources，构造 /api/v1/locations/batch-correct payload。
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
import { toastStore } from "@/stores/toast";

type 标准库项 = { location: string; academy: string };
type 书院项 = { id: number; name: string; sort_order?: number };

const loading = ref<boolean>(false);
const 扫描中 = ref<boolean>(false);
const 操作中 = ref<boolean>(false);
const 错误信息 = ref<string>("");
const 提示信息 = ref<string>("");

const 标准库映射 = ref<Record<string, string>>({});
const 书院对象列表 = ref<书院项[]>([]);
const 书院新增 = ref<string>("");

const 标准库 = reactive<{ search: string; filterAcademy: string; newLocation: string; newAcademy: string }>({
  search: "",
  filterAcademy: "",
  newLocation: "",
  newAcademy: ""
});

const 标准库列表 = computed<标准库项[]>(() => {
  const m = 标准库映射.value || {};
  return Object.keys(m)
    .sort()
    .map((k) => ({ location: k, academy: String(m[k] || "").trim() }));
});

const 书院列表 = computed(() => 书院对象列表.value.map((a) => a.name).filter(Boolean));

const 标准库过滤后列表 = computed(() => {
  const q = 标准库.search.trim().toLowerCase();
  const aca = 标准库.filterAcademy;
  return 标准库列表.value.filter((it) => {
    if (aca && it.academy !== aca) return false;
    if (!q) return true;
    return it.location.toLowerCase().includes(q) || it.academy.toLowerCase().includes(q);
  });
});

const 编辑弹窗显示 = ref<boolean>(false);
const 编辑原始名称 = ref<string>("");
const 编辑错误 = ref<string>("");
const 编辑表单 = reactive<{ location: string; academy: string }>({ location: "", academy: "" });

const 确认弹窗显示 = ref<boolean>(false);
const 确认标题 = ref<string>("");
const 确认描述 = ref<string>("");
const 确认按钮文本 = ref<string>("确认");
const 确认变体 = ref<"default" | "primary" | "danger">("primary");
const 确认动作 = ref<null | (() => Promise<void>)>(null);

function 关闭确认弹窗(): void {
  确认弹窗显示.value = false;
  确认标题.value = "";
  确认描述.value = "";
  确认按钮文本.value = "确认";
  确认变体.value = "primary";
  确认动作.value = null;
}

async function 执行确认动作(): Promise<void> {
  if (!确认动作.value) return;
  await 确认动作.value();
  关闭确认弹窗();
}

function 打开确认删除标准库(location: string): void {
  确认标题.value = "确认删除标准场地";
  确认描述.value = `将删除标准场地：${location}`;
  确认按钮文本.value = "删除";
  确认变体.value = "danger";
  确认动作.value = async () => {
    await 删除标准库(location);
  };
  确认弹窗显示.value = true;
}

function 打开确认删除书院(id: number, name: string): void {
  确认标题.value = "确认删除书院";
  确认描述.value = `将删除书院：${name}`;
  确认按钮文本.value = "删除";
  确认变体.value = "danger";
  确认动作.value = async () => {
    await 删除书院(id);
  };
  确认弹窗显示.value = true;
}

function 打开确认纠错(): void {
  确认标题.value = "确认执行纠错";
  确认描述.value = `将把所选原始场地合并到：${纠错.target}`;
  确认按钮文本.value = "确认纠错";
  确认变体.value = "primary";
  确认动作.value = 执行纠错;
  确认弹窗显示.value = true;
}

function 打开确认批量纠错(): void {
  const count = 构造批量纠错Payload().reduce((acc, x) => acc + x.sources.length, 0);
  确认标题.value = "确认提交批量纠错";
  确认描述.value = `将提交 ${count} 条合并纠错操作。`;
  确认按钮文本.value = "提交";
  确认变体.value = "primary";
  确认动作.value = 提交批量纠错;
  确认弹窗显示.value = true;
}

const 纠错 = reactive<{ target: string; candidates: string[]; selectedSources: string[] }>({
  target: "",
  candidates: [],
  selectedSources: []
});

const 扫描结果 = reactive<{ high_confidence: any[]; manual_review: any[] }>({ high_confidence: [], manual_review: [] });
const 批量选择 = ref<string[]>([]);

const 批量可提交 = computed(() => 批量选择.value.length > 0 && (扫描结果.high_confidence.length + 扫描结果.manual_review.length) > 0);

async function 刷新(): Promise<void> {
  loading.value = true;
  错误信息.value = "";
  提示信息.value = "";
  try {
    const [mapping, academies] = await Promise.all([api.locationsMapping(), api.academiesList()]);
    标准库映射.value = mapping.mapping || {};
    书院对象列表.value = (academies || []).slice();
  } catch (e) {
    错误信息.value = e instanceof ApiError ? e.message : "刷新失败：未知错误";
  } finally {
    loading.value = false;
  }
}

async function 添加标准库(): Promise<void> {
  const location = 标准库.newLocation.trim();
  const academy = 标准库.newAcademy.trim();
  if (!location || !academy) return;
  操作中.value = true;
  错误信息.value = "";
  提示信息.value = "";
  try {
    await api.locationsMappingUpsert({ location, academy });
    标准库.newLocation = "";
    提示信息.value = "添加成功。";
    toastStore.push("已添加标准场地", { tone: "success" });
    await 刷新();
  } catch (e) {
    错误信息.value = e instanceof ApiError ? e.message : "添加失败：未知错误";
  } finally {
    操作中.value = false;
  }
}

function 打开编辑(it: 标准库项): void {
  编辑原始名称.value = it.location;
  编辑表单.location = it.location;
  编辑表单.academy = it.academy;
  编辑错误.value = "";
  编辑弹窗显示.value = true;
}

function 关闭编辑(): void {
  编辑弹窗显示.value = false;
}

async function 保存编辑(): Promise<void> {
  编辑错误.value = "";
  const newLoc = 编辑表单.location.trim();
  const newAca = 编辑表单.academy.trim();
  if (!newLoc || !newAca) {
    编辑错误.value = "场地名称与书院不能为空。";
    return;
  }
  操作中.value = true;
  try {
    const old = 编辑原始名称.value;
    if (old && old !== newLoc) {
      await api.locationsMappingDelete(old);
    }
    await api.locationsMappingUpsert({ location: newLoc, academy: newAca });
    关闭编辑();
    提示信息.value = "保存成功。";
    toastStore.push("已保存标准场地", { tone: "success" });
    await 刷新();
  } catch (e) {
    编辑错误.value = e instanceof ApiError ? e.message : "保存失败：未知错误";
  } finally {
    操作中.value = false;
  }
}

async function 删除标准库(location: string): Promise<void> {
  操作中.value = true;
  错误信息.value = "";
  提示信息.value = "";
  try {
    await api.locationsMappingDelete(location);
    提示信息.value = "已删除。";
    toastStore.push("已删除标准场地", { tone: "success" });
    await 刷新();
  } catch (e) {
    错误信息.value = e instanceof ApiError ? e.message : "删除失败：未知错误";
  } finally {
    操作中.value = false;
  }
}

async function 添加书院(): Promise<void> {
  const name = 书院新增.value.trim();
  if (!name) return;
  操作中.value = true;
  try {
    await api.academyAdd(name);
    书院新增.value = "";
    toastStore.push("已添加书院", { tone: "success" });
    await 刷新();
  } catch (e) {
    错误信息.value = e instanceof ApiError ? e.message : "添加书院失败：未知错误";
  } finally {
    操作中.value = false;
  }
}

async function 删除书院(id: number): Promise<void> {
  操作中.value = true;
  try {
    await api.academyDelete(id);
    toastStore.push("已删除书院", { tone: "success" });
    await 刷新();
  } catch (e) {
    错误信息.value = e instanceof ApiError ? e.message : "删除书院失败：未知错误";
  } finally {
    操作中.value = false;
  }
}

async function 移动书院(idx: number, delta: number): Promise<void> {
  const list = 书院对象列表.value.slice();
  const next = idx + delta;
  if (next < 0 || next >= list.length) return;
  const tmp = list[idx];
  list[idx] = list[next];
  list[next] = tmp;
  书院对象列表.value = list;

  操作中.value = true;
  try {
    await api.academiesOrderUpdate(list.map((x) => x.id));
    toastStore.push("已保存排序", { tone: "success" });
    await 刷新();
  } catch (e) {
    错误信息.value = e instanceof ApiError ? e.message : "保存排序失败：未知错误";
  } finally {
    操作中.value = false;
  }
}

async function 加载候选(): Promise<void> {
  if (!纠错.target) return;
  操作中.value = true;
  纠错.candidates = [];
  纠错.selectedSources = [];
  try {
    const res = await api.locationsCorrectionCandidates(纠错.target);
    纠错.candidates = res || [];
    toastStore.push(`已加载候选：${纠错.candidates.length} 条`, { tone: "success" });
  } catch (e) {
    错误信息.value = e instanceof ApiError ? e.message : "获取候选失败：未知错误";
  } finally {
    操作中.value = false;
  }
}

async function 执行纠错(): Promise<void> {
  const target = 纠错.target;
  const academy = 标准库映射.value[target];
  const merge = (纠错.selectedSources || []).slice();
  if (!target || !academy || !merge.length) return;
  操作中.value = true;
  try {
    const res = await api.locationsCorrect({ location: target, academy, merge_locations: merge });
    提示信息.value = `纠错完成：共影响 ${res.count} 条。`;
    toastStore.push("纠错已提交", { tone: "success" });
    await 刷新();
    纠错.candidates = [];
    纠错.selectedSources = [];
  } catch (e) {
    错误信息.value = e instanceof ApiError ? e.message : "纠错失败：未知错误";
  } finally {
    操作中.value = false;
  }
}

async function 自动扫描(): Promise<void> {
  扫描中.value = true;
  错误信息.value = "";
  提示信息.value = "";
  批量选择.value = [];
  try {
    const res = await api.locationsAutoCorrectScan();
    扫描结果.high_confidence = (res.high_confidence || []) as any[];
    扫描结果.manual_review = (res.manual_review || []) as any[];
    提示信息.value = `扫描完成：高置信度 ${扫描结果.high_confidence.length} 条；需人工确认 ${扫描结果.manual_review.length} 条。`;
    toastStore.push("扫描完成", { tone: "success" });
  } catch (e) {
    错误信息.value = e instanceof ApiError ? e.message : "扫描失败：未知错误";
  } finally {
    扫描中.value = false;
  }
}

function 构造批量纠错Payload(): Array<{ target: string; academy: string; sources: string[] }> {
  const picked = new Set(批量选择.value);
  const outByTarget: Record<string, { academy: string; sources: string[] }> = {};

  function add(target: string, source: string, academy: string): void {
    const t = String(target || "").trim();
    const s = String(source || "").trim();
    const a = String(academy || "").trim();
    if (!t || !s || !a) return;
    if (!outByTarget[t]) outByTarget[t] = { academy: a, sources: [] };
    outByTarget[t].sources.push(s);
  }

  扫描结果.high_confidence.forEach((it, idx) => {
    if (!picked.has(`H-${idx}`)) return;
    add(it.target, it.source, it.academy || 标准库映射.value[it.target] || "");
  });
  扫描结果.manual_review.forEach((it, idx) => {
    if (!picked.has(`M-${idx}`)) return;
    add(it.target, it.source, it.academy || 标准库映射.value[it.target] || "");
  });

  return Object.keys(outByTarget).map((k) => ({ target: k, academy: outByTarget[k].academy, sources: outByTarget[k].sources }));
}

async function 提交批量纠错(): Promise<void> {
  const corrections = 构造批量纠错Payload();
  if (!corrections.length) return;
  操作中.value = true;
  try {
    const res = await api.locationsBatchCorrect({ corrections });
    提示信息.value = `批量纠错完成：共影响 ${res.count} 条。`;
    toastStore.push("批量纠错已提交", { tone: "success" });
    await 刷新();
    批量选择.value = [];
  } catch (e) {
    错误信息.value = e instanceof ApiError ? e.message : "批量纠错失败：未知错误";
  } finally {
    操作中.value = false;
  }
}

onMounted(() => {
  void 刷新();
});
</script>

