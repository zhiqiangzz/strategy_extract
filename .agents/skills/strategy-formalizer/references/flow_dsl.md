# Flow DSL — wiring the callbacks into a driver

> **Agents: follow the English part only (above the "中文版" divider). The Chinese part is a translation for human readers and adds no instructions.**
>
> **说明：agent 执行时只需参考上半部分的英文；下半部分的中文仅供人类阅读，内容相同，不含额外指令。**

## What the flow is

The `flow` section of `S7_formal.json` is the strategy's control flow: the code-level counterpart of section 4 (execution steps) and section 5 (exit and risk) of the summary. `sf_driver.py gen` renders it into `S7_strategy_driver.py`, a class whose `on_event(event, ctx)` method the downstream agent calls on each scheduling event: `tick` (new price), `minor_bar` (minor-timeframe bar closed), `major_bar` (major-timeframe bar closed), `timer`. Each rule names its `trigger` event; on that event it runs (calling its callback), on other events it is skipped and its callback's last result is read from the driver's `SignalCache`. That is how the pre-entry phase (direction and entry signal polled on bar closes), the in-position phase (slow major-timeframe judgements for exits and stop management) and tick-level stop checks share one deterministic driver. `on_event()` walks the rules top to bottom and returns a list of `Action`s; the downstream agent executes them through its `ExecutionPort` and keeps the `Position` current. The driver never places orders. Two things are built in rather than delegated: the stop-hit test (exit path one) and position sizing from the per-trade risk fraction.

## Callback schedule

Every callback in `formal.json` carries `schedule: {trigger, mode}` decided in S6: `trigger` is the event on which it is re-evaluated (`tick`, `minor_bar`, `major_bar`, `timer`, or `on_demand` when the downstream caller decides the cadence and calls `on_event("on_demand", ctx)` itself); `mode` is `sync` (the implementation returns the result) or `async` (a slow judgement: the implementation must return immediately, and may return `None` to keep the previous cached value while a thread or coroutine computes the new one; the downstream agent then hands the result back through the next call). The driver never spawns threads itself; the schedule tells the downstream agent what to run where. A rule's `trigger` must equal its callback's `schedule.trigger`.

## Structure

```json
"flow": {
  "initial_state": "FLAT",
  "states": [{"id": "FLAT", "name_zh": "空仓"}, {"id": "IN_POSITION", "name_zh": "持仓"}],
  "rules": [ { ...rule... }, ... ],
  "dryrun": [ { ...scenario... }, ... ]
}
```

## Rule fields

| Field | Meaning |
|---|---|
| `id` | `F01`, `F02`, … in evaluation order. |
| `state` | State the rule applies to, or `*` for every state. |
| `trigger` | Event the rule runs on: `tick`, `minor_bar`, `major_bar`, `timer`, `on_demand` (caller-paced), or `*` (every event). Must equal the called callback's `schedule.trigger`. A rule testing `stop_hit` must run on `tick`. |
| `when` | Python boolean expression; empty = always. Namespace: `state`, `position`, `ctx`, `stop_hit`, every `bind` name of earlier rules, `None/True/False`. Only comparisons, boolean operators, arithmetic and attribute access one level deep (`entry.entry_price`, `position.stop_at_cost`) are allowed; no calls. |
| `call` | Callback id (`CB01`) to invoke, or empty for a built-in-only rule (e.g. the stop-hit exit). |
| `args` | Map `input_name → expression` for callback inputs that cannot be resolved automatically. Resolution order: `args`, a bind with the same name, a `StepContext` field with the same name (`instrument`, `major_tf_data`, `minor_tf_data`, `major_tf_context`, `position`, `last_price`, `now`). |
| `bind` | Name under which the call's result is available to later rules in the same evaluation. |
| `when_result` | Boolean expression over the namespace plus this rule's bind; `then` fires only if it is true (empty = fire unconditionally when `then` is set). |
| `then` | Built-in action: `enter`, `close:<reason>`, `move_stop_to_cost`, `move_stop` (uses this rule's bind as the new stop; "only tightens" is enforced by the runtime), `set_stop`, or empty. |
| `uses` | Only for `enter`: where to find `direction`, `entry_price`, `stop` (defaults `direction`, `entry.entry_price`, this rule's bind). |
| `next` | State to move to after the action; a rule whose `next` fires ends the evaluation. |
| `step_ref` | The summary line the rule implements: `execution_steps.3`, `exit_and_risk.4`, or a range `execution_steps.2-3`. S8 checks that every bold callback line of section 4 is referenced. |
| `note_en` / `note_zh` | Free comment, copied into the generated code. |

## Dry-run scenarios

Each scenario scripts a sequence of events (`event`: tick / minor_bar / major_bar / timer, default tick) with the price and what the callbacks return at that event, and the expected action trace. A callback is only consulted on its trigger event, so give values only there; an `async` callback scripted as `null` keeps its cached value. `sf_driver.py dryrun` runs the generated driver with those scripted callbacks and `RecordingPort`, prints the trace and fails on mismatch. Compound outputs are given as dicts and turned into `EntryDecision` / `StopDistance` automatically.

```json
{"name": "trend_then_reversal", "note_zh": "入场→移损至成本→移动止损→反转清仓",
 "account": {"capital": 1000000, "per_trade_loss_ratio": 0.01}, "multiplier": 10,
 "ticks": [
   {"event": "major_bar", "last_price": 100, "CB01": "long"},
   {"event": "minor_bar", "last_price": 100, "CB02": {"decision": "enter", "entry_price": 100}, "CB03": {"value": 2, "unit": "points"}},
   {"event": "tick", "last_price": 101},
   {"event": "major_bar", "last_price": 103, "CB01": "long", "CB05": false, "CB06": true},
   {"event": "major_bar", "last_price": 106, "CB01": "long", "CB05": false, "CB04": 103.0},
   {"event": "major_bar", "last_price": 104, "CB01": "uncertain", "CB05": true}],
 "expect": ["enter", "move_stop_to_cost", "move_stop", "close:reversal"]}
```

Action labels: `enter`, `move_stop_to_cost`, `move_stop`, `set_stop`, `close:<reason>`. A callback that is called at a tick without a scripted value makes the dry-run fail, which catches rules that fire when they should not. Write at least two scenarios: the happy path through every exit, and the stop-hit path.

## Worked example (大小周期共振)

| id | state | trigger | when | call → bind | when_result | then | next | step_ref |
|---|---|---|---|---|---|---|---|---|
| F01 | * | major_bar | | CB01 → direction (async) | | | | execution_steps.1 |
| F02 | FLAT | minor_bar | direction in ('long','short') | CB02 → entry (args major_direction=direction) | | | | execution_steps.2 |
| F03 | FLAT | minor_bar | entry is not None and entry.decision == 'enter' | CB03 → stop (args entry_price=entry.entry_price) | | enter | IN_POSITION | execution_steps.3 |
| F04 | IN_POSITION | tick | stop_hit | | | close:stop | FLAT | exit_and_risk.4 |
| F05 | IN_POSITION | major_bar | | CB05 → reversed (args major_direction=direction, async) | reversed | close:reversal | FLAT | execution_steps.5 |
| F06 | IN_POSITION | major_bar | not position.stop_at_cost | CB06 → favorable (async) | favorable | move_stop_to_cost | | execution_steps.4 |
| F07 | IN_POSITION | major_bar | position.stop_at_cost | CB04 → new_stop (async) | new_stop is not None | move_stop | | execution_steps.5 |

Reading it as prose: on every major bar refresh the direction (slow, may be async); on every minor bar while flat and the direction is definite, ask for an entry signal and, on "enter", get the stop distance, enter and switch to IN_POSITION; on every tick while in a position, check the stop; on every major bar while in a position, check reversal, then move to cost once, then trail. Between major bars no major-timeframe callback is called.

## Runtime contract (from templates/strategy_driver.template.py)

- `on_event(event, ctx)` is called by the downstream agent on `tick`, `minor_bar`, `major_bar` or `timer`; `step(ctx)` is shorthand for a tick.
- `SignalCache` keeps every callback's latest result; `cache.age(name)` gives the number of events since it was produced.
- `StepContext(instrument, major_tf_data, minor_tf_data, position, major_tf_context, last_price, now)` is built by the downstream agent before each call.
- `Account(capital, per_trade_loss_ratio)` sizes entries: contracts = floor(capital × ratio / (stop distance × multiplier)).
- `ExecutionPort.enter / set_stop / close` are implemented downstream; `set_stop` with reason `cost` must set `position.stop_at_cost = True`.
- `RecordingPort` is the in-memory reference used by the dry-run and tests.

---

# 中文版（仅供人类阅读；agent 请参考上方英文）

## flow 是什么

`S7_formal.json` 的 `flow` 段是策略的控制流：总结第 4 节（执行步骤）和第 5 节（出场与风控）在代码层面的对应物。`sf_driver.py gen` 把它渲染为 `S7_strategy_driver.py`，其 `on_event(event, ctx)` 方法由下游 agent 在每个调度事件上调用：`tick`（新价格）、`minor_bar`（小周期 K 线收盘）、`major_bar`（大周期 K 线收盘）、`timer`。每条规则声明自己的 `trigger` 事件；在该事件上执行（调用回调），其他事件上跳过并从 driver 的 `SignalCache` 读取其回调上次的结果。入场前阶段（按 K 线收盘轮询方向与入场信号）、持仓阶段（用于出场与止损管理的慢速大周期判断）与 tick 级止损检查就这样共用一个确定性的 driver。`on_event()` 按顺序走一遍规则，返回一组 `Action`；下游 agent 通过自己实现的 `ExecutionPort` 执行它们并维护 `Position`。driver 不下单。两件事内置而非委托：止损触发判断（出场路径一）和按单笔风险比例计算仓位。

## 回调调度

`formal.json` 中每个回调带 `schedule: {trigger, mode}`，在 S6 商定：`trigger` 是重新评估的事件（`tick`、`minor_bar`、`major_bar`、`timer`，或 `on_demand`：由下游调用方决定频率并自行调用 `on_event("on_demand", ctx)`）；`mode` 为 `sync`（实现直接返回结果）或 `async`（慢判断：实现必须立即返回，可返回 `None` 以沿用缓存值，由线程或协程计算新值后在下次调用交回）。driver 自己不开线程；schedule 告诉下游该在哪里跑什么。规则的 `trigger` 必须等于其回调的 `schedule.trigger`。

## 结构

见英文部分的 JSON 示例：`initial_state`、`states`、`rules`、`dryrun`。

## 规则字段

| 字段 | 含义 |
|---|---|
| `id` | `F01`、`F02`…，按评估顺序。 |
| `state` | 规则适用的状态，`*` 表示所有状态。 |
| `trigger` | 规则执行的事件：`tick`、`minor_bar`、`major_bar`、`timer`、`on_demand`（调用方定频率）或 `*`（所有事件）。必须等于所调用回调的 `schedule.trigger`。判断 `stop_hit` 的规则必须在 `tick` 上执行。 |
| `when` | Python 布尔表达式；空 = 总是。命名空间：`state`、`position`、`ctx`、`stop_hit`、此前规则的所有 `bind` 名、`None/True/False`。只允许比较、布尔运算、算术和一级属性访问（`entry.entry_price`、`position.stop_at_cost`）；不允许函数调用。 |
| `call` | 要调用的回调 id（`CB01`），空表示只用内置逻辑的规则（如止损出场）。 |
| `args` | 无法自动解析的回调输入的映射 `输入名 → 表达式`。解析顺序：`args`、同名 bind、同名 `StepContext` 字段（`instrument`、`major_tf_data`、`minor_tf_data`、`major_tf_context`、`position`、`last_price`、`now`）。 |
| `bind` | 调用结果在本次评估中供后续规则使用的名字。 |
| `when_result` | 命名空间加本规则 bind 上的布尔表达式；为真时才执行 `then`（空 = 只要有 `then` 就执行）。 |
| `then` | 内置动作：`enter`、`close:<原因>`、`move_stop_to_cost`、`move_stop`（以本规则的 bind 为新止损；"只进不退"由运行时强制）、`set_stop`，或空。 |
| `uses` | 仅 `enter` 用：从哪里取 `direction`、`entry_price`、`stop`（默认 `direction`、`entry.entry_price`、本规则的 bind）。 |
| `next` | 动作之后转到的状态；`next` 生效的规则结束本次评估。 |
| `step_ref` | 规则实现的总结行：`execution_steps.3`、`exit_and_risk.4` 或范围 `execution_steps.2-3`。S8 检查第 4 节每个含加粗回调的行都被引用。 |
| `note_en` / `note_zh` | 自由注释，会复制到生成的代码里。 |

## dry-run 场景

每个场景是一串事件（`event`：tick / minor_bar / major_bar / timer，默认 tick），每个事件给出价格和各回调在该事件上的返回值，以及期望的动作轨迹。回调只在其触发事件上被咨询，因此只在那里给值；`async` 回调写 `null` 表示沿用缓存值。`sf_driver.py dryrun` 用这些脚本化回调和 `RecordingPort` 跑生成的 driver，打印轨迹，不符则失败。复合输出写成字典，自动构造为 `EntryDecision` / `StopDistance`。格式见英文部分示例。动作标签：`enter`、`move_stop_to_cost`、`move_stop`、`set_stop`、`close:<原因>`。某 tick 被调用却没有脚本值的回调会使 dry-run 失败，用于捕捉不该触发的规则。至少写两个场景：走完每条出场路径的正常路径，以及打止损路径。

## 示例（大小周期共振）

见英文部分的表格。读成文字：每根大周期 K 线收盘刷新方向（慢判断，可异步）；空仓且方向明确时，每根小周期 K 线收盘问入场信号，信号为入场则取止损距离、开仓并转入 IN_POSITION；持仓时每个 tick 检查止损；每根大周期 K 线收盘检查反转，然后移损至成本一次，之后移动止损。大周期 K 线之间不调用任何大周期回调。

## 运行时契约（来自 templates/strategy_driver.template.py）

- `on_event(event, ctx)` 由下游 agent 在 `tick`、`minor_bar`、`major_bar`、`timer` 上调用；`step(ctx)` 等价于一次 tick。
- `SignalCache` 保存每个回调的最新结果；`cache.age(name)` 给出产生以来经过的事件数。
- `StepContext(instrument, major_tf_data, minor_tf_data, position, major_tf_context, last_price, now)` 由下游 agent 在每次调用前构造。
- `Account(capital, per_trade_loss_ratio)` 计算开仓手数：floor(本金 × 比例 / (止损价差 × 合约乘数))。
- `ExecutionPort.enter / set_stop / close` 由下游实现；原因为 `cost` 的 `set_stop` 必须置 `position.stop_at_cost = True`。
- `RecordingPort` 是 dry-run 与测试使用的内存版参考实现。
