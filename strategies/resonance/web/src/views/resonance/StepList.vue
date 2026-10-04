<script setup lang="ts">
import type { FlowData } from "../../types";
import RoleDot from "./RoleDot.vue";
import { CLICKABLE, onActivate, seconds, stepTitle } from "./roles";

// The calls in order. The indented rows tagged 代码 are what debate.py did between
// two calls, without the model.
defineProps<{ flow: FlowData; selected: string }>();
const emit = defineEmits<{ select: [id: string] }>();
</script>

<template>
  <div class="flex min-w-0 flex-col gap-1">
    <template v-for="(s, i) in flow.steps" :key="s.id">
      <div
        role="button"
        tabindex="0"
        :aria-current="selected === s.id ? 'step' : undefined"
        :class="[
          'flex items-center gap-2.5 rounded-lg border border-solid px-2.5 py-2',
          CLICKABLE,
          selected === s.id ? 'border-primary bg-surface' : 'border-transparent hover:bg-surface'
        ]"
        @click="emit('select', s.id)"
        @keydown="onActivate($event, () => emit('select', s.id))"
      >
        <span class="w-5 shrink-0 text-xs tabular-nums text-muted">{{ i + 1 }}</span>
        <RoleDot :role="s.role" />
        <span class="flex min-w-0 flex-1 flex-col">
          <span class="text-sm font-medium text-text">{{ stepTitle(s, flow.rounds) }}</span>
          <span class="truncate font-mono text-[11px] text-muted">{{ s.id }}</span>
        </span>
        <span class="flex shrink-0 flex-col items-end">
          <span class="text-xs tabular-nums text-text">{{ seconds(s.seconds) }}</span>
          <span class="font-mono text-[11px] tabular-nums text-muted">{{ s.end ?? "" }}</span>
        </span>
      </div>
      <div
        v-if="s.glue"
        class="ml-5 flex gap-2 border-l border-l-solid border-border py-1.5 pl-4 text-xs text-muted"
      >
        <span class="h-fit shrink-0 rounded border border-solid border-border px-1 text-[10px] leading-4">代码</span>
        <span class="min-w-0">{{ s.glue }}</span>
      </div>
    </template>
  </div>
</template>
