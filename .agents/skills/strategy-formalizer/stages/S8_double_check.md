# S8 — Double check and freeze

> **Agents: follow the English part only (above the "中文版" divider). The Chinese part is a translation for human readers and adds no instructions.**
>
> **说明：agent 执行时只需参考上半部分的英文；下半部分的中文仅供人类阅读，内容相同，不含额外指令。**

## Goal

Confirm that the summary, the term set and the formal interface describe the same strategy with nothing missing and nothing contradictory, then freeze the deliverables in `final/`. The script does the mechanical part (bold ↔ callbacks ↔ formal entries, sections present, no open questions, validators); you do the semantic part: read the summary's execution steps and exit rules one by one and verify each is fully covered by defined terms and callbacks, and that no term definition contradicts a summary sentence.

## Inputs

- `S5_summary_marked.md`, `S6_terms_defined.json`, `S7_formal.json`, `S7_callbacks_stub.py`, `S6_conflict_log.md`, `references/consistency_rules.md`.

## Outputs

| File | Content |
|---|---|
| `S8_check_report.md` | Script findings (written by `sf_check.py run`) followed by your "Semantic review" section: a table step by step (summary line → terms/callbacks covering it → OK / issue), and a list of fixes applied. |
| `final/strategy.md`, `final/terms.json`, `final/formal.json`, `final/callbacks_stub.py` | Frozen copies written by `sf_check.py freeze`. These are what the downstream trading agent consumes. |

## Procedure

1. `SF/sf_state.py start S8`; `SF/sf_check.py run`. Fix every ERROR at its source (summary bold, term file, formal file) and re-run until zero errors. Read the warnings; a term never mentioned in the summary is usually either stale (drop it) or a missing sentence in the summary (add it).
2. Semantic review: for each numbered line in sections 4 and 5 and each bullet in section 6, list the terms that make it executable. A line that needs a judgement but has no callback, or a callback whose definition allows something the summary forbids, is an issue. Check the conflict log's resolutions are actually reflected in both files. Write the section into `S8_check_report.md` under "Semantic review".
3. If an issue needs a definition change that alters meaning, stop and ask the user (a single question; log it in `S6_dialog.json` with `--stage S6` for the record), apply the answer to both files, re-run step 1. If the change is large, `reopen S6` instead.
4. `SF/sf_check.py freeze`; `SF/sf_state.py complete S8` (this marks S8 done directly; no accept step follows); final message; end the turn.

## Done criteria

- `sf_check.py run` reports 0 errors; the semantic review table has no open issue.
- `final/` contains the four files; `state.json` shows S8 `done`.

## Final message

Summarize in ≤10 lines: number of live terms, number of callbacks with their names, where `final/` is, and that the downstream agent should subclass `final/callbacks_stub.py` and read `final/strategy.md` sections 4–6.

---

# 中文版（仅供人类阅读；agent 请参考上方英文）

## 目标

确认总结、术语集、形式化接口描述的是同一个策略，没有遗漏也没有矛盾，然后把交付物冻结到 `final/`。脚本做机械部分（加粗 ↔ 回调 ↔ 形式化条目、章节齐全、无未答问题、各校验通过），你做语义部分：逐条阅读总结的执行步骤和出场规则，确认每条都被已定义的术语和回调完整覆盖，且没有术语定义与总结句子矛盾。

## 输入

- `S5_summary_marked.md`、`S6_terms_defined.json`、`S7_formal.json`、`S7_callbacks_stub.py`、`S6_conflict_log.md`、`references/consistency_rules.md`。

## 产出

| 文件 | 内容 |
|---|---|
| `S8_check_report.md` | 脚本发现（由 `sf_check.py run` 写出）之后是你的"语义审查"节：逐行表格（总结行 → 覆盖它的术语/回调 → 通过 / 问题）和已做修复的列表。 |
| `final/strategy.md`、`final/terms.json`、`final/formal.json`、`final/callbacks_stub.py` | `sf_check.py freeze` 写出的冻结副本。下游交易 agent 使用的就是这些。 |

## 步骤

1. `SF/sf_state.py start S8`；`SF/sf_check.py run`。从源头（总结加粗、术语文件、形式化文件）修复每个 ERROR 并重跑直到为零。阅读警告——总结从未提到的术语通常要么过期（丢弃）要么总结漏了一句（补上）。
2. 语义审查：对第 4、5 节每个编号行和第 6 节每个条目，列出使其可执行的术语。需要判断却没有回调、或回调定义允许总结禁止的事，都是问题。核对冲突日志的裁决是否真的体现在两个文件里。写入 `S8_check_report.md` 的"Semantic review"节。
3. 若某问题需要改变含义的定义修改，停下来问用户（单个问题；用 `--stage S6` 记入 `S6_dialog.json` 留痕），把回答落实到两个文件后重跑第 1 步。改动大则 `reopen S6`。
4. `SF/sf_check.py freeze`；`SF/sf_state.py complete S8`（直接标记 S8 为 done，之后没有 accept）；最终消息；结束本轮。

## 完成标准

- `sf_check.py run` 报 0 个错误；语义审查表没有未解决的问题。
- `final/` 含四个文件；`state.json` 显示 S8 为 `done`。

## 最终消息

不超过 10 行：存活术语数、回调数及其名称、`final/` 的位置，以及下游 agent 应继承 `final/callbacks_stub.py` 并阅读 `final/strategy.md` 第 4~6 节。
