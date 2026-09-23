# Strategy summary template

> **Agents: follow the English part only (above the "中文版" divider). The Chinese part is a translation for human readers and adds no instructions. The skeleton to copy into the workspace is at the end of this file between the SKELETON-START and SKELETON-END markers.**
>
> **说明：agent 执行时只需参考上半部分的英文；下半部分的中文仅供人类阅读，内容相同。要复制到 workspace 的骨架在文件末尾 SKELETON-START 与 SKELETON-END 标记之间。**

## How to use

Copy the skeleton (between the markers at the end of this file) verbatim into `S2_summary_init.md`, replace `{strategy_name}`, and fill each section in Chinese. Keep every `<!-- section: ... -->` marker exactly as is: scripts locate sections by these markers. Do not bold anything before S5; from S5 onward wrap the canonical Chinese name of every `role=callback` term in `**bold**` and never bold anything else.

## What each section holds

1. **summary / 策略总结** — One or two paragraphs describing the whole strategy in prose: what market state it targets, how it gets in, how it manages the position, how it gets out. Written for a human reviewer.
2. **one_liner / 一句话概述** — A single sentence, e.g. "Major timeframe decides direction, minor timeframe times the entry, trailing stop protects profit, exit on stop or major reversal."
3. **premise / 策略前提与理念** — Bullet list of the beliefs and assumptions the strategy rests on (e.g. "cannot tell trend from range in real time, so do not try"; "30% win rate with 3:1 payoff is positive expectancy"). These become phase=philosophy terms later.
4. **execution_steps / 执行步骤** — Numbered steps in execution order. Each step names the decision being made and, from S5 on, bolds the callback term that makes it. This section and the next are what the downstream trading agent executes: be concrete about order and preconditions, and keep interpretation of ambiguous terms out of here (that lives in the term file).
5. **exit_and_risk / 出场与风控** — Every way a position can be closed or reduced, and every risk rule (initial stop placement, move-to-cost trigger, trailing rule, hard exits, position sizing). Each exit path must be consistent with the term definitions; S6 checks for contradictions here.
6. **scope_and_params / 适用范围与参数** — What the strategy applies to and the tunables: instruments / varieties, contract selection (main vs far month), timeframe pair, numeric parameters with defaults or ranges. Decisions from the S3 dialog such as "trade many varieties, main contract" are recorded here so that S4 can filter terms against them.

---

# 中文版（仅供人类阅读；agent 请参考上方英文）

## 用法

把文件末尾标记之间的骨架原样复制为 `S2_summary_init.md`，替换 `{strategy_name}`，用中文填写各节。保留每个 `<!-- section: ... -->` 标记，脚本靠它们定位章节。S5 之前不加粗任何内容；S5 起只有 `role=callback` 术语的规范中文名才能 `**加粗**`，其他一律不加粗。

## 各节内容

1. **策略总结** —— 一到两段散文完整描述策略：面向什么行情、如何入场、如何持仓、如何出场。给人读的。
2. **一句话概述** —— 一句话，例如"大周期定方向，小周期定入场时机，移动止损保利润，打止损或大周期反转出场"。
3. **策略前提与理念** —— 策略赖以成立的信念与前提，条目式（如"实时分不清趋势与震荡，所以不去判断""30% 胜率配 3:1 盈亏比是正期望"）。之后对应 phase=philosophy 的术语。
4. **执行步骤** —— 按执行顺序编号。每一步写明做什么决策，S5 起把做该决策的回调术语加粗。本节与下一节是下游交易 agent 真正执行的部分：顺序和前置条件要具体，对模糊术语的解释不要写在这里（写在术语文件里）。
5. **出场与风控** —— 所有平仓/减仓的途径和全部风控规则（初始止损位置、移损至成本的触发条件、移动止损规则、硬性出场、仓位）。每条出场路径都要与术语定义一致，S6 会在这里查矛盾。
6. **适用范围与参数** —— 适用对象与可调参数：品种、合约选择（主力/远月）、周期搭配、数值参数及其默认值或范围。S3 对话中"多品种、主力合约"之类的决定记录在这里，S4 据此过滤术语。

---

<!-- SKELETON-START -->
# 策略总结 — {strategy_name}

<!-- section: summary -->
## 1. 策略总结

<!-- section: one_liner -->
## 2. 一句话概述

<!-- section: premise -->
## 3. 策略前提与理念

<!-- section: execution_steps -->
## 4. 执行步骤

1. 

<!-- section: exit_and_risk -->
## 5. 出场与风控

- 

<!-- section: scope_and_params -->
## 6. 适用范围与参数

- 
<!-- SKELETON-END -->
