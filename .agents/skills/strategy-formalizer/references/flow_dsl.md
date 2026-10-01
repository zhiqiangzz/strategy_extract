# Flow DSL — wiring the callbacks into a driver

> **Agents: follow the English part only (above the "中文版" divider). The Chinese part is a translation for human readers and adds no instructions.**
>
> **说明：agent 执行时只需参考上半部分的英文；下半部分的中文仅供人类阅读，内容相同，不含额外指令。**

## What the flow is

The `flow` section of `S7_formal.json` is the strategy's control flow: the code-level counterpart of section 4 (execution steps) and section 5 (exit and risk) of the summary. `sf_driver.py gen` renders it into `S7_strategy_driver.py`, a class whose `step(ctx)` method is evaluated by the downstream agent whenever new data arrives (every minor-timeframe bar, every tick, or any cadence it chooses; callbacks decide their own re-evaluation timing internally). `step()` walks the rules top to bottom, calls callbacks, and returns a list of `Action`s; the downstream agent executes them through its `ExecutionPort` and keeps the `Position` current. The driver never places orders. Two things are built in rather than delegated: the stop-hit test (exit path one) and position sizing from the per-trade risk fraction.

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

Each scenario scripts what the callbacks return at each evaluation ("tick") and what action trace is expected. `sf_driver.py dryrun` runs the generated driver with those scripted callbacks and `RecordingPort`, prints the trace and fails on mismatch. Compound outputs are given as dicts and turned into `EntryDecision` / `StopDistance` automatically.

```json
{"name": "trend_then_reversal", "note_zh": "入场→移损至成本→移动止损→反转清仓",
 "account": {"capital": 1000000, "per_trade_loss_ratio": 0.01}, "multiplier": 10,
 "ticks": [
   {"last_price": 100, "CB01": "long", "CB02": {"decision": "enter", "entry_price": 100}, "CB03": {"value": 2, "unit": "points"}},
   {"last_price": 103, "CB01": "long", "CB05": false, "CB06": true},
   {"last_price": 106, "CB01": "long", "CB05": false, "CB04": 103.0},
   {"last_price": 104, "CB01": "uncertain", "CB05": true}],
 "expect": ["enter", "move_stop_to_cost", "move_stop", "close:reversal"]}
```

Action labels: `enter`, `move_stop_to_cost`, `move_stop`, `set_stop`, `close:<reason>`. A callback that is called at a tick without a scripted value makes the dry-run fail, which catches rules that fire when they should not. Write at least two scenarios: the happy path through every exit, and the stop-hit path.

## Worked example (大小周期共振)

| id | state | when | call → bind | when_result | then | next | step_ref |
|---|---|---|---|---|---|---|---|
| F01 | * | | CB01 → direction | | | | execution_steps.1 |
| F02 | FLAT | direction in ('long','short') | CB02 → entry (args major_direction=direction) | | | | execution_steps.2 |
| F03 | FLAT | entry is not None and entry.decision == 'enter' | CB03 → stop (args entry_price=entry.entry_price) | | enter | IN_POSITION | execution_steps.3 |
| F04 | IN_POSITION | stop_hit | | | close:stop | FLAT | exit_and_risk.4 |
| F05 | IN_POSITION | | CB05 → reversed (args major_direction=direction) | reversed | close:reversal | FLAT | execution_steps.5 |
| F06 | IN_POSITION | not position.stop_at_cost | CB06 → favorable | favorable | move_stop_to_cost | | execution_steps.4 |
| F07 | IN_POSITION | position.stop_at_cost | CB04 → new_stop | new_stop is not None | move_stop | | execution_steps.5 |

Reading it as prose: refresh the major direction; when flat and the direction is definite, ask for an entry signal; on "enter", get the stop distance, enter and switch to IN_POSITION; when in a position, first the stop-hit exit, then the reversal exit, then move to cost once, then trail.

## Runtime contract (from templates/strategy_driver.template.py)

- `StepContext(instrument, major_tf_data, minor_tf_data, position, major_tf_context, last_price, now)` is built by the downstream agent before each call.
- `Account(capital, per_trade_loss_ratio)` sizes entries: contracts = floor(capital × ratio / (stop distance × multiplier)).
- `ExecutionPort.enter / set_stop / close` are implemented downstream; `set_stop` with reason `cost` must set `position.stop_at_cost = True`.
- `RecordingPort` is the in-memory reference used by the dry-run and tests.

---

# 中文版（仅供人类阅读；agent 请参考上方英文）

## flow 是什么

`S7_formal.json` 的 `flow` 段是策略的控制流：总结第 4 节（执行步骤）和第 5 节（出场与风控）在代码层面的对应物。`sf_driver.py gen` 把它渲染为 `S7_strategy_driver.py`，其 `step(ctx)` 方法由下游 agent 在新数据到达时调用（每根小周期 K 线、每个 tick 或任意节奏；回调内部自行决定重新评估的时机）。`step()` 按顺序走一遍规则、调用回调，返回一组 `Action`；下游 agent 通过自己实现的 `ExecutionPort` 执行它们并维护 `Position`。driver 不下单。两件事内置而非委托：止损触发判断（出场路径一）和按单笔风险比例计算仓位。

## 结构

见英文部分的 JSON 示例：`initial_state`、`states`、`rules`、`dryrun`。

## 规则字段

| 字段 | 含义 |
|---|---|
| `id` | `F01`、`F02`…，按评估顺序。 |
| `state` | 规则适用的状态，`*` 表示所有状态。 |
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

每个场景写明各回调在每次评估（tick）返回什么、期望的动作轨迹是什么。`sf_driver.py dryrun` 用这些脚本化回调和 `RecordingPort` 跑生成的 driver，打印轨迹，不符则失败。复合输出写成字典，自动构造为 `EntryDecision` / `StopDistance`。格式见英文部分示例。动作标签：`enter`、`move_stop_to_cost`、`move_stop`、`set_stop`、`close:<原因>`。某 tick 被调用却没有脚本值的回调会使 dry-run 失败，用于捕捉不该触发的规则。至少写两个场景：走完每条出场路径的正常路径，以及打止损路径。

## 示例（大小周期共振）

见英文部分的表格。读成文字：先刷新大周期方向；空仓且方向明确时问入场信号；信号为入场时取止损距离、开仓并转入 IN_POSITION；持仓时先看止损是否被打，再看是否反转，然后移损至成本一次，之后移动止损。

## 运行时契约（来自 templates/strategy_driver.template.py）

- `StepContext(instrument, major_tf_data, minor_tf_data, position, major_tf_context, last_price, now)` 由下游 agent 在每次调用前构造。
- `Account(capital, per_trade_loss_ratio)` 计算开仓手数：floor(本金 × 比例 / (止损价差 × 合约乘数))。
- `ExecutionPort.enter / set_stop / close` 由下游实现；原因为 `cost` 的 `set_stop` 必须置 `position.stop_at_cost = True`。
- `RecordingPort` 是 dry-run 与测试使用的内存版参考实现。
