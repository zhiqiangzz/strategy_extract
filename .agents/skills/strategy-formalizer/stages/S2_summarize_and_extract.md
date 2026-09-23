# S2 — Summarize and extract terms (two subagents) / 总结与术语提取（两个子代理）

> Agents: read the English blocks only. 中文仅供人类阅读。

## Goal / 目标

Fork the corrected text into two independent views: a human-readable structured summary (sub1) and a list of candidate key terms (sub2). They are produced by two subagents launched **in parallel** with the Agent tool, using the prompts in `agents/`. They are independent on purpose: the summary is what the user will discuss in S3; the term list is what S4 will prune using that discussion. Subagents cannot talk to the user, so no question is asked in this stage; uncertainties are marked in the outputs instead.

把矫正后的文本分成两个独立视角：给人读的结构化总结（sub1）和候选关键术语列表（sub2）。两者由 Agent 工具**并行**启动的两个子代理产出，提示词在 `agents/`。刻意独立：总结是 S3 与用户讨论的对象，术语表是 S4 根据讨论剪裁的对象。子代理不能与用户对话，本阶段不提问，不确定之处标注在产出里。

## Inputs / 输入

- `S1_strategy_raw.md` (primary), `S1_sources.json` (to find secondary files for context).
- `templates/strategy_summary.template.md`, `schemas/term.schema.json`.

## Outputs / 产出

| File | Producer | Content |
|---|---|---|
| `S2_summary_init.md` | sub1 | Summary following the template's six sections. Bodies in Chinese. No bold yet. Unclear points marked `[待确认: ...]`. |
| `S2_terms_init.json` | sub2 | `{"stage":"S2","scheme_id":null,"terms":[...]}` with every field of the term schema present; `status: candidate`, `origin: S2_extract`, `role`/`phase` null. |
| `S2_terms_init.xlsx` | main agent | `SF/sf_terms.py to-xlsx S2_terms_init.json`. |

## Procedure / 步骤

1. `SF/sf_state.py start S2`.
2. Launch two Agent-tool subagents in one message. Give each the full text of its prompt file (`agents/sub1_summarizer.md`, `agents/sub2_term_extractor.md`) followed by the absolute paths of `S1_strategy_raw.md`, `S1_sources.json`, the output file, and the template/schema it needs. Tell each to write its file and reply with a 5-line report.
3. When both return: read both outputs. Run `SF/sf_terms.py validate S2_terms_init.json --fix` and fix any error (malformed ids, duplicate names, more than 50 terms → merge the most similar ones yourself and note it). Check the summary has all six `<!-- section: -->` markers.
4. `SF/sf_terms.py to-xlsx S2_terms_init.json`.
5. `SF/sf_state.py complete S2`, print the stop message, end the turn.

1. `SF/sf_state.py start S2`。
2. 在一条消息里启动两个子代理，各自提供提示词文件全文、`S1_strategy_raw.md` 与 `S1_sources.json` 的绝对路径、输出文件路径、所需模板/schema，要求写文件并回复 5 行报告。
3. 两者返回后阅读产出；运行 `validate --fix` 修复错误（id 格式、重名、超过 50 个则自行合并最相近者并说明）；确认总结含六个章节标记。
4. 生成 xlsx。
5. `complete S2`，打印停止消息，结束本轮。

## Done criteria / 完成标准

- Summary has all six section markers with non-empty bodies (placeholders allowed only as `[待确认]`).
- Term file validates; between 10 and 50 candidate terms, each with a non-empty `source_quote` and `appears_in`.

## Stop message / 停止消息

Ask the user to read `S2_summary_init.md` and mark disagreements (they will be discussed in S3), and to glance at `S2_terms_init.xlsx` — but tell them term pruning happens in S4, so they need not edit the term list now.
