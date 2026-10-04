<script setup lang="ts">
import { computed } from "vue";
import type { FlowData } from "../../types";
import TagPill from "./TagPill.vue";

// What a run leaves under runs/<packDate>/<symbol>/ and one level above.
const props = defineProps<{ flow: FlowData }>();

interface FileRow {
  name: string;
  count: string;
  when: string;
  by: string;
  role: string;
  git: "忽略" | "跟踪";
}

const rows = computed<FileRow[]>(() => {
  const n = props.flow.steps.length + " 个";
  return [
    { name: "<步骤>.prompt.md", count: n, when: "每次调用返回后", by: "claude_cli.py", role: "发给模型的完整提示词。用来核对模型在这一步到底看到了什么。", git: "忽略" },
    { name: "<步骤>.response.json", count: n, when: "每次调用返回后", by: "claude_cli.py", role: "CLI 的原始返回：通过 schema 校验的结构化结果、起止时间、费用、重试次数。", git: "忽略" },
    {
      name: props.flow.cacheFile || "decision.<key>.json",
      count: "1 个",
      when: "Manager 返回后",
      by: "debate.py",
      role: "缓存：最终决策、双方立论、组装好的辩论记录、费用。同样条件重跑直接读它，不再调用模型。",
      git: "忽略"
    },
    { name: "debate.md", count: "1 个", when: "全部品种跑完后", by: "cli.py", role: "给人看的完整辩论记录：立论、每个线程的交锋与裁定、每轮的终止理由、Manager 的结论。", git: "跟踪" },
    { name: "flow.json", count: "1 个", when: "全部品种跑完后", by: "flow.py", role: "本页面的数据。模板不含数据，只读这个文件。", git: "跟踪" },
    { name: "../decisions.json", count: "全品种共用", when: "全部品种跑完后", by: "cli.py", role: "所有品种的决策、来源结论、立论、辩论、费用。cli report 靠它重新渲染报告、辩论记录和 flow.json。", git: "跟踪" },
    { name: "../report.md", count: "全品种共用", when: "全部品种跑完后", by: "cli.py", role: "总览表，加每个品种的理由、辩论进程和论据裁定表。", git: "跟踪" },
    { name: "../../index.json", count: "全部运行共用", when: "每次运行后", by: "flow.py", role: "有 flow.json 的包日期和品种列表，供本页面的日期与品种切换使用。", git: "跟踪" }
  ];
});

const TH = "border-b border-b-solid border-border px-4 py-3 text-left text-xs font-medium text-muted";
const TD = "border-b border-b-solid border-border px-4 py-3 align-top";
</script>

<template>
  <div class="overflow-x-auto rounded-lg border border-solid border-border bg-surface">
    <table class="w-full min-w-[760px] border-collapse text-sm">
      <thead>
        <tr>
          <th :class="TH">文件</th>
          <th :class="TH">何时写出</th>
          <th :class="TH">由谁写</th>
          <th :class="TH">作用</th>
          <th :class="TH">git</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="f in rows" :key="f.name">
          <td :class="TD">
            <span class="block font-mono text-xs font-medium text-text">{{ f.name }}</span>
            <span class="block text-xs text-muted">{{ f.count }}</span>
          </td>
          <td :class="[TD, 'whitespace-nowrap text-text']">{{ f.when }}</td>
          <td :class="[TD, 'whitespace-nowrap font-mono text-xs text-muted']">{{ f.by }}</td>
          <td :class="[TD, 'text-muted']">{{ f.role }}</td>
          <td :class="[TD, 'whitespace-nowrap']"><TagPill>{{ f.git }}</TagPill></td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
