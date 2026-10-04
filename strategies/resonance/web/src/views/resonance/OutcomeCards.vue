<script setup lang="ts">
import { computed } from "vue";
import type { FlowData } from "../../types";
import RoleChip from "./RoleChip.vue";

// How the debate ended (one ruling per round) and what the manager made of it.
const props = defineProps<{ flow: FlowData }>();

const reasoning = computed(() => props.flow.decision.reasoning.replace(/\*\*/g, ""));
</script>

<template>
  <div class="grid items-start gap-4 lg:grid-cols-2">
    <div class="flex min-w-0 flex-col gap-3 rounded-lg border border-solid border-border bg-surface p-4 sm:p-5">
      <div><RoleChip role="mod">辩论为什么到此为止</RoleChip></div>
      <div v-for="g in flow.rulings" :key="g.round" class="flex flex-col gap-1">
        <span class="text-xs font-semibold text-text">
          第 {{ g.round }} 轮后 · {{ g.by === "moderator" ? "主持人" : "代码" }}：{{ g.continue ? "继续" : "终止" }}
          <template v-if="g.focus.length">（下一轮只辩 {{ g.focus.join("、") }}）</template>
        </span>
        <p class="m-0 text-sm text-muted">{{ g.reason }}</p>
      </div>
      <p v-if="!flow.rulings.length" class="m-0 text-sm text-muted">双方均未提出论据，没有进行辩论。</p>
    </div>
    <div class="flex min-w-0 flex-col gap-3 rounded-lg border border-solid border-border bg-surface p-4 sm:p-5">
      <div><RoleChip role="mgr">Manager：{{ flow.decision.direction }}，置信度 {{ flow.decision.confidence }}</RoleChip></div>
      <p v-if="flow.decision.summary" class="m-0 text-sm text-text">{{ flow.decision.summary }}</p>
      <div v-if="flow.decision.drivers.length" class="flex flex-col gap-1">
        <span class="text-xs font-semibold text-muted">关键论据</span>
        <span v-for="d in flow.decision.drivers" :key="d" class="font-mono text-xs text-text">{{ d }}</span>
      </div>
      <div v-if="flow.decision.risks.length" class="flex flex-col gap-1">
        <span class="text-xs font-semibold text-muted">风险</span>
        <span v-for="r in flow.decision.risks" :key="r" class="text-sm text-muted">{{ r }}</span>
      </div>
      <details v-if="reasoning">
        <summary class="cursor-pointer text-xs font-semibold text-muted">完整理由</summary>
        <p class="m-0 mt-2 whitespace-pre-line text-sm text-text">{{ reasoning }}</p>
      </details>
    </div>
  </div>
</template>
