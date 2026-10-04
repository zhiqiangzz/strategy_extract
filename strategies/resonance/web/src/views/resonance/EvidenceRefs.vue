<script setup lang="ts">
defineProps<{ refs: string[] }>();
</script>

<template>
  <div v-if="refs.length" class="flex flex-wrap gap-1.5">
    <span
      v-for="r in refs"
      :key="r"
      class="rounded border border-solid border-border px-1.5 py-0.5 font-mono text-[11px] text-muted"
    >{{ r }}</span>
  </div>
</template>
