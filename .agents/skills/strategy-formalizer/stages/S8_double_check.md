# S8 — Double check and freeze / 交叉核对并冻结

> Agents: read the English blocks only. 中文仅供人类阅读。

## Goal / 目标

Confirm that the summary, the term set and the formal interface describe the same strategy with nothing missing and nothing contradictory, then freeze the deliverables in `final/`. The script does the mechanical part (bold ↔ callbacks ↔ formal entries, sections present, no open questions, validators); you do the semantic part: read the summary's execution steps and exit rules one by one and verify each is fully covered by defined terms and callbacks, and that no term definition contradicts a summary sentence.

确认总结、术语集、形式化接口描述的是同一个策略，没有遗漏也没有矛盾，然后把交付物冻结到 `final/`。脚本做机械部分（加粗 ↔ 回调 ↔ 形式化条目、章节齐全、无未答问题、各校验通过），你做语义部分：逐条阅读总结的执行步骤和出场规则，确认每条都被已定义的术语和回调完整覆盖，且没有术语定义与总结句子矛盾。

## Inputs / 输入

- `S5_summary_marked.md`, `S6_terms_defined.json`, `S7_formal.json`, `S7_callbacks_stub.py`, `S6_conflict_log.md`, `references/consistency_rules.md`.

## Outputs / 产出

| File | Content |
|---|---|
| `S8_check_report.md` | Script findings (written by `sf_check.py run`) followed by your "Semantic review" section: a table step-by-step (summary line → terms/callbacks covering it → OK / issue), and a list of fixes applied. |
| `final/strategy.md`, `final/terms.json`, `final/formal.json`, `final/callbacks_stub.py` | Frozen copies written by `sf_check.py freeze`. These are what the downstream trading agent consumes. |

## Procedure / 步骤

1. `SF/sf_state.py start S8`; `SF/sf_check.py run`. Fix every ERROR at its source (summary bold, term file, formal file) and re-run until zero errors. Read the warnings; a term never mentioned in the summary is usually either stale (drop it) or a missing sentence in the summary (add it).
2. Semantic review: for each numbered line in sections 4 and 5 and each bullet in section 6, list the terms that make it executable. A line that needs a judgement but has no callback, or a callback whose definition allows something the summary forbids, is an issue. Check the conflict log's resolutions are actually reflected in both files. Write the section into `S8_check_report.md` under "Semantic review".
3. If an issue needs a definition change that alters meaning, stop and ask the user (this is a single question, log it in `S6_dialog.json` with `--stage S6` for the record), apply the answer to both files, re-run step 1. If the change is large, `reopen S6` instead.
4. `SF/sf_check.py freeze`; `SF/sf_state.py complete S8`; final message; end the turn.

1. `start S8`；`sf_check.py run`，从源头修复每个 ERROR 直到为零；阅读警告——总结从未提到的术语通常要么过期（丢弃）要么总结漏了一句（补上）。
2. 语义审查：对第 4、5 节的每个编号行和第 6 节每个条目，列出使其可执行的术语。需要判断却没有回调、或回调定义允许总结禁止的事，都是问题。核对冲突日志的裁决是否真的体现在两个文件里。写入报告的"Semantic review"。
3. 需要改变含义的定义修改 → 停下来问用户（单个问题，记入 `S6_dialog.json`），落实到两个文件后重跑第 1 步；改动大则 `reopen S6`。
4. `freeze`、`complete S8`、最终消息、结束本轮。

## Done criteria / 完成标准

- `sf_check.py run` reports 0 errors; the semantic review table has no open issue.
- `final/` contains the four files; `state.json` shows S8 `awaiting_review` (the user's `accept` marks the run done).

## Final message / 最终消息

Summarize in ≤10 lines: number of live terms, number of callbacks with their names, where `final/` is, and that the downstream agent should subclass `final/callbacks_stub.py` and read `final/strategy.md` sections 4–6.
