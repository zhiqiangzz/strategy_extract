# Strategy summary / 策略总结 — {strategy_name}

> Agents: read the English guidance in this template only; the Chinese lines are for human readers. In the generated file, write section bodies in Chinese (the user's language) unless the user asks otherwise. Keep every `<!-- section: ... -->` marker exactly as is: scripts locate sections by these markers. From S5 onward, wrap the canonical Chinese name of every role=callback term in `**bold**` and never bold anything else.
>
> 说明：请保留每个 `<!-- section: ... -->` 标记，脚本靠它们定位章节。S5 之后，只有 role=callback 的术语才能用 `**加粗**`，其他内容一律不加粗。

<!-- section: summary -->
## 1. Strategy summary / 策略总结

_(EN guidance) One or two paragraphs describing the whole strategy in prose: what market state it targets, how it gets in, how it manages the position, how it gets out. Written for a human reviewer._

_（中文）用一到两段散文完整描述策略：面向什么行情、如何入场、如何持仓、如何出场。给人读的。_

<!-- section: one_liner -->
## 2. One-line overview / 一句话概述

_(EN guidance) A single sentence, e.g. "Major timeframe decides direction, minor timeframe times the entry, trailing stop protects profit, exit on stop or major reversal."_

_（中文）一句话，例如"大周期定方向，小周期定入场时机，移动止损保利润，打止损或大周期反转出场"。_

<!-- section: premise -->
## 3. Premise and philosophy / 策略前提与理念

_(EN guidance) Bullet list of the beliefs and assumptions the strategy rests on (e.g. "cannot tell trend from range in real time, so do not try"; "30% win rate with 3:1 payoff is positive expectancy"). These are role=philosophy terms later._

_（中文）策略赖以成立的信念与前提，条目式。之后多对应 phase=philosophy 的术语。_

<!-- section: execution_steps -->
## 4. Execution steps / 执行步骤

_(EN guidance) Numbered steps in execution order. Each step names the decision being made and, from S5 on, bolds the callback term that makes it. This section and the next are what the downstream trading agent executes; be concrete about order and preconditions, and keep interpretation of ambiguous terms out of here (that lives in the term file)._

_（中文）按执行顺序编号。每一步写明做什么决策，S5 起把做该决策的回调术语加粗。本节与下一节是下游交易 agent 真正执行的部分：顺序和前置条件要具体，对模糊术语的解释不要写在这里（写在术语文件里）。_

1. …
2. …

<!-- section: exit_and_risk -->
## 5. Exit and risk control / 出场与风控

_(EN guidance) Every way a position can be closed or reduced, and every risk rule (initial stop placement, move-to-cost trigger, trailing rule, hard exits, position sizing). Each exit path must be consistent with the term definitions; S6 checks for contradictions here._

_（中文）所有平仓/减仓的途径和全部风控规则（初始止损位置、移损至成本的触发条件、移动止损规则、硬性出场、仓位）。每条出场路径都要与术语定义一致，S6 会在这里查矛盾。_

<!-- section: scope_and_params -->
## 6. Scope and parameters / 适用范围与参数

_(EN guidance) What the strategy applies to and the tunables: instruments / varieties, contract selection (main vs far month), timeframe pair, and numeric parameters with their defaults or ranges. Decisions from the S3 dialog such as "trade many varieties, main contract" are recorded here so that S4 can filter terms against them._

_（中文）适用对象与可调参数：品种、合约选择（主力/远月）、周期搭配、数值参数及其默认值或范围。S3 对话中"多品种、主力合约"之类的决定记录在这里，S4 据此过滤术语。_
