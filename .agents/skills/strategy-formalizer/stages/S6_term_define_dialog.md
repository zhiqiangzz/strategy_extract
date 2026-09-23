# S6 — Define every term with the user / 与用户对话明确每个术语

> Agents: read the English blocks only. 中文仅供人类阅读。

## Goal / 目标

Give every live term an agreed definition, callback by callback. For each callback you discuss the callback itself (what exactly is being judged, what the possible outputs are, what information it may use) and then the auxiliary/constraint/parameter terms that support it. New terms may appear (e.g. the user says "favourable move means at least 1R of open profit" → parameter `1R 阈值`), old ones may be dropped. After every round you check the definitions against the summary and against each other for contradictions (see `references/consistency_rules.md`) and log the outcome in `S6_conflict_log.md`. When a contradiction is found, the user decides which side wins; you then update both the summary and the term.

按回调逐个为每个存活术语商定定义。对每个回调先讨论回调本身（究竟判断什么、可能的输出有哪些、可以用什么信息），再讨论支持它的辅助/约束/参数术语。可能出现新术语（如用户说"有利运动指浮盈至少 1R" → 参数 `1R 阈值`），也可能丢弃旧术语。每轮之后对照 `references/consistency_rules.md` 检查定义与总结、定义之间是否矛盾，并记录到 `S6_conflict_log.md`。发现矛盾时由用户裁决，然后同时更新总结与术语。

## Inputs / 输入

- `S5_terms_classified.json`, `S5_summary_marked.md`, `S5_categories.json`, `S1_strategy_raw.md`, `S3_dialog.json` (do not re-ask what was answered there).

## Outputs / 产出

| File | Content |
|---|---|
| `S6_dialog.json` / `.md` | All questions and answers, `affects.terms` filled. |
| `S6_terms_defined.json` / `.xlsx` | Every live term `status: defined` with `definition_zh` (agreed with the user) and `definition_en` (your faithful translation; the downstream agent reads it). New terms `origin: S6_dialog`. |
| `S6_conflict_log.md` | One entry per contradiction: what conflicted (quote both sides), dialog id where the user decided, what was changed. Also a final line "no further conflicts found on <date>". |
| `S5_summary_marked.md` (updated in place) | Any strategy change agreed in S6 is applied here too, so summary and terms never diverge. Note each such edit in the conflict log. |

## Procedure / 步骤

1. `SF/sf_state.py start S6`; `SF/sf_terms.py carry S5_terms_classified.json S6_terms_defined.json --stage S6`; create `S6_conflict_log.md` with the banner and an empty list.
2. Order the work: callbacks in execution order (section 4 then 5), each followed by its supporting terms; then remaining parameters/scope/philosophy terms.
3. Per round (3–6 terms): for each term draft a definition from the raw text and S3 answers, state your draft, and ask what is wrong or missing. For callbacks always ask: allowed outputs (e.g. 多/空/不确定), what happens on "uncertain", what inputs it may use (timeframe, indicators, position state), and when it is re-evaluated. Write questions with `SF/sf_dialog.py --stage S6 add` first, then ask.
4. Log answers (`answer`), update `definition_zh`/`definition_en`/`status` in the json (or via `add` for new terms; `status: dropped` with reason for removed ones), then `close` with a resolution.
5. After each round: `SF/sf_terms.py validate S6_terms_defined.json --categories S5_categories.json --require-classified`, then walk the consistency checklist for the terms touched. Any conflict → write it into the log, ask the user in the next round, resolve, update both files.
6. Continue until every live term is `defined` and the user confirms nothing is missing. Then a final full checklist pass over all terms and the summary; append the closing line to the conflict log.
7. `SF/sf_terms.py validate S6_terms_defined.json --categories S5_categories.json --require-classified --require-defined`; `SF/sf_check.py run --lenient --terms S6_terms_defined.json`; `SF/sf_dialog.py --stage S6 to-md`; `SF/sf_terms.py to-xlsx S6_terms_defined.json --categories S5_categories.json`; `SF/sf_state.py complete S6`; stop; end the turn.

1. `start S6`；`carry` 生成 S6 术语文件；新建带横幅的空 `S6_conflict_log.md`。
2. 顺序：按执行顺序（第 4 节再第 5 节）逐个回调，每个回调后紧跟其支持术语；最后是剩余的参数/范围/理念术语。
3. 每轮 3~6 个术语：先根据原文和 S3 回答起草定义，陈述草稿，再问哪里不对或缺什么。回调必问：允许的输出、"不确定"时怎么办、可用输入、何时重新评估。先 `add` 落盘再提问。
4. 记录回答、更新 json（新术语 `add`，删除的置 dropped 并写原因），`close` 写明改动。
5. 每轮后运行校验并对触及的术语走一遍一致性清单；有矛盾则记入日志、下一轮问用户、裁决后同时更新两个文件。
6. 直到所有存活术语都 `defined` 且用户确认无遗漏；最后对全部术语和总结做一次完整清单检查，日志追加收尾行。
7. 运行最终校验、`to-md`、`to-xlsx`、`complete S6`、停止、结束本轮。

## Resume note / 恢复提示

Open entries in `S6_dialog.json` are questions to re-ask verbatim. Terms with `status: kept` (not `defined`) are the remaining work.

## Done criteria / 完成标准

- Validator with `--require-defined` passes; no open dialog entries.
- Conflict log has the closing line and no unresolved entry.
- Every callback has `definition_en` naming its outputs.

## Stop message / 停止消息

Point the user to `S6_terms_defined.xlsx` (definitions column) and `S6_conflict_log.md`; ask them to correct any definition that does not match what they meant.
