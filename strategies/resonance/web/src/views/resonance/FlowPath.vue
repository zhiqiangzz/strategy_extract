<script setup lang="ts">
import { computed } from "vue";
import type { FlowData, FlowRuling, FlowStep } from "../../types";
import RoleDot from "./RoleDot.vue";

// The path this run took through the debate: evidence pack → opening statements →
// up to `maxRounds` rounds, each closed by a ruling → manager. Rounds that did not
// happen are shown dashed, so the reader sees where the debate stopped and who stopped it.
const props = defineProps<{ flow: FlowData }>();

interface RoundBox {
  round: number;
  held: boolean;
  steps: FlowStep[];
  ruling: FlowRuling | null;
}

const maxRounds = computed(() => Math.max(props.flow.config.maxRounds ?? 0, props.flow.rounds, 1));
const theses = computed(() => props.flow.steps.filter((s) => s.kind === "thesis"));
const rounds = computed<RoundBox[]>(() =>
  Array.from({ length: maxRounds.value }, (_, i) => {
    const round = i + 1;
    return {
      round,
      held: round <= props.flow.rounds,
      steps: props.flow.steps.filter((s) => s.round === round && s.kind !== "moderator"),
      ruling: props.flow.rulings.find((g) => g.round === round) ?? null
    };
  })
);

function rulingText(g: FlowRuling): string {
  const who = g.by === "moderator" ? "主持人" : "代码";
  if (!g.continue) return `${who}：终止`;
  return `${who}：继续` + (g.focus.length ? `，下一轮只辩 ${g.focus.join("、")}` : "");
}

const BOX = "flex min-w-0 flex-col gap-1.5 rounded-lg border border-solid border-border bg-surface px-3 py-2.5";
const TITLE = "text-xs font-semibold text-muted";
const ARROW = "self-center text-muted";
</script>

<template>
  <div class="flex flex-wrap items-stretch gap-2">
    <div :class="BOX">
      <span :class="TITLE">证据包</span>
      <span class="font-mono text-sm text-text">{{ flow.packDate }}</span>
      <span class="text-xs text-muted">技术指标 · 基本面 · 新闻 · 研报</span>
    </div>
    <span :class="ARROW" aria-hidden="true">→</span>
    <div :class="BOX">
      <span :class="TITLE">立论 · 两侧并行</span>
      <span v-for="s in theses" :key="s.id" class="inline-flex items-center gap-1.5 text-sm text-text">
        <RoleDot :role="s.role" small />{{ s.label }}
      </span>
    </div>
    <template v-for="r in rounds" :key="r.round">
      <span :class="ARROW" aria-hidden="true">→</span>
      <div v-if="r.held" :class="BOX">
        <span :class="TITLE">第 {{ r.round }} 轮 · 反驳后再反驳</span>
        <div class="flex flex-wrap gap-x-3 gap-y-1">
          <span v-for="s in r.steps" :key="s.id" class="inline-flex items-center gap-1.5 text-sm text-text">
            <RoleDot :role="s.role" small />{{ s.label }}
          </span>
        </div>
        <span v-if="r.ruling" class="inline-flex items-center gap-1.5 text-xs font-medium text-text">
          <RoleDot v-if="r.ruling.by === 'moderator'" role="mod" small />{{ rulingText(r.ruling) }}
        </span>
      </div>
      <div v-else class="flex flex-col justify-center gap-1 rounded-lg border border-dashed border-border px-3 py-2.5">
        <span :class="TITLE">第 {{ r.round }} 轮</span>
        <span class="text-xs text-muted">未进行</span>
      </div>
    </template>
    <span :class="ARROW" aria-hidden="true">→</span>
    <div :class="BOX">
      <span :class="TITLE">Manager 裁决</span>
      <span class="inline-flex items-center gap-1.5 text-sm font-semibold text-text">
        <RoleDot role="mgr" small />{{ flow.decision.direction }}
      </span>
      <span class="text-xs text-muted">置信度 {{ flow.decision.confidence }}</span>
    </div>
  </div>
</template>
