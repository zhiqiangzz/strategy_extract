<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { fetchFlow, fetchIndex } from "./api";
import type { FlowData, FlowIndex } from "./types";
import DebateFlowView from "./views/resonance/DebateFlowView.vue";

// Standalone shell: pick a pack date and a symbol from runs/index.json, load that
// flow.json and hand it to DebateFlowView. The choice lives in the URL hash
// (#2026-09-30/LC) so a view can be linked. Inside another frontend, replace this
// shell with that app's own routing and keep DebateFlowView as it is.
const index = ref<FlowIndex | null>(null);
const flow = ref<FlowData | null>(null);
const packDate = ref("");
const symbol = ref("");
const loading = ref(true);
const error = ref("");

const symbols = computed(() => index.value?.runs.find((r) => r.packDate === packDate.value)?.symbols ?? []);

function fromHash(): { packDate: string; symbol: string } | null {
  const m = /^#(\d{4}-\d{2}-\d{2})\/([A-Za-z0-9]+)$/.exec(window.location.hash);
  return m ? { packDate: m[1], symbol: m[2] } : null;
}

async function show(date: string, sym: string): Promise<void> {
  packDate.value = date;
  symbol.value = sym;
  loading.value = true;
  error.value = "";
  try {
    flow.value = await fetchFlow(date, sym);
    const hash = `#${date}/${sym}`;
    if (window.location.hash !== hash) window.history.replaceState(null, "", hash);
  } catch (e) {
    flow.value = null;
    error.value = e instanceof Error ? e.message : String(e);
  } finally {
    loading.value = false;
  }
}

function pickDate(date: string): void {
  const first = index.value?.runs.find((r) => r.packDate === date)?.symbols[0];
  if (first) void show(date, first.symbol);
}

function onHashChange(): void {
  const h = fromHash();
  if (h && (h.packDate !== packDate.value || h.symbol !== symbol.value)) void show(h.packDate, h.symbol);
}

onMounted(async () => {
  window.addEventListener("hashchange", onHashChange);
  try {
    index.value = await fetchIndex();
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
    loading.value = false;
    return;
  }
  const wanted = fromHash();
  const run = index.value.runs.find((r) => r.packDate === wanted?.packDate) ?? index.value.runs[0];
  const sym = run?.symbols.find((s) => s.symbol === wanted?.symbol) ?? run?.symbols[0];
  if (run && sym) {
    await show(run.packDate, sym.symbol);
  } else {
    loading.value = false;
  }
});
onBeforeUnmount(() => window.removeEventListener("hashchange", onHashChange));
</script>

<template>
  <div class="mx-auto flex max-w-[76rem] flex-col gap-8 px-4 py-6 sm:px-6 lg:py-10">
    <div v-if="index && index.runs.length" class="flex flex-wrap items-center gap-x-4 gap-y-3 text-sm">
      <label class="flex items-center gap-2">
        <span class="text-muted">证据包</span>
        <select
          id="pack-date"
          class="rounded border border-solid border-border bg-surface px-2 py-1 text-sm text-text"
          :value="packDate"
          @change="pickDate(($event.target as HTMLSelectElement).value)"
        >
          <option v-for="r in index.runs" :key="r.packDate" :value="r.packDate">{{ r.packDate }}</option>
        </select>
      </label>
      <div class="flex flex-wrap items-center gap-2">
        <span class="text-muted">品种</span>
        <a
          v-for="s in symbols"
          :key="s.symbol"
          :href="`#${packDate}/${s.symbol}`"
          :aria-current="s.symbol === symbol ? 'page' : undefined"
          :class="[
            'inline-flex items-baseline gap-1.5 rounded border border-solid px-2.5 py-1 no-underline',
            s.symbol === symbol ? 'border-primary bg-surface text-text' : 'border-border text-muted hover:bg-surface'
          ]"
        >
          <span class="font-mono text-sm font-semibold text-text">{{ s.symbol }}</span>
          <span class="text-xs">{{ s.direction }} {{ s.confidence }}</span>
        </a>
      </div>
    </div>

    <p v-if="loading" class="m-0 text-sm text-muted">正在读取数据…</p>
    <div v-else-if="error" class="flex flex-col gap-1 rounded-lg border border-solid border-border bg-surface p-4 text-sm">
      <span class="font-semibold text-text">读取数据失败</span>
      <span class="font-mono text-xs text-muted">{{ error }}</span>
      <span class="text-muted">页面需要通过 `cli web` 提供的服务打开，数据在 runs/index.json 和 runs/&lt;包日期&gt;/&lt;品种&gt;/flow.json。</span>
    </div>
    <div v-else-if="!flow" class="rounded-lg border border-dashed border-border p-6 text-sm text-muted">
      还没有任何运行的数据。执行一次 `cli judge` 之后，这里会列出它的包日期和品种。
    </div>
    <DebateFlowView v-else :flow="flow" />
  </div>
</template>
