<script setup lang="ts">
defineProps<{ label: string; value: string; note?: string }>();
</script>

<template>
  <div class="flex min-w-0 flex-col gap-0.5">
    <span class="text-xs text-muted">{{ label }}</span>
    <span class="text-base font-semibold text-text">{{ value }}</span>
    <span v-if="note" class="text-xs text-muted">{{ note }}</span>
  </div>
</template>
