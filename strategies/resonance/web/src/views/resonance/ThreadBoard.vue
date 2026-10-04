<script setup lang="ts">
import { ref, watch } from "vue";
import type { FlowData, Side } from "../../types";
import RoleChip from "./RoleChip.vue";
import ThreadCard from "./ThreadCard.vue";
import { ROLE_NAME } from "./roles";

// Both sides' arguments side by side; one thread open at a time.
const props = defineProps<{ flow: FlowData; initialThread?: string }>();

const SIDES: Side[] = ["long", "short"];
const open = ref<string | null>(props.initialThread ?? null);
watch(
  () => props.flow,
  () => {
    open.value = null;
  }
);
</script>

<template>
  <div class="grid gap-6 lg:grid-cols-2">
    <div v-for="side in SIDES" :key="side" class="flex min-w-0 flex-col gap-3">
      <div class="flex flex-col gap-2">
        <div class="flex flex-wrap items-center gap-2">
          <RoleChip :role="side">{{ ROLE_NAME[side] }}立论</RoleChip>
          <span v-if="flow.theses[side]" class="text-xs text-muted">自评置信度 {{ flow.theses[side]!.confidence }}</span>
        </div>
        <p v-if="flow.theses[side]" class="m-0 line-clamp-4 text-sm text-muted">{{ flow.theses[side]!.thesis }}</p>
      </div>
      <ThreadCard
        v-for="t in flow.threads.filter((x) => x.owner === side)"
        :key="t.id"
        :thread="t"
        :open="open === t.id"
        @toggle="open = open === t.id ? null : t.id"
      />
    </div>
  </div>
</template>
