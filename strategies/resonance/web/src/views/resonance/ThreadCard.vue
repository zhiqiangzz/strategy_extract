<script setup lang="ts">
import type { FlowThread } from "../../types";
import EvidenceRefs from "./EvidenceRefs.vue";
import RoleDot from "./RoleDot.vue";
import TagPill from "./TagPill.vue";
import VerdictPill from "./VerdictPill.vue";
import { CLICKABLE, ROLE_NAME, SIDE_CHAR, onActivate } from "./roles";

// One argument and everything said about it. Collapsed: the claim, the chain of
// exchanges as tags, the ruling. Expanded: the full texts.
defineProps<{ thread: FlowThread; open: boolean }>();
const emit = defineEmits<{ toggle: [] }>();
</script>

<template>
  <div class="rounded-lg border border-solid border-border bg-surface">
    <div
      role="button"
      tabindex="0"
      :aria-expanded="open"
      :class="['flex flex-col gap-2 rounded-lg p-3.5 sm:p-4', CLICKABLE]"
      @click="emit('toggle')"
      @keydown="onActivate($event, () => emit('toggle'))"
    >
      <div class="flex flex-wrap items-center gap-2">
        <span class="font-mono text-sm font-semibold text-text">{{ thread.id }}</span>
        <span class="text-xs text-muted">强度 {{ thread.strength }} · {{ thread.status }}</span>
        <span class="ml-auto"><VerdictPill :value="thread.verdict" /></span>
      </div>
      <p class="m-0 text-sm text-text">{{ thread.claim }}</p>
      <div class="flex flex-wrap items-center gap-1.5 text-xs text-muted">
        <template v-for="(x, i) in thread.exchanges" :key="i">
          <span v-if="i > 0" aria-hidden="true">→</span>
          <span
            class="inline-flex items-center gap-1.5 rounded-full border border-solid border-border px-2 py-0.5 text-text"
          >
            <RoleDot :role="x.speaker" small />{{ SIDE_CHAR[x.speaker] }} · {{ x.tag }}
          </span>
        </template>
        <span class="ml-auto">{{ open ? "收起" : "展开交锋" }}</span>
      </div>
    </div>
    <div v-if="open" class="flex flex-col gap-4 border-t border-t-solid border-border p-3.5 sm:p-4">
      <div class="flex flex-col gap-2">
        <span class="text-xs font-semibold text-muted">推理</span>
        <p class="m-0 text-sm text-text">{{ thread.reasoning }}</p>
        <EvidenceRefs :refs="thread.refs" />
      </div>
      <div class="flex flex-col gap-4">
        <div v-for="(x, i) in thread.exchanges" :key="i" class="grid grid-cols-[0.75rem_minmax(0,1fr)] gap-x-2.5">
          <span class="pt-1.5"><RoleDot :role="x.speaker" /></span>
          <div class="flex min-w-0 flex-col gap-1.5">
            <div class="flex flex-wrap items-center gap-2 text-xs font-medium text-text">
              第 {{ x.round }} 轮 · {{ ROLE_NAME[x.speaker] }}{{ x.kind }}
              <TagPill>{{ x.tag }}</TagPill>
            </div>
            <p v-if="!x.unanswered" class="m-0 text-sm text-muted">{{ x.text }}</p>
            <p v-if="x.revised" class="m-0 rounded-lg bg-bg px-3 py-2 text-sm text-text">
              <span class="mr-2 text-xs text-muted">收窄后的论据</span>{{ x.revised }}
            </p>
            <EvidenceRefs :refs="x.refs" />
          </div>
        </div>
      </div>
      <div v-if="thread.verdict" class="flex flex-col gap-1.5 rounded-lg bg-bg p-3">
        <div class="flex items-center gap-2 text-xs font-semibold text-text">
          Manager 裁定<VerdictPill :value="thread.verdict" />
        </div>
        <p class="m-0 text-sm text-muted">{{ thread.verdictReason }}</p>
      </div>
    </div>
  </div>
</template>
