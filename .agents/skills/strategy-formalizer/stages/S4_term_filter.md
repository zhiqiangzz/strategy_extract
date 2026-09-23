# S4 — Filter and correct terms using the S3 context / 依据 S3 对话过滤、矫正术语

> Agents: read the English blocks only. 中文仅供人类阅读。

## Goal / 目标

Reconcile the candidate term list with what the user decided in S3. Terms that the user's version of the strategy no longer needs are dropped with a reason that cites the dialog (e.g. the text said "only trade lithium carbonate" but the user trades many varieties → drop; the text said "far-month contract" but the user trades the main contract → drop or rewrite). Terms the dialog introduced are added. Near-duplicates are merged. The result is a lean list: ≤30 live terms is the target, 50 is the hard limit.

让候选术语表与用户在 S3 的决定一致。用户版本的策略不再需要的术语予以丢弃，原因引用对话（原文只做碳酸锂而用户做多品种 → 丢弃；原文远月合约而用户做主力合约 → 丢弃或改写）；对话引入的术语加入；近似重复的合并。结果要精简：目标 ≤30 个存活术语，硬上限 50。

## Inputs / 输入

- `S2_terms_init.json`, `S3_dialog.json` (all resolutions, especially `NEW TERM:` notes), `S3_summary_corrected.md`.

## Outputs / 产出

| File | Content |
|---|---|
| `S4_terms_filtered.json` / `.xlsx` | Same ids as S2 plus new ones. Dropped terms keep their row with `status: dropped` and `drop_reason: "D00x: ..."`. Kept terms get `status: kept`, updated `aliases`, and `appears_in` re-checked against the corrected summary. New terms have `origin: S3_dialog`. |

## Procedure / 步骤

1. `SF/sf_state.py start S4`; `SF/sf_terms.py carry S2_terms_init.json S4_terms_filtered.json --stage S4`.
2. Walk every term with the corrected summary open. Decide: keep / drop / rename / merge. Rules of thumb: drop if the concept no longer appears in the corrected summary and no dialog answer needs it; drop scope terms superseded by section 6; merge terms that would get the same definition; do not drop a term only because it is hard.
3. Add terms from `NEW TERM:` resolutions and from any concept in sections 4–6 that is not yet a term and is not self-explanatory: `SF/sf_terms.py add S4_terms_filtered.json --name-zh ... --origin S3_dialog --source-quote "<quote from dialog or summary>" --appears-in "execution_steps"`.
4. `SF/sf_terms.py validate S4_terms_filtered.json`. If the live count is above 30, merge again or downgrade explanatory sentences into `notes` of a related term before adding; above 50 is an error.
5. `SF/sf_terms.py diff S2_terms_init.json S4_terms_filtered.json` and paste the diff into the stop message.
6. `SF/sf_terms.py to-xlsx S4_terms_filtered.json`; `SF/sf_state.py complete S4`; stop; end the turn.

1. `start S4`；`carry` 生成 S4 文件。
2. 对照修订后的总结逐个术语判断：保留 / 丢弃 / 改名 / 合并。经验规则：修订后的总结中不再出现且没有对话需要它 → 丢弃；被第 6 节取代的范围类术语 → 丢弃；定义会相同的 → 合并；不要因为难就丢。
3. 从 `NEW TERM:` 及第 4~6 节中尚未成为术语、又不自明的概念中新增术语（`add`，origin 为 S3_dialog）。
4. `validate`；存活数超过 30 先合并或把解释性句子降为相关术语的 `notes`，超过 50 报错。
5. `diff` 并把结果贴进停止消息。
6. `to-xlsx`、`complete S4`、停止、结束本轮。

## Done criteria / 完成标准

- Validator passes; every dropped term has a `drop_reason` starting with a dialog id or "merged into T###".
- Every concept named in sections 4–6 of the corrected summary that needs a definition is a live term.

## Stop message / 停止消息

Show the diff. Ask the user to edit `S4_terms_filtered.xlsx` (change status, rename, add rows without id) if they disagree; on resume you will run `from-xlsx`.
