# Consistency rules for S6 and S8 / S6、S8 的一致性检查清单

> Agents: read the English blocks only. 中文仅供人类阅读。

Scripts catch structural problems (dangling ids, missing definitions, bold mismatches). The checks below need reading and judgement; walk them after every S6 round for the terms touched, and over everything in S8. Record each finding in `S6_conflict_log.md` (S6) or `S8_check_report.md` (S8) with the two conflicting quotes, the dialog id where the user decided, and the edit made.

脚本只能发现结构性问题（悬空 id、缺定义、加粗不匹配）。下面的检查需要阅读和判断：S6 每轮后对触及的术语走一遍，S8 对全部内容走一遍。每个发现记入 `S6_conflict_log.md`（S6）或 `S8_check_report.md`（S8），附两段冲突原文、用户裁决的对话 id 和所做修改。

## 1. Exit paths / 出场路径

Every way the summary closes a position must be allowed by the term definitions, and every exit a term definition allows must appear in the summary. Classic conflict: summary says "exit on stop OR on major-timeframe reversal", but `trailing_stop_level`'s definition says "the only exit is the trailing stop". Ask which is true; then either add `major_trend_reversal` as a callback with a `triggers` relation to closing, or delete the reversal sentence.

总结中每条平仓途径都必须被术语定义允许，术语定义允许的每条出场也必须出现在总结里。典型冲突："打止损或大周期反转出场" vs 术语说"唯一出场是移动止损"。问清楚后要么补回调和 `triggers` 关系，要么删句子。

## 2. Stop-loss direction and timing / 止损方向与时机

"Stop only tightens" must hold in every rule that moves a stop (move-to-cost, trailing). "As soon as possible but not immediately" needs a trigger term (favourable move confirmed); if no term defines the trigger, the callback is under-specified.

"止损只进不退"要在所有移动止损的规则里成立；"尽快但不是立刻"需要一个触发术语，没有则回调定义不足。

## 3. Direction filter / 方向过滤

If a callback decides direction (major timeframe), every entry rule must reference it, and the "uncertain" output must have a defined consequence (no trade / wait / keep position?). Check that no entry rule bypasses the filter.

若某回调决定方向，每条入场规则都必须引用它，且"不确定"输出要有明确后果。检查没有入场规则绕过过滤。

## 4. Scope / 适用范围

Section 6 (instruments, contract choice, timeframe pair) must not be contradicted by any live term: a live `scope` term "far-month contract" while section 6 says "main contract" is a conflict; drop or rewrite.

第 6 节不得与任何存活术语冲突：术语说远月而第 6 节说主力，就是冲突。

## 5. Parameters / 参数

Each numeric statement (timeframe gap 1–2 orders, payoff ≥ 3, 1R threshold) must exist once, as a `parameter` term, with the same value in the summary and the definition. Two terms carrying the same number are a merge candidate.

每个数值陈述只应存在一次，作为 parameter 术语，总结与定义中的数值一致。

## 6. Term vs summary wording / 术语与总结措辞

A callback's bold name in the summary must be used in the sense of its definition at every occurrence. If a sentence uses the term loosely (e.g. "大周期" meaning the chart rather than the direction judgement), rewrite the sentence or add an alias/aux term.

回调在总结中每次加粗出现的含义都必须与定义一致；用法松散时改写句子或增加别名/辅助术语。

## 7. Coverage / 覆盖

Every numbered step in section 4 and every bullet in section 5 must be executable with the live terms: identify the callback that makes its decision and the constraints/parameters it uses. A step with a judgement but no callback is a gap; a callback nothing invokes is stale.

第 4 节每一步、第 5 节每条都要能用存活术语执行：找出做决策的回调及其约束/参数。有判断无回调是遗漏，无人调用的回调是过期。

## 8. New terms from dialog / 对话新增术语

A term added in S6 must have `supports` (unless it is a callback) and must be mentioned in the summary; otherwise add the sentence or drop the term.

S6 新增术语必须有 `supports`（回调除外）且在总结中被提及，否则补句子或丢弃。
