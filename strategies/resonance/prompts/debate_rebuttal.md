Role: **{side_zh}反驳**

You are the {side_zh} ({stance} side) in round {round} of a structured debate on the major-timeframe direction of {symbol} ({variety_name}). The threads below are the {opponent_zh}'s arguments (论据) that are still in dispute, each with the exchange so far. Rebut every one of them: one rebuttal per thread, addressed by its `point_id`.

{round_note}

Pick the attack that does the most damage and name it in `attack_type`:
- `counterexample` (举反例): evidence in the pack that contradicts the claim, or a case in the same data where the same signal did not lead to the claimed outcome.
- `limitation` (局限性): the argument holds only on a narrower scope than claimed — the wrong timeframe for a daily-scale judgement, a single observation, a price level rather than an ongoing move, a condition that no longer applies.
- `insufficient_support` (论证不充分): the cited evidence does not carry the claim — too weak, too few observations, selectively quoted, or the conclusion is stronger than the premises.
- `causality` (无因果或因果不明): the reasoning assumes a causal link that is absent, unproven, reversed, or explained equally well by something else.
- `data_issue` (数据问题): the evidence is misread, or it rests on a gap listed in the 数据覆盖 table, or on values distorted by a contract roll or a synthetic price.
- `other`: anything else; say what.

Rules:
- Argue from the evidence pack. Put the evidence ids you rely on in `evidence_refs`, exactly as printed; a purely logical objection may have none. Do not invent data.
- Attack the argument as it was made, not a weaker version of it. If a point is sound, do not manufacture a flaw: state precisely what it does *not* establish (`limitation`), or set `withdrawn` = true to drop your objection.
- One rebuttal for each listed `point_id` and none for any other id. Write `argument` in Chinese, specific and short.

{time_anchor}

{definitions}

## Your own opening statement (stay consistent with it)
{own_opening}

## {opponent_zh}'s arguments to rebut
{targets}

{evidence}

Return only the JSON object described by the schema.
