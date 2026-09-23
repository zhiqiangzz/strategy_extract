# S6 — Define every term with the user

> **Agents: follow the English part only (above the "中文版" divider). The Chinese part is a translation for human readers and adds no instructions.**
>
> **说明：agent 执行时只需参考上半部分的英文；下半部分的中文仅供人类阅读，内容相同，不含额外指令。**

## Goal

Give every live term an agreed definition, callback by callback, asking one atomic question per turn. For each callback you discuss the callback itself (what exactly is being judged, what the possible outputs are, what information it may use; each of these is its own question) and then the auxiliary/constraint/parameter terms that support it. New terms may appear (e.g. the user says "favourable move means at least 1R of open profit" → parameter `1R 阈值`), old ones may be dropped. After every round you check the definitions against the summary and against each other for contradictions (see `references/consistency_rules.md`) and log the outcome in `S6_conflict_log.md`. When a contradiction is found, the user decides which side wins; you then update both the summary and the term.

## Inputs

- `S5_terms_classified.json`, `S5_summary_marked.md`, `S5_categories.json`, `S1_strategy_raw.md`, `S3_dialog.json` (do not re-ask what was answered there).

## Outputs

| File | Content |
|---|---|
| `S6_dialog.json` / `.md` | All questions and answers, `affects.terms` filled. |
| `S6_terms_defined.json` / `.xlsx` | Every live term `status: defined` with `definition_zh` (agreed with the user) and `definition_en` (your faithful translation; the downstream agent reads it). New terms `origin: S6_dialog`. |
| `S6_conflict_log.md` | One entry per contradiction: what conflicted (quote both sides), dialog id where the user decided, what was changed. Also a final line "no further conflicts found on <date>". |
| `S5_summary_marked.md` (updated in place) | Any strategy change agreed in S6 is applied here too, so summary and terms never diverge. Note each such edit in the conflict log. |

## Procedure

1. `SF/sf_state.py start S6`; `SF/sf_terms.py carry S5_terms_classified.json S6_terms_defined.json --stage S6`; create `S6_conflict_log.md` with the banner and an empty list.
2. Order the work: callbacks in execution order (section 4 then 5), each followed by its supporting terms; then remaining parameters/scope/philosophy terms.
3. One question per turn. For each term draft a definition from the raw text and S3 answers, state the draft, and ask a single question about it (e.g. "这个定义对吗？缺什么？"). For callbacks ask, as separate consecutive questions: the allowed outputs (e.g. 多/空/不确定); what happens on "uncertain"; what inputs it may use (timeframe, indicators, position state); when it is re-evaluated. Group one term's questions under one `round` (`--new-round` when you move to the next term). Write each question with `SF/sf_dialog.py --stage S6 add` first, ask it, end the turn.
4. When the answer arrives: `answer`, update `definition_zh`/`definition_en`/`status` in the json (or `add` a new term; `status: dropped` with reason for removed ones), `close` with a resolution, then ask the next question.
5. After finishing a term: `SF/sf_terms.py validate S6_terms_defined.json --categories S5_categories.json --require-classified`, then walk the consistency checklist for the terms touched. Any conflict → write it into the log, ask the user about it as its own question, resolve, update both files.
6. Continue until every live term is `defined` and the user confirms nothing is missing. Then a final full checklist pass over all terms and the summary; append the closing line to the conflict log.
7. `SF/sf_terms.py validate S6_terms_defined.json --categories S5_categories.json --require-classified --require-defined`; `SF/sf_check.py run --lenient --terms S6_terms_defined.json`; `SF/sf_dialog.py --stage S6 to-md`; `SF/sf_terms.py to-xlsx S6_terms_defined.json --categories S5_categories.json`; `SF/sf_state.py complete S6`; stop; end the turn.

## Resume note

An open entry in `S6_dialog.json` is the question to re-ask verbatim (there is at most one). Terms with `status: kept` (not `defined`) are the remaining work.

## Done criteria

- Validator with `--require-defined` passes; no open dialog entries.
- Conflict log has the closing line and no unresolved entry.
- Every callback has `definition_en` naming its outputs.

## Stop message

Point the user to `S6_terms_defined.xlsx` (definitions column) and `S6_conflict_log.md`; ask them to correct any definition that does not match what they meant.

---

# 中文版（仅供人类阅读；agent 请参考上方英文）

## 目标

按回调逐个为每个存活术语商定定义，每轮只问一个原子问题。对每个回调先讨论回调本身（究竟判断什么、可能的输出有哪些、可以用什么信息，每一项都是单独的问题），再讨论支持它的辅助/约束/参数术语。可能出现新术语（如用户说"有利运动指浮盈至少 1R" → 参数 `1R 阈值`），也可能丢弃旧术语。每轮之后对照 `references/consistency_rules.md` 检查定义与总结、定义之间是否矛盾，并记录到 `S6_conflict_log.md`。发现矛盾时由用户裁决，然后同时更新总结与术语。

## 输入

- `S5_terms_classified.json`、`S5_summary_marked.md`、`S5_categories.json`、`S1_strategy_raw.md`、`S3_dialog.json`（那里已回答的不要再问）。

## 产出

| 文件 | 内容 |
|---|---|
| `S6_dialog.json` / `.md` | 全部问答，`affects.terms` 已填。 |
| `S6_terms_defined.json` / `.xlsx` | 每个存活术语 `status: defined`，含与用户商定的 `definition_zh` 和你忠实翻译的 `definition_en`（下游 agent 读它）。新术语 `origin: S6_dialog`。 |
| `S6_conflict_log.md` | 每个矛盾一条：冲突内容（引用双方原文）、用户裁决的对话 id、所做修改。末尾一行"<日期> 未再发现矛盾"。 |
| `S5_summary_marked.md`（原地更新） | S6 中商定的任何策略变更也同步写入这里，使总结与术语不分叉。每处此类修改记入冲突日志。 |

## 步骤

1. `SF/sf_state.py start S6`；`SF/sf_terms.py carry S5_terms_classified.json S6_terms_defined.json --stage S6`；新建带横幅和空列表的 `S6_conflict_log.md`。
2. 顺序：按执行顺序（第 4 节再第 5 节）逐个回调，每个回调后紧跟其支持术语；最后是剩余的参数/范围/理念术语。
3. 每轮只问一个。对每个术语先根据原文和 S3 回答起草定义，陈述草稿，只问一个问题（如"这个定义对吗？缺什么？"）。回调要依次分别问：允许的输出（如 多/空/不确定）；"不确定"时怎么办；可用输入（周期、指标、持仓状态）；何时重新评估。同一术语的问题用同一个 `round`（换术语时 `--new-round`）。每个问题先 `SF/sf_dialog.py --stage S6 add` 落盘，提出，结束本轮。
4. 收到回答：`answer`，在 json 中更新 `definition_zh`/`definition_en`/`status`（新术语用 `add`；删除的置 `status: dropped` 并写原因），`close` 并写 resolution，然后问下一个。
5. 每完成一个术语：`SF/sf_terms.py validate S6_terms_defined.json --categories S5_categories.json --require-classified`，再对触及的术语走一遍一致性清单。有矛盾 → 写入日志、作为单独一个问题问用户、裁决后同时更新两个文件。
6. 直到所有存活术语都 `defined` 且用户确认无遗漏。最后对全部术语和总结做一次完整清单检查；在冲突日志追加收尾行。
7. `SF/sf_terms.py validate S6_terms_defined.json --categories S5_categories.json --require-classified --require-defined`；`SF/sf_check.py run --lenient --terms S6_terms_defined.json`；`SF/sf_dialog.py --stage S6 to-md`；`SF/sf_terms.py to-xlsx S6_terms_defined.json --categories S5_categories.json`；`SF/sf_state.py complete S6`；停止；结束本轮。

## 恢复提示

`S6_dialog.json` 中的 open 条目（最多一个）是要原样再问的问题。`status: kept`（而非 `defined`）的术语是剩余工作。

## 完成标准

- 带 `--require-defined` 的校验通过；没有未回答的对话条目。
- 冲突日志有收尾行且没有未解决的条目。
- 每个回调的 `definition_en` 都写明了输出。

## 停止消息

指引用户查看 `S6_terms_defined.xlsx`（定义列）和 `S6_conflict_log.md`；请其修正任何与本意不符的定义。
