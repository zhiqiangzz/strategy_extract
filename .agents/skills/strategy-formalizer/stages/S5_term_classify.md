# S5 — Classify terms and bold the callbacks

> **Agents: follow the English part only (above the "中文版" divider). The Chinese part is a translation for human readers and adds no instructions.**
>
> **说明：agent 执行时只需参考上半部分的英文；下半部分的中文仅供人类阅读，内容相同，不含额外指令。**

## Goal

Decide, for every live term, what the downstream trading agent must do with it. The default scheme (`role_x_phase`, see `references/classification_schemes.md`) has two axes: **role** — `callback` (the downstream agent must implement a function that returns a decision at runtime), `parameter`, `constraint`, `aux_note`, `scope`; and **phase** — where in the trade lifecycle it applies. The test for `callback` is: *does the strategy require a judgement at runtime that the text does not decide deterministically?* "Major timeframe direction → long/short/uncertain" is a callback; "the two timeframes differ by 1–2 orders of magnitude" is a parameter or aux_note that supports it. Callback terms are then bolded in the summary so the downstream agent can see exactly where each decision is invoked.

## Inputs

- `S4_terms_filtered.json`, `S3_summary_corrected.md`, `templates/categories.*.json`, `references/classification_schemes.md`.

## Outputs

| File | Content |
|---|---|
| `S5_categories.json` | Copy of the chosen `templates/categories.<scheme>.json`, with any value the user added or renamed. The `legend` at the top is the bilingual name table. |
| `S5_terms_classified.json` / `.xlsx` | Every live term with `role`, `phase`, `name_en` (snake_case, will be the callback name), `supports` (aux/constraint/parameter → the callback ids they qualify), `appears_in`. |
| `S5_summary_marked.md` | `S3_summary_corrected.md` with the canonical `name_zh` of every callback term wrapped in `**…**` at each occurrence in sections 4–6 (at least once each). Nothing else bold. This file is the living summary from now until S8. |

## Procedure

1. `SF/sf_state.py start S5`; `SF/sf_terms.py carry S4_terms_filtered.json S5_terms_classified.json --stage S5`.
2. Scheme choice (short dialog, no `sf_dialog` logging needed): present the three schemes in three lines each, recommend `role_x_phase`, let the user pick or tweak. Copy the template to `S5_categories.json`; `SF/sf_state.py set-scheme <id>`.
3. Classify every live term. Fill `name_en`. For every non-callback term fill `supports` with the callback(s) it qualifies (a constraint on entry supports the entry callback, etc.). If a term supports nothing and is not a callback, ask whether it is really needed; prefer dropping.
4. Sanity rules: every step in section 4 and every exit path in section 5 must be covered by at least one callback; a callback whose output the text fully determines (no judgement) is not a callback — make it a constraint. Typical count: 3–8 callbacks.
5. Produce `S5_summary_marked.md`: bold each callback's `name_zh` where it occurs; if the summary uses a different wording, rewrite that sentence to use the canonical name (add the old wording to `aliases`).
6. Validate: `SF/sf_terms.py validate S5_terms_classified.json --categories S5_categories.json --require-classified` and `SF/sf_check.py run --lenient --summary S5_summary_marked.md --terms S5_terms_classified.json` (lenient = skips definitions/formal/dialog checks, keeps the bold checks).
7. `SF/sf_terms.py to-xlsx S5_terms_classified.json --categories S5_categories.json`; `SF/sf_state.py complete S5`; stop; end the turn.

## Done criteria

- Both validators pass; every callback appears in bold at least once; nothing else is bold.
- `S5_categories.json` legend lists every role/phase value with its Chinese name.

## Stop message

List the callbacks (id, name_zh, name_en, phase) in a small table and ask the user to confirm that these are exactly the decisions they expect the downstream agent to make. Mention they can change role/phase in the xlsx.

---

# 中文版（仅供人类阅读；agent 请参考上方英文）

## 目标

为每个存活术语决定下游交易 agent 该拿它怎么办。默认方案 `role_x_phase`（见 `references/classification_schemes.md`）有两轴：**role** —— `callback`（下游必须实现一个在运行时返回决策的函数）、`parameter`、`constraint`、`aux_note`、`scope`；**phase** —— 在交易生命周期的哪个阶段起作用。判断 `callback` 的标准是：*策略是否需要一个运行时判断，而原文没有确定性地给出答案？* "大周期方向 → 多/空/不确定"是回调；"大小周期差 1~2 个数量级"是支持它的参数或辅助说明。随后把回调术语在总结中加粗，让下游 agent 一眼看到每个决策在哪一步被调用。

## 输入

- `S4_terms_filtered.json`、`S3_summary_corrected.md`、`templates/categories.*.json`、`references/classification_schemes.md`。

## 产出

| 文件 | 内容 |
|---|---|
| `S5_categories.json` | 所选 `templates/categories.<方案>.json` 的副本，含用户新增或改名的取值。顶部 `legend` 是中英对照表。 |
| `S5_terms_classified.json` / `.xlsx` | 每个存活术语的 `role`、`phase`、`name_en`（snake_case，将作为回调名）、`supports`（辅助/约束/参数 → 它们所限定的回调 id）、`appears_in`。 |
| `S5_summary_marked.md` | 在 `S3_summary_corrected.md` 基础上，把每个回调术语的规范 `name_zh` 在第 4~6 节每次出现处用 `**…**` 加粗（每个至少一次）。其他一律不加粗。从现在到 S8，它是"活"总结。 |

## 步骤

1. `SF/sf_state.py start S5`；`SF/sf_terms.py carry S4_terms_filtered.json S5_terms_classified.json --stage S5`。
2. 方案选择（简短对话，不必走 `sf_dialog`）：三行介绍每个方案，推荐 `role_x_phase`，用户选定或微调。复制模板为 `S5_categories.json`；`SF/sf_state.py set-scheme <id>`。
3. 逐个分类存活术语。填 `name_en`。每个非回调术语填 `supports`（指向它所限定的回调，例如入场约束支持入场回调）。既不是回调又不支持任何回调的术语，问一下是否真的需要，倾向丢弃。
4. 检查规则：第 4 节每一步、第 5 节每条出场路径至少被一个回调覆盖；输出被原文完全确定、无需判断的不算回调，改为约束。典型数量 3~8 个回调。
5. 生成 `S5_summary_marked.md`：加粗每个回调的 `name_zh`；总结措辞不同时改写该句为规范名，并把旧措辞记入 `aliases`。
6. 校验：`SF/sf_terms.py validate S5_terms_classified.json --categories S5_categories.json --require-classified`，以及 `SF/sf_check.py run --lenient --summary S5_summary_marked.md --terms S5_terms_classified.json`（lenient 跳过定义/形式化/对话检查，只保留加粗检查）。
7. `SF/sf_terms.py to-xlsx S5_terms_classified.json --categories S5_categories.json`；`SF/sf_state.py complete S5`；停止；结束本轮。

## 完成标准

- 两个校验都通过；每个回调至少加粗出现一次；其他内容不加粗。
- `S5_categories.json` 的 legend 列出每个 role/phase 取值及其中文名。

## 停止消息

用小表格列出回调（id、name_zh、name_en、phase），请用户确认这些正是他们期望下游 agent 做出的决策。说明可以在 xlsx 中修改 role/phase。
