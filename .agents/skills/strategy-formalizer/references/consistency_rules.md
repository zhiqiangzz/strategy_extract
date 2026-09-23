# Consistency rules for S6 and S8

> **Agents: follow the English part only (above the "中文版" divider). The Chinese part is a translation for human readers and adds no instructions.**
>
> **说明：agent 执行时只需参考上半部分的英文；下半部分的中文仅供人类阅读，内容相同，不含额外指令。**

Scripts catch structural problems (dangling ids, missing definitions, bold mismatches). The checks below need reading and judgement; walk them after every S6 round for the terms touched, and over everything in S8. Record each finding in `S6_conflict_log.md` (S6) or `S8_check_report.md` (S8) with the two conflicting quotes, the dialog id where the user decided, and the edit made.

## 1. Exit paths

Every way the summary closes a position must be allowed by the term definitions, and every exit a term definition allows must appear in the summary. Classic conflict: the summary says "exit on stop OR on major-timeframe reversal", but `trailing_stop_level`'s definition says "the only exit is the trailing stop". Ask which is true; then either add `major_trend_reversal` as a callback with a `triggers` relation to closing, or delete the reversal sentence.

## 2. Stop-loss direction and timing

"Stop only tightens" must hold in every rule that moves a stop (move-to-cost, trailing). "As soon as possible but not immediately" needs a trigger term (favourable move confirmed); if no term defines the trigger, the callback is under-specified.

## 3. Direction filter

If a callback decides direction (major timeframe), every entry rule must reference it, and the "uncertain" output must have a defined consequence (no trade / wait / keep position?). Check that no entry rule bypasses the filter.

## 4. Scope

Section 6 (instruments, contract choice, timeframe pair) must not be contradicted by any live term: a live `scope` term "far-month contract" while section 6 says "main contract" is a conflict; drop or rewrite.

## 5. Parameters

Each numeric statement (timeframe gap 1–2 orders, payoff ≥ 3, 1R threshold) must exist once, as a `parameter` term, with the same value in the summary and the definition. Two terms carrying the same number are a merge candidate.

## 6. Term vs summary wording

A callback's bold name in the summary must be used in the sense of its definition at every occurrence. If a sentence uses the term loosely (e.g. "大周期" meaning the chart rather than the direction judgement), rewrite the sentence or add an alias/aux term.

## 7. Coverage

Every numbered step in section 4 and every bullet in section 5 must be executable with the live terms: identify the callback that makes its decision and the constraints/parameters it uses. A step with a judgement but no callback is a gap; a callback nothing invokes is stale.

## 8. New terms from dialog

A term added in S6 must have `supports` (unless it is a callback) and must be mentioned in the summary; otherwise add the sentence or drop the term.

---

# 中文版（仅供人类阅读；agent 请参考上方英文）

脚本只能发现结构性问题（悬空 id、缺定义、加粗不匹配）。下面的检查需要阅读和判断：S6 每轮后对触及的术语走一遍，S8 对全部内容走一遍。每个发现记入 `S6_conflict_log.md`（S6）或 `S8_check_report.md`（S8），附两段冲突原文、用户裁决的对话 id 和所做修改。

## 1. 出场路径

总结中每条平仓途径都必须被术语定义允许，术语定义允许的每条出场也必须出现在总结里。典型冲突：总结说"打止损或大周期反转出场"，而 `trailing_stop_level` 的定义说"唯一出场是移动止损"。问清楚哪个为真；然后要么把 `major_trend_reversal` 加为回调并建立到平仓的 `triggers` 关系，要么删掉反转那句。

## 2. 止损方向与时机

"止损只进不退"要在所有移动止损的规则（移损至成本、移动止损）里成立。"尽快但不是立刻"需要一个触发术语（有利运动确认）；没有术语定义触发条件，则回调定义不足。

## 3. 方向过滤

若某回调决定方向（大周期），每条入场规则都必须引用它，且"不确定"输出要有明确后果（不交易 / 等待 / 保持持仓？）。检查没有入场规则绕过过滤。

## 4. 适用范围

第 6 节（品种、合约选择、周期搭配）不得与任何存活术语冲突：存活的 `scope` 术语说"远月合约"而第 6 节说"主力合约"，就是冲突；丢弃或改写。

## 5. 参数

每个数值陈述（级别差 1~2 个数量级、盈亏比 ≥ 3、1R 阈值）只应存在一次，作为 `parameter` 术语，总结与定义中的数值一致。两个术语带同一个数值，是合并候选。

## 6. 术语与总结措辞

回调在总结中每次加粗出现的含义都必须与定义一致。若某句用法松散（如"大周期"指图表而非方向判断），改写句子或增加别名/辅助术语。

## 7. 覆盖

第 4 节每个编号步骤、第 5 节每个条目都要能用存活术语执行：找出做决策的回调及其使用的约束/参数。有判断无回调是遗漏，无人调用的回调是过期。

## 8. 对话新增术语

S6 新增的术语必须有 `supports`（回调除外）且在总结中被提及；否则补句子或丢弃术语。
