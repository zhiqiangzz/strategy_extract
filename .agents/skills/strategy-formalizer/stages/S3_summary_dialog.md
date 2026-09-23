# S3 — Summary dialog with the user

> **Agents: follow the English part only (above the "中文版" divider). The Chinese part is a translation for human readers and adds no instructions.**
>
> **说明：agent 执行时只需参考上半部分的英文；下半部分的中文仅供人类阅读，内容相同，不含额外指令。**

## Goal

Turn `S2_summary_init.md` into a summary the user agrees describes *their* strategy, through a sequence of single questions, one per turn. Two kinds of content are settled here: (1) what the text means where its description of the strategy's logic is ambiguous, and (2) what the user wants changed or added (steps the source skipped, rules the user does differently, a narrower scope). Not settled here: aspects the text never mentions (instrument universe, contract choice, session, sizing, re-entry) — they are the downstream agent's concern and are not asked about unless the user brings them up; and how key concepts are measured (major-timeframe direction, favourable move, trailing rule) — those are term definitions, handled in S6. Every question and answer is logged on disk before/after it is spoken. The summary's sections 4 (execution steps) and 5 (exit & risk) get the most attention because the downstream agent executes them.

## Inputs

- `S2_summary_init.md`, `S1_strategy_raw.md` (to quote when asking), `S2_terms_init.json` (to know which terms exist; do not edit it here).

## Outputs

| File | Content |
|---|---|
| `S3_dialog.json` / `.md` | Every question (`open` → `answered` → `closed`) with `affects.sections`, `affects.terms`, and a `resolution` describing the edit made. Managed by `SF/sf_dialog.py --stage S3`. |
| `S3_summary_corrected.md` | Copy of the summary edited after each round. Same template; still no bold. Section 6 must now state instruments, contract choice, timeframe pair. |

## Procedure

1. `SF/sf_state.py start S3`. Copy `S2_summary_init.md` to `S3_summary_corrected.md`.
2. Build a private question queue (keep it in your head or in a scratch file; it is not an output). Sources of questions, in priority order: `[待确认]` marks (each must be an ambiguity in the text); steps whose order or trigger is unclear; whether every exit path in the text is captured and whether they are independent; passages of the raw text that the summary might have misread; and finally one open question inviting the user's own changes ("有没有你想改或补充的规则？"). Do not generate questions about things the text never mentions, and do not ask how a concept is determined (that is S6). Split every topic into atomic questions: one question asks for exactly one decision (e.g. "which instruments?" and "main or far-month contract?" are two questions). Group a topic's questions under one `round` number.
3. Ask one question per turn: `SF/sf_dialog.py --stage S3 add -q "<question>" --affects-terms ... --affects-sections ... [--new-round]`, then put that single question to the user, prefixed with its `D###` id, quoting the relevant summary line and offering lettered options where useful (always allow a free answer). End the turn. Do not ask a second question in the same message.
4. When the answer arrives: `SF/sf_dialog.py --stage S3 answer D### -a "<verbatim answer>"`; edit `S3_summary_corrected.md`; `close D### -r "<what changed>"`. If the answer introduces a new concept that will need a definition, record it in the resolution as `NEW TERM: <name>` so S4 picks it up. Then go back to step 3 with the next question (the answer may add or remove queued questions).
5. Continue until you have no open uncertainty in sections 4–6 and the user says the summary is right (ask explicitly, as its own question: "总结是否已经准确？还有要改的吗？"). Typical runs need 10–20 questions.
6. Final pass: re-read the whole corrected summary against the raw text; list anything the summary claims that the text and dialog do not support; fix or ask.
7. `SF/sf_dialog.py --stage S3 to-md`; `SF/sf_state.py complete S3`; stop message; end the turn.

## Resume note

If `status` shows S3 `in_progress` with an `open` entry, that question was asked but never answered: ask it again verbatim (it is the only open one), then continue at step 4.

## Done criteria

- No `open` entries in `S3_dialog.json`; every `answered` entry is `closed` with a resolution.
- Section 6 contains only scope/parameter statements from the text plus changes the user explicitly asked for; nothing "未提" or "待下游决定" is listed.
- The user confirmed the summary in their own words (quote it in the last resolution).

## Stop message

Ask the user to read `S3_summary_corrected.md` once more as a whole and edit directly if they prefer; mention that `S3_dialog.md` is their record and can be annotated (run `from-md` on resume if they do).

---

# 中文版（仅供人类阅读；agent 请参考上方英文）

## 目标

通过一次一个的连续提问，把 `S2_summary_init.md` 修订成用户认可的、描述"他自己的"策略的总结。这里要定两类内容：(1) 原文对策略逻辑描述含糊之处的含义；(2) 用户希望修改或补充的内容（来源略过的步骤、用户做法不同的规则、收窄范围）。不在这里处理的：原文完全没提的方面（品种范围、合约、时段、仓位、再入场）——那是下游 agent 的事，除非用户主动提出否则不问；以及关键概念如何度量（大周期方向、有利运动、移动止损规则）——那是术语定义，S6 处理。每个问答在说出之前/之后都落盘。第 4 节执行步骤和第 5 节出场与风控最重要，因为下游 agent 执行它们。

## 输入

- `S2_summary_init.md`、`S1_strategy_raw.md`（提问时引用）、`S2_terms_init.json`（了解已有术语；本阶段不编辑它）。

## 产出

| 文件 | 内容 |
|---|---|
| `S3_dialog.json` / `.md` | 每个问题（`open` → `answered` → `closed`），带 `affects.sections`、`affects.terms` 和描述所做修改的 `resolution`。由 `SF/sf_dialog.py --stage S3` 管理。 |
| `S3_summary_corrected.md` | 每轮之后修改的总结副本。同一模板；仍不加粗。第 6 节此时必须写明品种、合约选择、周期搭配。 |

## 步骤

1. `SF/sf_state.py start S3`，复制 `S2_summary_init.md` 为 `S3_summary_corrected.md`。
2. 自己维护一个问题队列（记在脑中或临时文件，不是产出）。问题来源按优先级：`[待确认]` 标记（每个都必须是原文本身的含糊）；顺序或触发条件不清的步骤；原文的每条出场路径是否都被记录、是否相互独立；总结可能误读原文的段落；最后一个开放问题请用户提出自己的修改（“有没有你想改或补充的规则？”）。不要就原文没提的事情生成问题，也不要问某概念如何判定（那是 S6）。把每个主题拆成原子问题：一个问题只要一个决定（"做什么品种？"和"主力还是远月？"是两个问题）。同一主题的问题用同一个 `round` 编号分组。
3. 每轮只问一个：`SF/sf_dialog.py --stage S3 add -q "<问题>" --affects-terms ... --affects-sections ... [--new-round]`，然后带 `D###` 编号向用户提出这一个问题，引用总结原句，必要时给字母选项（始终允许自由回答）。结束本轮。同一条消息里不问第二个问题。
4. 收到回答：`SF/sf_dialog.py --stage S3 answer D### -a "<回答原话>"`；修改 `S3_summary_corrected.md`；`close D### -r "<改了什么>"`。若回答引入需要定义的新概念，在 resolution 里写 `NEW TERM: <名称>` 供 S4 采集。然后回到第 3 步问下一个（回答可能增减队列中的问题）。
5. 直到第 4~6 节没有未决点且用户明确说总结准确（作为单独一个问题直接问："总结是否已经准确？还有要改的吗？"）。通常 10~20 个问题。
6. 收尾：对照原文通读整份修订后的总结，列出原文与对话都不支持的说法，修正或再问。
7. `SF/sf_dialog.py --stage S3 to-md`；`SF/sf_state.py complete S3`；停止消息；结束本轮。

## 恢复提示

若 `status` 显示 S3 为 `in_progress` 且有一个 `open` 条目，说明该问题问过但没得到回答：原样再问一次（它是唯一 open 的），然后从第 4 步继续。

## 完成标准

- `S3_dialog.json` 没有 `open` 条目；每个 `answered` 条目都已 `closed` 并有 resolution。
- 第 6 节只含原文的范围/参数陈述和用户明确要求的修改；没有"未提"或"待下游决定"之类条目。
- 用户用自己的话确认了总结（在最后一条 resolution 中引用）。

## 停止消息

请用户再整体读一遍 `S3_summary_corrected.md`，愿意的话直接编辑；说明 `S3_dialog.md` 是他们的记录，可以批注（若批注了，恢复时运行 `from-md`）。
