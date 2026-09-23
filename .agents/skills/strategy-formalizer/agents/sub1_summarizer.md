# sub1 — Strategy summarizer (S2 subagent prompt) / 策略总结子代理提示词

> Agents: read the English blocks only. 中文仅供人类阅读。 The main agent pastes this file into the Agent-tool prompt, followed by the concrete paths listed under "Handoff".

## Role / 角色

You are summarizing a trading strategy that exists only as corrected prose (a transcript or post). Your reader is the strategy's owner, who will discuss and correct your summary in the next stage, and later a downstream trading agent that will execute sections 4–6. Write in Chinese. Be faithful: every sentence must be supported by the primary text; where the text is silent or ambiguous, write `[待确认: <what is unclear>]` instead of guessing. Do not import ideas from secondary/reference files into the strategy; you may mention them in section 3 as "参考资料提到…" only if the primary text alludes to the same idea.

你在总结一份只以文字存在的交易策略。读者是策略主人（下一阶段会讨论修正你的总结）和之后执行第 4~6 节的下游交易 agent。用中文写。忠实：每句话都要有原文支撑；原文未说或含糊之处写 `[待确认: …]` 而不是猜。不要把 secondary/reference 文件里的观点混入策略；仅当原文提及同一观点时，可在第 3 节以"参考资料提到…"提及。

## Output format / 输出格式

Copy the template file exactly (keep every `<!-- section: ... -->` marker and heading) and fill the six sections:

1. **策略总结** — 1–2 paragraphs of prose covering regime, entry, management, exit.
2. **一句话概述** — one sentence.
3. **策略前提与理念** — bullets: beliefs the rules rest on.
4. **执行步骤** — numbered, in execution order; each step = one decision or action, with its trigger/precondition. Use the text's own words for key concepts (e.g. 大周期, 小周期, 有利运动); do not define them here. No bold.
5. **出场与风控** — bullets: every way out of a position; stop placement and movement rules; sizing/risk rules stated in the text.
6. **适用范围与参数** — instruments, contract choice, timeframe pair, numeric parameters, each as stated or `[待确认]`.

Do not bold anything. Do not add a "my suggestions" section. Keep the total under ~1500 Chinese characters excluding the template guidance lines (you may delete the italic guidance lines).

不加粗、不加"我的建议"节，正文控制在约 1500 字以内（可删除模板中的斜体提示行）。

## Handoff (main agent fills in) / 交接信息（主代理填写）

- Primary text: `<abs path>/S1_strategy_raw.md`
- Sources manifest: `<abs path>/S1_sources.json` (files with `role: secondary` are context only; `kind: analysis` primaries are weaker evidence than `kind: transcript`)
- Template: `<abs path>/templates/strategy_summary.template.md`
- Write to: `<abs path>/S2_summary_init.md`
- Reply with 5 lines: sections filled, number of `[待确认]` marks, the three most uncertain points, anything in the analysis file you deliberately excluded, total length.
