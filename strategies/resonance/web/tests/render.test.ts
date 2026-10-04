import { readdirSync, readFileSync, existsSync } from "node:fs";
import { join, resolve } from "node:path";
import { createSSRApp } from "vue";
import { renderToString } from "vue/server-renderer";
import { describe, expect, it } from "vitest";
import DebateFlowView from "../src/views/resonance/DebateFlowView.vue";
import { FLOW_SCHEMA, type FlowData } from "../src/types";

// The template is checked by rendering it to HTML with real-shaped data:
// tests/fixtures/flow.sample.json is produced by the judge's own code
// (strategies/resonance/tests/make_web_fixture.py), so a field the template reads
// but flow.py no longer writes shows up here as "undefined" in the output.

function load(path: string): FlowData {
  return JSON.parse(readFileSync(path, "utf-8")) as FlowData;
}

async function render(flow: FlowData, props: { initialStep?: string; initialThread?: string } = {}): Promise<string> {
  const html = await renderToString(createSSRApp(DebateFlowView, { flow, ...props }));
  for (const leak of ["undefined", "NaN", "[object Object]", ">null<", ">false<"]) {
    expect(html, `rendered output contains ${leak}`).not.toContain(leak);
  }
  return html;
}

const sample = load(resolve(__dirname, "fixtures/flow.sample.json"));

describe("DebateFlowView", () => {
  it("renders the sample run: path, timeline, steps, threads, files", async () => {
    expect(sample.schema).toBe(FLOW_SCHEMA);
    const html = await render(sample);
    expect(html).toContain("CU 沪铜 · 大周期辩论流程");
    expect(html).toContain("12 次调用的时间线");
    expect(html).toContain("第 3 轮 · 反驳后再反驳");
    expect(html).toContain("代码：终止");
    expect(html).toContain("主持人：继续，下一轮只辩 多1");
    expect(html).toContain("第 2 轮 · 空方反驳");
    expect(html).toContain("3 条论据的交锋");
    expect(html).toContain("持有 short 2 手，反转 是");
    expect(html).toContain(sample.cacheFile);
    // one bar per timed call, on a real time axis
    expect(html.match(/role="button" tabindex="0" aria-pressed/g)?.length).toBe(sample.steps.length);
    expect(html).toContain("08:46");
  });

  it("renders every call's detail and every thread opened", async () => {
    for (const step of sample.steps) {
      const html = await render(sample, { initialStep: step.id });
      expect(html).toContain(`${step.id}.response.json`);
      expect(html).toContain(step.result);
    }
    for (const thread of sample.threads) {
      const html = await render(sample, { initialThread: thread.id });
      expect(html).toContain("收起");
      expect(html).toContain(thread.reasoning);
    }
  });

  it("still renders a run whose per-call records are gone", async () => {
    const bare: FlowData = {
      ...sample,
      wall: null,
      clock0: null,
      cacheFile: "",
      steps: sample.steps.map((s) => ({
        ...s, start: null, end: null, t0: null, t1: null, seconds: null, cost: null, attempts: null, promptChars: null, blocks: []
      }))
    };
    const html = await render(bare);
    expect(html).toContain("无法绘制时间线");
    expect(html).toContain("这一步的提示词留痕不在本机");
    expect(html).not.toContain('aria-pressed');
  });

  it("renders every real flow.json found under runs/", async () => {
    const runs = resolve(__dirname, "../../runs");
    const files: string[] = [];
    for (const date of existsSync(runs) ? readdirSync(runs) : []) {
      const dateDir = join(runs, date);
      if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) continue;
      for (const sym of readdirSync(dateDir)) {
        const f = join(dateDir, sym, "flow.json");
        if (existsSync(f)) files.push(f);
      }
    }
    for (const f of files) {
      const flow = load(f);
      const html = await render(flow, { initialThread: flow.threads[0]?.id });
      expect(html, f).toContain(`${flow.symbol} ${flow.name}`);
    }
  });
});
