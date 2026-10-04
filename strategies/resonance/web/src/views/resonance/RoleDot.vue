<script setup lang="ts">
import type { Role } from "../../types";
import { ROLE_BG } from "./roles";

defineProps<{ role: Role; small?: boolean }>();
</script>

<template>
  <span :class="['inline-block shrink-0 rounded-full', small ? 'h-2 w-2' : 'h-2.5 w-2.5', ROLE_BG[role]]"></span>
</template>
