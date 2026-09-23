# Classification schemes for S5 / S5 术语分类方案

> Agents: read the English blocks only. 中文仅供人类阅读。

Three schemes are available as `templates/categories.<scheme_id>.json`. The default is A. The scheme is chosen with the user at the start of S5 and recorded with `sf_state.py set-scheme`. Whatever the scheme, one thing must remain expressible: *which terms need a wrapper*, i.e. which the downstream trading agent must implement as a callback. The examples below use `strategy_zoo/大小周期共振` (multi-timeframe resonance with move-to-cost and trailing stop).

三种方案对应 `templates/categories.<scheme_id>.json`，默认为 A。S5 开始时与用户商定并用 `sf_state.py set-scheme` 记录。无论哪种方案都必须能表达*哪些术语需要 wrapper*，即下游交易 agent 必须实现为回调。示例取自 `strategy_zoo/大小周期共振`。

## A. `role_x_phase` — Role × Phase (default) / 角色 × 交易阶段（默认）

Two orthogonal axes. **role** answers "what must the downstream agent do with this term": `callback` (implement a runtime judgement; `needs_wrapper: true`; bolded in the summary), `parameter` (a tunable value), `constraint` (a hard rule limiting a callback), `aux_note` (guidance the implementer must read), `scope` (instrument / contract / timeframe applicability). **phase** answers "at which step of the trade does it matter": `market_context`, `entry`, `position_mgmt`, `exit`, `risk`, `philosophy`. Non-callback terms carry `supports: [callback ids]` so the graph shows what each callback depends on. Recommended because the downstream agent gets both "do I implement this?" and "when is it used?" without reading the summary.

两个正交轴。**role** 回答"下游 agent 拿这个术语怎么办"：`callback`（实现运行时判断，需要 wrapper，总结中加粗）、`parameter`（可调数值）、`constraint`（限制回调的硬规则）、`aux_note`（实现者必须阅读的说明）、`scope`（品种/合约/周期适用范围）。**phase** 回答"在交易的哪一步起作用"：`market_context`、`entry`、`position_mgmt`、`exit`、`risk`、`philosophy`。非回调术语通过 `supports` 指向回调，图上能看到每个回调依赖什么。推荐：下游 agent 不读总结也能同时知道"要不要实现"和"何时使用"。

| Term (zh) | name_en | role | phase | supports |
|---|---|---|---|---|
| 大周期方向判定 | major_timeframe_direction | callback → 多/空/不确定 | market_context | — |
| 小周期入场信号 | minor_timeframe_entry_signal | callback → 入场/不入场 | entry | — |
| 有利运动确认 | favorable_move_confirmed | callback → 是/否 | position_mgmt | — |
| 移动止损线位置 | trailing_stop_level | callback → 价格 | position_mgmt | — |
| 大周期趋势反转 | major_trend_reversal | callback → 是/否 | exit | — |
| 大小周期级别差 | timeframe_gap | parameter (1–2 orders of magnitude) | market_context | T001, T002 |
| 尽快但不是立刻 | asap_not_immediately | aux_note | position_mgmt | 有利运动确认 |
| 止损只进不退 | stop_only_tightens | constraint | position_mgmt | 移动止损线位置 |
| 逆向信号过滤 | counter_trend_filter | constraint | entry | 小周期入场信号 |
| 盈亏比阈值 ≥ 3 | payoff_ratio_threshold | parameter | risk | — |
| 零成本持仓 | zero_cost_position | aux_note | philosophy | 有利运动确认 |
| 只交易碳酸锂 | lithium_carbonate_only | scope (dropped in S4 if user trades many varieties) | market_context | — |

## B. `role_only` — Role only / 仅按下游角色

The role axis alone. Simplest; enough when the strategy is short and the summary's section structure already shows when each term is used. The graph loses its phase clusters.

只有 role 轴。最简单；策略较短、总结章节已能说明使用时机时够用。图上没有阶段分组。

## C. `phase_plus_key` — Phase + key flag / 交易阶段 + 关键标记

The phase axis plus a two-valued role axis (`callback` / `aux_note`). Fits users who think in trade stages; parameters and constraints are all "aux_note" here, so the stub's docstrings carry less structure (no separate parameter table).

phase 轴加二值 role 轴（`callback` / `aux_note`）。适合按交易阶段思考的用户；参数和约束都归为 aux_note，桩代码的 docstring 结构较弱（没有单独的参数表）。

## Deciding "callback or not" / 如何判断是否回调

Ask: *at runtime, must someone look at data and make a judgement the text does not fully determine?* Yes → callback. If the text fully determines it (e.g. "ignore signals against the major direction"), it is a constraint on some callback. If it is a number → parameter. If it only explains → aux_note. A callback's output must be enumerable or a concrete value (direction enum, yes/no, a price); if you cannot say what it returns, it is not yet a callback — discuss it in S6.

问：*运行时是否需要有人看数据做出原文没有完全确定的判断？* 是 → 回调。原文完全确定的（如"逆向信号一律忽略"）→ 某回调的约束。是数值 → 参数。只是解释 → 辅助说明。回调的输出必须可枚举或是具体值（方向枚举、是/否、价格）；说不清返回什么的，还不是回调，留到 S6 讨论。

## Adding a value / 新增分类值

Edit `<workspace>/S5_categories.json` (not the template): append to the axis `values` and to the `legend`. `sf_terms.py validate --categories` accepts any value listed there.
