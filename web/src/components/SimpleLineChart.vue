<!--
  简易折线图（SVG 实现）

  为什么自己写：
  - 目前 web/ 依赖非常克制（仅 Vue + Router），不引入 ECharts/Chart.js；
  - 看板与趋势图只需要“能看懂”的基础折线即可；
  - 后续如需要更复杂交互，可以再替换为专业图表库。
-->
<template>
  <div class="图表卡片 卡片">
    <div class="图表标题区">
      <div class="图表标题">{{ title }}</div>
      <div v-if="subtitle" class="图表副标题 提示-次要">{{ subtitle }}</div>
    </div>

    <div class="图表容器">
      <svg :viewBox="`0 0 ${宽} ${高}`" class="图表SVG" role="img" aria-label="趋势图">
        <g>
          <line :x1="边距左" :y1="边距上" :x2="边距左" :y2="高 - 边距下" class="轴线" />
          <line :x1="边距左" :y1="高 - 边距下" :x2="宽 - 边距右" :y2="高 - 边距下" class="轴线" />
        </g>

        <g v-if="刻度列表.length">
          <g v-for="t in 刻度列表" :key="t.value">
            <line :x1="边距左" :y1="t.y" :x2="宽 - 边距右" :y2="t.y" class="网格线" />
            <text :x="边距左 - 8" :y="t.y + 4" class="刻度文字" text-anchor="end">{{ t.value }}</text>
          </g>
        </g>

        <Transition name="ui-fade" mode="out-in" appear>
          <g :key="渲染键">
            <g v-for="s in 归一化序列" :key="s.name">
              <polyline :points="s.points" class="折线" :style="{ stroke: s.color }" />
              <g v-for="p in s.dots" :key="p.key">
                <circle :cx="p.x" :cy="p.y" r="3.2" class="圆点" :style="{ fill: s.color }">
                  <title>{{ p.tip }}</title>
                </circle>
              </g>
            </g>
          </g>
        </Transition>
      </svg>
    </div>

    <div class="图例区" v-if="series.length">
      <div v-for="s in series" :key="s.name" class="图例项">
        <span class="图例色块" :style="{ background: s.color }" />
        <span>{{ s.name }}</span>
      </div>
    </div>

    <div v-if="!labels.length" class="提示-次要 小字">暂无数据</div>
  </div>
</template>

<script setup lang="ts">
/**
 * 简易折线图脚本
 *
 * 实现逻辑（核心思路）：
 * 1) 把 labels 当作 X 轴等距点；
 * 2) 把 series.values 合并求出全局最大值/最小值，用于 Y 轴比例；
 * 3) 把每个点映射到 SVG 坐标系，拼接成 polyline 的 points；
 * 4) 用 circle + title 提供最基本的 hover 值提示。
 */

import { computed } from "vue";

export type 折线序列 = {
  name: string;
  color: string;
  values: number[];
};

const props = defineProps<{
  title: string;
  subtitle?: string;
  labels: string[];
  series: 折线序列[];
}>();

const 宽 = 860;
const 高 = 240;

const 边距左 = 44;
const 边距右 = 18;
const 边距上 = 16;
const 边距下 = 28;

const 可绘制宽 = computed(() => 宽 - 边距左 - 边距右);
const 可绘制高 = computed(() => 高 - 边距上 - 边距下);

const 全部值 = computed(() => props.series.flatMap((s) => s.values.map((v) => (Number.isFinite(v) ? Number(v) : 0))));

const 最大值 = computed(() => {
  const arr = 全部值.value;
  if (!arr.length) return 0;
  return Math.max(...arr, 0);
});

const 最小值 = computed(() => {
  const arr = 全部值.value;
  if (!arr.length) return 0;
  return Math.min(...arr, 0);
});

const 刻度列表 = computed(() => {
  const max = 最大值.value;
  const min = 最小值.value;
  const range = Math.max(1, max - min);

  const ticks = 4;
  const out: Array<{ value: number; y: number }> = [];
  for (let i = 0; i <= ticks; i++) {
    const v = Math.round(min + (range * i) / ticks);
    const y = yFromValue(v);
    out.push({ value: v, y });
  }
  return out;
});

function xFromIndex(i: number): number {
  const n = Math.max(1, props.labels.length - 1);
  return 边距左 + (可绘制宽.value * i) / n;
}

function yFromValue(v: number): number {
  const max = 最大值.value;
  const min = 最小值.value;
  const range = Math.max(1, max - min);
  const t = (v - min) / range;
  return 边距上 + (1 - t) * 可绘制高.value;
}

const 归一化序列 = computed(() => {
  const labels = props.labels;
  return props.series.map((s) => {
    const points: string[] = [];
    const dots: Array<{ key: string; x: number; y: number; tip: string }> = [];
    for (let i = 0; i < labels.length; i++) {
      const v = Number(s.values[i] ?? 0) || 0;
      const x = xFromIndex(i);
      const y = yFromValue(v);
      points.push(`${x},${y}`);
      dots.push({ key: `${s.name}-${i}`, x, y, tip: `${labels[i]}：${s.name} ${v}` });
    }
    return { name: s.name, color: s.color, points: points.join(" "), dots };
  });
});

const 渲染键 = computed(() => {
  const labels = props.labels;
  const head = labels[0] || "";
  const tail = labels[labels.length - 1] || "";
  const seriesSig = props.series
    .map((s) => {
      const values = s.values || [];
      const v0 = values[0] ?? 0;
      const v1 = values[values.length - 1] ?? 0;
      return `${s.name}:${values.length}:${v0}:${v1}`;
    })
    .join("|");
  return `${labels.length}:${head}:${tail}:${seriesSig}`;
});
</script>

<style scoped>
.图表卡片 {
  padding: 14px;
  min-width: 0;
}

.图表标题区 {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.图表标题 {
  font-weight: 800;
}

.图表容器 {
  margin-top: 12px;
  width: 100%;
  overflow: auto;
  border-radius: 12px;
  border: var(--边框-卡片);
  background: var(--颜色-面板2);
}

.图表SVG {
  display: block;
  width: 860px;
  height: 240px;
}

.轴线 {
  stroke: rgba(255, 255, 255, 0.18);
  stroke-width: 1;
}

.网格线 {
  stroke: rgba(255, 255, 255, 0.06);
  stroke-width: 1;
}

.刻度文字 {
  fill: var(--颜色-次要文本);
  font-size: 11px;
}

.折线 {
  fill: none;
  stroke-width: 2.2;
}

.圆点 {
  stroke: rgba(0, 0, 0, 0.45);
  stroke-width: 1;
}

.图例区 {
  margin-top: 10px;
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
}

.图例项 {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--颜色-文本);
}

.图例色块 {
  width: 10px;
  height: 10px;
  border-radius: 3px;
}
</style>

