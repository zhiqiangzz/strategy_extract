<script setup lang="ts">
import { VERDICT_MARK } from "./roles";

// The manager's ruling on one point. Deliberately not colored: red and green
// already mean 多方 and 空方 on this page.
defineProps<{ value: string | null }>();
</script>

<template>
  <span
    v-if="value"
    class="inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded-full border border-solid border-muted px-2 py-0.5 text-xs font-medium text-text"
  >
    <span aria-hidden="true">{{ VERDICT_MARK[value] ?? "·" }}</span>
    {{ value }}
  </span>
</template>
