<script setup lang="ts">
import { computed } from "vue";
import type { FlowData } from "../../types";
import FactItem from "./FactItem.vue";
import { money, seconds } from "./roles";

const props = defineProps<{ flow: FlowData }>();

const summed = computed(() => props.flow.steps.reduce((n, s) => n + (s.seconds ?? 0), 0));
const lastRuling = computed(() => props.flow.rulings[props.flow.rulings.length - 1] ?? null);
const endedBy = computed(() => {
  const g = lastRuling.value;
  if (!g) return "没有进行辩论";
  return g.by === "moderator" ? `第 ${g.round} 轮后主持人终止` : `第 ${g.round} 轮后代码终止`;
});
const reversal = computed(() => {
  const p = props.flow.position;
  if (!p) return "无持仓";
  return `持有 ${p.direction} ${p.volume} 手，反转 ${props.flow.decision.reversal ? "是" : "否"}`;
});
</script>

<template>
  <header class="flex flex-col gap-4">
    <div class="flex flex-col gap-2">
      <span class="font-mono text-xs text-muted">证据包 {{ flow.packDate }} · 决策时点为当日开盘前 · 最后交易日 {{ flow.lastSession || "—" }}</span>
      <h1 class="m-0 text-2xl font-semibold text-text sm:text-3xl">{{ flow.symbol }} {{ flow.name }} · 大周期辩论流程</h1>
      <p class="m-0 max-w-[46rem] text-sm text-muted">
        一次大周期方向判断，是 {{ flow.steps.length }} 次模型调用，加上调用之间的几段代码。下面依次是：这次运行走过的路径、每次调用的时间与内容、各条论据的交锋，以及留下的文件。
      </p>
    </div>
    <div
      class="grid grid-cols-2 gap-x-6 gap-y-4 border-y border-y-solid border-border py-4 sm:grid-cols-3 lg:grid-cols-6"
    >
      <FactItem label="结论" :value="flow.decision.direction" :note="'置信度 ' + flow.decision.confidence" />
      <FactItem label="辩论" :value="flow.rounds + ' 轮'" :note="endedBy" />
      <FactItem
        label="模型调用"
        :value="flow.steps.length + ' 次'"
        :note="[flow.config.model, flow.config.effort].filter(Boolean).join(' · ') || undefined"
      />
      <FactItem label="费用" :value="money(flow.cost)" />
      <FactItem
        label="耗时"
        :value="seconds(flow.wall)"
        :note="flow.wall != null ? '各步累计 ' + summed + ' 秒，两侧并行' : '逐次留痕不在本机'"
      />
      <FactItem label="证据质量" :value="flow.decision.quality" :note="reversal" />
    </div>
  </header>
</template>
