# S2 — Summarize and extract terms (two subagents)

> **Agents: follow the English part only (above the "中文版" divider). The Chinese part is a translation for human readers and adds no instructions.**
>
> **说明：agent 执行时只需参考上半部分的英文；下半部分的中文仅供人类阅读，内容相同，不含额外指令。**

## Goal

Fork the corrected text into two independent views: a human-readable structured summary (sub1) and a list of candidate key terms (sub2). They are produced by two subagents launched **in parallel** with the Agent tool, using the prompts in `agents/`. They are independent on purpose: the summary is what the user will discuss in S3; the term list is what S4 will prune using that discussion. Subagents cannot talk to the user, so no question is asked in this stage; uncertainties are marked in the outputs instead.

## Inputs

- `S1_strategy_clean.md` (the organised corrected text; primary input), `S1_strategy_raw.md` (timestamped twin, for locating quotes), `S1_sources.json` (to find secondary files for context).
- `templates/strategy_summary.template.md`, `schemas/term.schema.json`.

## Outputs

| File | Producer | Content |
|---|---|---|
| `S2_summary_init.md` | sub1 | Summary following the template's six sections (copy the skeleton between the SKELETON-START/END markers of the template). Bodies in Chinese. No bold yet. Unclear points marked `[待确认: ...]`. |
| `S2_terms_init.json` | sub2 | `{"stage":"S2","scheme_id":null,"terms":[...]}` with every field of the term schema present; `status: candidate`, `origin: S2_extract`, `role`/`phase` null. |
| `S2_terms_init.xlsx` | main agent | `SF/sf_terms.py to-xlsx S2_terms_init.json`. |

## Procedure

1. `SF/sf_state.py start S2`.
2. Launch two Agent-tool subagents in one message. Give each the full text of its prompt file (`agents/sub1_summarizer.md`, `agents/sub2_term_extractor.md`) followed by the absolute paths of `S1_strategy_clean.md`, `S1_strategy_raw.md`, `S1_sources.json`, the output file, and the template/schema it needs. Tell each to write its file and reply with a 5-line report.
3. When both return: read both outputs. Run `SF/sf_terms.py validate S2_terms_init.json --fix` and fix any error (malformed ids, duplicate names, more than 50 terms → merge the most similar ones yourself and note it). Check the summary has all six `<!-- section: -->` markers.
4. `SF/sf_terms.py to-xlsx S2_terms_init.json`.
5. `SF/sf_state.py complete S2`, print the stop message, end the turn.

## Done criteria

- Summary has all six section markers with non-empty bodies. Every `[待确认]` points at an ambiguity in the text itself; none lists an unmentioned aspect (contract, session, sizing…) or asks how a concept is determined. Remove any that do before completing.
- Term file validates; between 10 and 50 candidate terms, each with a non-empty `source_quote` and `appears_in`.

## Stop message

Ask the user to read `S2_summary_init.md` and mark disagreements (they will be discussed in S3), and to glance at `S2_terms_init.xlsx`; tell them term pruning happens in S4, so they need not edit the term list now.

---

# 中文版（仅供人类阅读；agent 请参考上方英文）

## 目标

把矫正后的文本分成两个独立视角：给人读的结构化总结（sub1）和候选关键术语列表（sub2）。两者由 Agent 工具**并行**启动的两个子代理产出，提示词在 `agents/`。刻意独立：总结是 S3 与用户讨论的对象，术语表是 S4 根据讨论剪裁的对象。子代理不能与用户对话，本阶段不提问，不确定之处标注在产出里。

## 输入

- `S1_strategy_clean.md`（整理后的矫正文本，主要输入）、`S1_strategy_raw.md`（带时间戳的副本，用于定位引用）、`S1_sources.json`（用于找到作为背景的 secondary 文件）。
- `templates/strategy_summary.template.md`、`schemas/term.schema.json`。

## 产出

| 文件 | 产出者 | 内容 |
|---|---|---|
| `S2_summary_init.md` | sub1 | 按模板六节写的总结（复制模板中 SKELETON-START/END 标记之间的骨架）。正文中文。暂不加粗。不清楚之处标 `[待确认: ...]`。 |
| `S2_terms_init.json` | sub2 | `{"stage":"S2","scheme_id":null,"terms":[...]}`，术语 schema 的字段齐全；`status: candidate`、`origin: S2_extract`、`role`/`phase` 为 null。 |
| `S2_terms_init.xlsx` | 主代理 | `SF/sf_terms.py to-xlsx S2_terms_init.json` 生成。 |

## 步骤

1. `SF/sf_state.py start S2`。
2. 在一条消息里启动两个子代理。各自提供提示词文件全文（`agents/sub1_summarizer.md`、`agents/sub2_term_extractor.md`），以及 `S1_strategy_clean.md`、`S1_strategy_raw.md`、`S1_sources.json`、输出文件、所需模板/schema 的绝对路径。要求写文件并回复 5 行报告。
3. 两者返回后阅读产出。运行 `SF/sf_terms.py validate S2_terms_init.json --fix` 修复错误（id 格式、重名、超过 50 个则自行合并最相近者并说明）。确认总结含六个 `<!-- section: -->` 标记。
4. `SF/sf_terms.py to-xlsx S2_terms_init.json`。
5. `SF/sf_state.py complete S2`，打印停止消息，结束本轮。

## 完成标准

- 总结六个章节标记齐全且正文非空。每个 `[待确认]` 都指向原文本身的含糊；没有任何一个在罗列原文没提的方面（合约、时段、仓位……）或询问某概念如何判定。完成前删掉不合规的标记。
- 术语文件通过校验；候选术语 10~50 个，每个都有非空的 `source_quote` 与 `appears_in`。

## 停止消息

请用户阅读 `S2_summary_init.md` 并标出不同意之处（S3 会讨论），并浏览 `S2_terms_init.xlsx`；告知术语剪裁在 S4 进行，现在不必编辑术语表。
