<script setup lang="ts">
import { computed, ref } from "vue";
import type { FlowData, FlowStep, Role } from "../../types";
import RoleDot from "./RoleDot.vue";
import { CLICKABLE, LANES, ROLE_BG, ROLE_NAME, clock, money, onActivate, stepTitle } from "./roles";

// The calls on a real time axis, one lane per speaker. Bar length is the call's
// duration; the two sides of a stage start together. Hover or focus shows a call in
// the readout; click selects it for the detail panel.
const props = defineProps<{ flow: FlowData; selected: string }>();
const emit = defineEmits<{ select: [id: string] }>();

const hover = ref<string | null>(null);
const timed = computed(() => props.flow.steps.filter((s) => s.t0 != null && s.t1 != null));
const hasTimeline = computed(() => props.flow.clock0 != null && timed.value.length > 0);

// Axis domain in seconds of the day, widened to 30-second boundaries.
const domain = computed(() => {
  const c0 = props.flow.clock0 ?? 0;
  const last = Math.max(0, ...timed.value.map((s) => s.t1 as number));
  const d0 = Math.floor(c0 / 30) * 30;
  const d1 = Math.max(Math.ceil((c0 + last) / 30) * 30, d0 + 60);
  return { c0, d0, d1 };
});

function pct(t: number): number {
  const { c0, d0, d1 } = domain.value;
  return ((c0 + t - d0) / (d1 - d0)) * 100;
}

const ticks = computed(() => {
  const { d0, d1 } = domain.value;
  const span = d1 - d0;
  const step = span <= 600 ? 60 : span <= 1200 ? 120 : span <= 3600 ? 300 : 600;
  const out: { left: number; label: string }[] = [];
  for (let t = Math.ceil(d0 / step) * step; t <= d1; t += step) {
    out.push({ left: ((t - d0) / span) * 100, label: clock(t) });
  }
  return out;
});

const bands = computed(() =>
  Array.from({ length: props.flow.rounds }, (_, i) => i + 1)
    .map((round) => {
      const steps = timed.value.filter((s) => s.round === round);
      if (!steps.length) return null;
      const left = pct(Math.min(...steps.map((s) => s.t0 as number)));
      const right = pct(Math.max(...steps.map((s) => s.t1 as number)));
      return { round, left, width: right - left };
    })
    .filter((b): b is { round: number; left: number; width: number } => b !== null)
);

const shown = computed<FlowStep | undefined>(
  () => props.flow.steps.find((s) => s.id === (hover.value ?? props.selected)) ?? props.flow.steps[0]
);

function barsOf(role: Role): FlowStep[] {
  return timed.value.filter((s) => s.role === role);
}

function barStyle(s: FlowStep): Record<string, string> {
  const left = pct(s.t0 as number);
  return { left: left + "%", width: `max(6px, ${pct(s.t1 as number) - left}%)` };
}

function barLabel(s: FlowStep): string {
  return s.role === "mod" || s.role === "mgr" ? "" : s.phase;
}

function describe(s: FlowStep): string {
  return `${stepTitle(s, props.flow.rounds)}，${s.start} 到 ${s.end}，${s.seconds} 秒，${money(s.cost)}`;
}
</script>

<template>
  <div class="flex flex-col gap-3 rounded-lg border border-solid border-border bg-surface p-4 sm:p-5">
    <template v-if="hasTimeline && shown">
      <div class="flex min-h-7 flex-wrap items-baseline gap-x-3 gap-y-1 text-sm">
        <span class="text-lg font-semibold text-text">{{ shown.seconds ?? "—" }} 秒</span>
        <span class="text-text">{{ money(shown.cost) }}</span>
        <span class="inline-flex items-center gap-1.5 text-muted">
          <RoleDot :role="shown.role" />{{ stepTitle(shown, flow.rounds) }}
        </span>
        <span class="font-mono text-xs tabular-nums text-muted">{{ shown.start ?? "—" }} → {{ shown.end ?? "—" }}</span>
      </div>
      <div class="overflow-x-auto">
        <div class="grid min-w-[640px] grid-cols-[4.5rem_minmax(0,1fr)] gap-x-3 pb-1">
          <div class="flex h-7 items-center text-xs text-muted">轮次</div>
          <div class="relative h-7">
            <div
              v-for="b in bands"
              :key="b.round"
              class="absolute top-1 flex h-5 items-center justify-center overflow-hidden rounded bg-bg text-[11px] text-muted"
              :style="{ left: b.left + '%', width: b.width + '%' }"
            >第 {{ b.round }} 轮</div>
          </div>
          <template v-for="role in LANES" :key="role">
            <div class="flex h-12 items-start gap-1.5 border-t border-t-solid border-border pt-2 text-xs font-medium text-text">
              <span class="pt-0.5"><RoleDot :role="role" /></span>{{ ROLE_NAME[role] }}
            </div>
            <div class="relative h-12 border-t border-t-solid border-border">
              <span
                v-for="t in ticks"
                :key="t.label"
                class="absolute bottom-0 top-0 w-px bg-border"
                :style="{ left: t.left + '%' }"
              ></span>
              <div
                v-for="s in barsOf(role)"
                :key="s.id"
                role="button"
                tabindex="0"
                :aria-pressed="selected === s.id"
                :aria-label="describe(s)"
                :class="['group absolute top-1.5 flex h-10 flex-col items-start gap-1', CLICKABLE]"
                :style="barStyle(s)"
                @mouseenter="hover = s.id"
                @mouseleave="hover = null"
                @focus="hover = s.id"
                @blur="hover = null"
                @click="emit('select', s.id)"
                @keydown="onActivate($event, () => emit('select', s.id))"
              >
                <span
                  :class="[
                    'block h-5 w-full rounded',
                    ROLE_BG[role],
                    selected === s.id
                      ? 'outline outline-2 outline-offset-2 outline-text'
                      : 'opacity-85 group-hover:opacity-100'
                  ]"
                ></span>
                <span class="whitespace-nowrap text-[11px] leading-none text-muted">{{ barLabel(s) }}</span>
              </div>
            </div>
          </template>
          <div class="border-t border-t-solid border-border"></div>
          <div class="relative h-6 border-t border-t-solid border-border">
            <span
              v-for="t in ticks"
              :key="t.label"
              class="absolute top-1.5 -translate-x-1/2 text-[11px] tabular-nums text-muted"
              :style="{ left: t.left + '%' }"
            >{{ t.label }}</span>
          </div>
        </div>
      </div>
      <p class="m-0 text-xs text-muted">
        横轴是真实时间，色条长度就是这次调用的耗时。同一阶段的多方和空方同时发出，等两侧都返回后才进入下一阶段。点任一色条看这一步的提示词和返回结果。
      </p>
    </template>
    <p v-else class="m-0 text-sm text-muted">
      这次运行的逐次调用留痕（*.response.json）不在本机，无法绘制时间线。调用顺序和内容见下方列表。
    </p>
  </div>
</template>
