<script setup lang="ts">
import type { FlowStep } from "../../types";
import FactItem from "./FactItem.vue";
import RoleChip from "./RoleChip.vue";
import TagPill from "./TagPill.vue";
import { money, seconds, stepTitle } from "./roles";

// One call: what it was asked, when it ran, what its prompt was made of and what came back.
defineProps<{ step: FlowStep; rounds: number }>();

function share(part: number, whole: number | null): string {
  return Math.max(1, whole ? (part / whole) * 100 : 0) + "%";
}
</script>

<template>
  <div class="flex min-w-0 flex-col gap-5 rounded-lg border border-solid border-border bg-surface p-4 sm:p-5">
    <div class="flex flex-col gap-2">
      <div class="flex flex-wrap items-center gap-2">
        <RoleChip :role="step.role">{{ stepTitle(step, rounds) }}</RoleChip>
        <span class="font-mono text-xs text-muted">模板 prompts/{{ step.template }}</span>
      </div>
      <p class="m-0 text-sm text-text">{{ step.job }}</p>
    </div>
    <div class="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4">
      <FactItem label="发出" :value="step.start ?? '—'" />
      <FactItem label="返回" :value="step.end ?? '—'" />
      <FactItem label="耗时" :value="seconds(step.seconds)" />
      <FactItem
        label="费用"
        :value="money(step.cost)"
        :note="step.attempts == null ? undefined : step.attempts > 1 ? '重试 ' + (step.attempts - 1) + ' 次' : '一次通过'"
      />
    </div>
    <div class="flex flex-col gap-3">
      <div class="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h3 class="m-0 text-sm font-semibold text-text">提示词里装了什么</h3>
        <span v-if="step.promptChars != null" class="font-mono text-[11px] text-muted">
          {{ step.id }}.prompt.md · {{ step.promptChars.toLocaleString("en-US") }} 字符
        </span>
      </div>
      <div v-if="step.blocks.length" class="flex flex-col gap-2.5">
        <div
          v-for="(b, i) in step.blocks"
          :key="i"
          class="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-x-3 gap-y-1"
        >
          <div class="min-w-0">
            <span class="text-sm font-medium text-text">{{ b.label }}</span>
            <span class="ml-2 text-xs text-muted">{{ b.note }}</span>
          </div>
          <span class="text-xs tabular-nums text-muted">{{ b.chars.toLocaleString("en-US") }}</span>
          <div class="col-span-2 h-1.5 rounded-full bg-bg">
            <div class="h-1.5 rounded-full bg-muted" :style="{ width: share(b.chars, step.promptChars) }"></div>
          </div>
        </div>
      </div>
      <p v-else class="m-0 text-sm text-muted">这一步的提示词留痕不在本机。</p>
    </div>
    <div class="flex flex-col gap-3">
      <div class="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h3 class="m-0 text-sm font-semibold text-text">模型返回了什么</h3>
        <span class="font-mono text-[11px] text-muted">{{ step.id }}.response.json</span>
      </div>
      <p class="m-0 text-sm text-text">{{ step.result }}</p>
      <div class="flex flex-col gap-2.5">
        <div v-for="(it, i) in step.items" :key="i" class="grid grid-cols-[2.5rem_minmax(0,1fr)] gap-x-2">
          <span class="pt-0.5 font-mono text-xs font-semibold text-text">{{ it.id }}</span>
          <div class="flex min-w-0 flex-col items-start gap-1">
            <TagPill>{{ it.tag }}</TagPill>
            <p v-if="it.text" class="m-0 text-sm text-muted">{{ it.text }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
