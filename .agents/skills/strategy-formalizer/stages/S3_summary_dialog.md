# S3 — Summary dialog with the user / 与用户对话修订策略总结

> Agents: read the English blocks only. 中文仅供人类阅读。

## Goal / 目标

Turn `S2_summary_init.md` into a summary the user agrees describes *their* strategy, through multiple rounds of questions. Two kinds of content are settled here: (1) what the text means where it is ambiguous, and (2) what the user wants changed or added (scope such as instruments and contract choice, steps the video skipped, rules the user does differently). Every question and answer is logged on disk before/after it is spoken. The summary's sections 4 (execution steps) and 5 (exit & risk) get the most attention because the downstream agent executes them.

通过多轮提问，把 `S2_summary_init.md` 修订成用户认可的、描述"他自己的"策略的总结。这里要定两类内容：(1) 原文模糊处的含义；(2) 用户希望修改或补充的内容（品种、合约选择等范围，视频略过的步骤，用户做法不同的规则）。每个问答在说出之前/之后都落盘。第 4 节执行步骤和第 5 节出场与风控最重要，因为下游 agent 执行它们。

## Inputs / 输入

- `S2_summary_init.md`, `S1_strategy_raw.md` (to quote when asking), `S2_terms_init.json` (to know which terms exist; do not edit it here).

## Outputs / 产出

| File | Content |
|---|---|
| `S3_dialog.json` / `.md` | Every question (`open` → `answered` → `closed`) with `affects.sections`, `affects.terms`, and a `resolution` describing the edit made. Managed by `SF/sf_dialog.py --stage S3`. |
| `S3_summary_corrected.md` | Copy of the summary edited after each round. Same template; still no bold. Section 6 must now state instruments, contract choice, timeframe pair. |

## Procedure / 步骤

1. `SF/sf_state.py start S3`. Copy `S2_summary_init.md` to `S3_summary_corrected.md`.
2. Prepare round 1: 3–6 questions. Prioritize: `[待确认]` marks; steps whose order or trigger is unclear; every exit path (is it complete?); scope (instruments, contract, timeframes, session/time filters); anything in the summary that the raw text does not actually say. Each question quotes the relevant summary line and, where useful, the raw text, and offers concrete options.
3. Write them first: `SF/sf_dialog.py --stage S3 add --batch <tmpfile.json>` (or one `add -q` per question). Then ask the user all questions of the round in one message, numbered with their `D###` ids.
4. For each answer: `SF/sf_dialog.py --stage S3 answer D### -a "<verbatim answer>"`; edit `S3_summary_corrected.md`; `close D### -r "<what changed>"`. If the answer introduces a new concept that will need a definition, record it in the resolution as `NEW TERM: <name>` so S4 picks it up.
5. Repeat rounds until you have no open uncertainty in sections 4–6 and the user says the summary is right (ask explicitly: "总结是否已经准确？还有要改的吗？"). Typical runs need 2–4 rounds.
6. Final pass: re-read the whole corrected summary against the raw text; list anything the summary claims that the text and dialog do not support; fix or ask.
7. `SF/sf_dialog.py --stage S3 to-md`; `SF/sf_state.py complete S3`; stop message; end the turn.

1. `start S3`，复制初版总结为 `S3_summary_corrected.md`。
2. 准备第一轮 3~6 个问题。优先：`[待确认]`；顺序或触发条件不清的步骤；每条出场路径是否完整；范围（品种、合约、周期、时段过滤）；总结里原文没说的内容。每个问题引用总结原句（必要时引用原文），并给出具体选项。
3. 先落盘（`add --batch` 或逐个 `add -q`），再在一条消息里带 `D###` 编号向用户提问。
4. 每个回答：`answer` 记录原话 → 修改总结 → `close -r` 写明改动。若回答引入需要定义的新概念，在 resolution 里写 `NEW TERM: <名称>` 供 S4 采集。
5. 反复直到第 4~6 节没有未决点且用户明确说总结准确（要直接问）。通常 2~4 轮。
6. 收尾：对照原文通读总结，列出原文与对话都不支持的说法，修正或再问。
7. `to-md`、`complete S3`、停止消息、结束本轮。

## Resume note / 恢复提示

If `status` shows S3 `in_progress` with `open` entries, those questions were asked but never answered: ask them again verbatim in one message, then continue at step 4.

## Done criteria / 完成标准

- No `open` entries in `S3_dialog.json`; every `answered` entry is `closed` with a resolution.
- Section 6 states instruments, contract selection and the timeframe pair (or explicitly "待下游决定").
- The user confirmed the summary in their own words (quote it in the last resolution).

## Stop message / 停止消息

Ask the user to read `S3_summary_corrected.md` once more as a whole and edit directly if they prefer; mention that `S3_dialog.md` is their record and can be annotated (run `from-md` on resume if they do).
