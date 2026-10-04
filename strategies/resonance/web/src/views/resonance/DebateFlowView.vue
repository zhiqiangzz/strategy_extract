<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { FlowData } from "../../types";
import CallTimeline from "./CallTimeline.vue";
import FileTable from "./FileTable.vue";
import FlowHeader from "./FlowHeader.vue";
import FlowPath from "./FlowPath.vue";
import OutcomeCards from "./OutcomeCards.vue";
import SectionHead from "./SectionHead.vue";
import StepDetail from "./StepDetail.vue";
import StepList from "./StepList.vue";
import ThreadBoard from "./ThreadBoard.vue";

// One symbol's judgement, end to end, rendered from a flow.json. The component
// holds no data of its own: pass it a FlowData and it shows that run.
// `initialStep` / `initialThread` preselect a call and an open thread (used by tests).
const props = defineProps<{ flow: FlowData; initialStep?: string; initialThread?: string }>();

const selected = ref(props.initialStep ?? props.flow.steps[0]?.id ?? "");
watch(
  () => props.flow,
  (flow) => {
    selected.value = flow.steps[0]?.id ?? "";
  }
);
const step = computed(() => props.flow.steps.find((s) => s.id === selected.value) ?? props.flow.steps[0]);
</script>

<template>
  <div class="flex flex-col gap-12 text-sm leading-relaxed text-text">
    <FlowHeader :flow="flow" />

    <section class="flex flex-col gap-4">
      <SectionHead title="这次运行走过的路径">
        辩论最多 {{ flow.config.maxRounds ?? 3 }} 轮。每轮先由对方逐条反驳，再由论据所有方逐条回应；一轮结束后，只要还有争议线程且没到上限，就由主持人决定是否再打一轮。虚线框是没有发生的轮次。
      </SectionHead>
      <FlowPath :flow="flow" />
    </section>

    <section class="flex flex-col gap-4">
      <SectionHead :title="flow.steps.length + ' 次调用的时间线'">
        每个色条是一次模型调用，颜色表示谁在说话。下方列表按顺序列出调用，夹在中间的「代码」行是两次调用之间由 debate.py 完成的事，不经过模型。
      </SectionHead>
      <CallTimeline :flow="flow" :selected="selected" @select="selected = $event" />
      <div class="grid gap-5 lg:grid-cols-[minmax(0,21rem)_minmax(0,1fr)]">
        <StepList :flow="flow" :selected="selected" @select="selected = $event" />
        <StepDetail v-if="step" :step="step" :rounds="flow.rounds" />
      </div>
    </section>

    <section class="flex flex-col gap-4">
      <SectionHead :title="flow.threads.length + ' 条论据的交锋'">
        立论里的每条论据成为一个线程。对方先反驳并指明攻击类型，所有方再回应，最后由 Manager 逐条裁定。标签链上的「多」「空」表示这一步是谁说的。
      </SectionHead>
      <ThreadBoard :flow="flow" :initial-thread="initialThread" />
      <OutcomeCards :flow="flow" />
    </section>

    <section class="flex flex-col gap-4">
      <SectionHead title="留下的文件">
        下表的路径相对于 runs/{{ flow.packDate }}/{{ flow.symbol }}/。逐次调用的提示词与响应只留在跑这次判断的机器上，不进 git。
      </SectionHead>
      <FileTable :flow="flow" />
    </section>
  </div>
</template>
