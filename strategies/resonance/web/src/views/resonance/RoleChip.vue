<script setup lang="ts">
import type { Role } from "../../types";
import RoleDot from "./RoleDot.vue";

defineProps<{ role: Role }>();
</script>

<template>
  <span
    class="inline-flex items-center gap-1.5 rounded-full border border-solid border-border bg-surface px-2.5 py-1 text-xs font-medium text-text"
  >
    <RoleDot :role="role" small />
    <slot />
  </span>
</template>
