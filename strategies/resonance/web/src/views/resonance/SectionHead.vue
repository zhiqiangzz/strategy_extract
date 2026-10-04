<script setup lang="ts">
defineProps<{ title: string }>();
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <h2 class="m-0 text-xl font-semibold text-text">{{ title }}</h2>
    <p class="m-0 max-w-[46rem] text-sm text-muted"><slot /></p>
  </div>
</template>
