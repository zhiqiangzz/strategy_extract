# S7 — Formalize: callbacks, relations, graph, stub

> **Agents: follow the English part only (above the "中文版" divider). The Chinese part is a translation for human readers and adds no instructions.**
>
> **说明：agent 执行时只需参考上半部分的英文；下半部分的中文仅供人类阅读，内容相同，不含额外指令。**

## Goal

Turn the defined terms into an interface for the downstream trading agent, and wire that interface into a complete trading logic. `S7_formal.json` lists each callback with its invocation point, inputs, output type (usually an enum such as `long/short/uncertain`) and the ids of every auxiliary, constraint and parameter term the implementer must read; each parameter with default/unit/range; and typed relations between terms (`supports`, `constrains`, `parameterizes`, `triggers`, `sequence`, `conflicts`). From it the scripts render a graph and a Python stub class whose method docstrings carry the definitions and notes. The `flow` section of the same file is the control flow (states + ordered rules, see `references/flow_dsl.md`) that `sf_driver.py` renders into `S7_strategy_driver.py`: a state machine whose `step()` calls the callbacks in the order of the summary's execution steps and returns trading actions. A dry-run with scripted callback results proves the flow before anything downstream exists.

## Inputs

- `S6_terms_defined.json`, `S5_summary_marked.md`, `schemas/formal.schema.json`.

## Outputs

| File | Content |
|---|---|
| `S7_formal.json` / `.xlsx` | callbacks / parameters / relations as described above. |
| `S7_term_graph.mmd` / `.dot` / `.pdf` | Graph: nodes = live terms grouped by phase, callbacks bold; edges = relations. The pdf is rendered by graphviz (needs `pixi install`). |
| `S7_callbacks_stub.py` | The standard interface dataclasses from `templates/callbacks_stub.template.py` (Bar, MarketData, Instrument, Position, EntryDecision, StopDistance, Direction) followed by `class StrategyCallbacks(ABC)` with one abstract, typed method per callback and a `PARAMETERS` dict. Must compile. |
| `S7_strategy_driver.py` | Generated from `flow`: runtime (Action, StepContext, Account, ExecutionPort, RecordingPort, StrategyDriverBase) plus `class StrategyDriver` whose `step(ctx)` is one commented block per flow rule. Imports the stub. Must compile and pass its dry-run scenarios. |

## Procedure

1. `SF/sf_state.py start S7`; `SF/sf_formal.py scaffold S6_terms_defined.json S7_formal.json` (creates callbacks, parameters and `supports`-derived relations mechanically).
2. Edit `S7_formal.json`: for each callback set `invoked_in` (`execution_steps.<n>` or `exit_and_risk.<n>` matching the numbered lines of the summary), `inputs` (name + type + which term motivates it; use the standard type names `MarketData`, `Bar`, `Instrument`, `Position`, `Direction` or scalars `float`/`int`/`bool`/`str`, so the stub is typed identically for every strategy), `output` (`type: enum` with English `values`, e.g. `long, short, uncertain`; or `price`, `bool`, or a standard compound type `EntryDecision` / `StopDistance`), and `description_en` (the definition plus the decision the caller makes with the result); set `schedule` (`trigger`: tick / minor_bar / major_bar / timer, `mode`: sync / async) from the S6 schedule answer recorded in the term's notes. Fill parameters' `default`/`unit`/`range` from the definitions. Add relations the scaffold cannot infer: `sequence` between callbacks in execution order, `triggers` (e.g. favorable_move_confirmed triggers trailing_stop_level), `conflicts` for anything the conflict log left as "both allowed".
3. Author the `flow` section (the scaffold left one placeholder rule per callback): decide the states (FLAT / IN_POSITION is the default; add states only if the strategy really has more, e.g. a partial-exit stage), then write the rules in evaluation order following section 4 of `S5_summary_marked.md` line by line: which state, which `trigger` event (must equal the callback's schedule trigger; `stop_hit` rules on `tick`), which condition, which callback, what to do with its result, which state next, and the `step_ref` of the summary line. Pre-entry rules normally trigger on bar closes; in-position major-timeframe rules on `major_bar`; the stop-hit exit on `tick`. Put the deterministic exits first in the in-position block (stop hit, then reversal), then stop management. Add at least two `dryrun` scenarios (full path through each exit; stop-hit path), each tick carrying its `event`, with callback values given only on their trigger events. Field reference: `references/flow_dsl.md`.
4. `SF/sf_formal.py validate S7_formal.json --terms S6_terms_defined.json` (includes the flow checks) and `SF/sf_driver.py validate S7_formal.json`.
5. `SF/sf_formal.py gen-stub S7_formal.json --terms S6_terms_defined.json --out S7_callbacks_stub.py`; read the stub once as the downstream implementer would; if a docstring is not enough to implement the method, the term definition is incomplete → fix the definition in `S6_terms_defined.json` (small wording fixes are allowed here; a change of meaning means `reopen S6`).
6. `SF/sf_driver.py gen S7_formal.json --terms S6_terms_defined.json --out S7_strategy_driver.py`, then `SF/sf_driver.py dryrun S7_formal.json`. Read the generated `step()` against section 4 once: every numbered step must be visible as a rule block in the same order. Fix the flow, not the generated file.
7. `SF/sf_graph.py render S7_formal.json --terms S6_terms_defined.json --pdf`; look at the graph for callbacks with no supporting terms, auxiliary terms attached to nothing, and the purple flow edges forming the intended order.
8. `SF/sf_formal.py to-xlsx S7_formal.json`; `SF/sf_state.py complete S7`; stop; end the turn.

## Done criteria

- `sf_formal.py validate` passes with no errors; every callback has non-empty inputs, output values and `description_en`.
- Stub compiles; graph files exist (pdf if graphviz is available).
- `sf_driver.py validate` passes (every callback called by a rule, every state reachable); the driver compiles; every dry-run scenario passes.

## Stop message

Show the callback list with their output enums, the flow table (id / state / when / call / then / next) and the dry-run traces; point the user to `S7_term_graph.pdf` (or `.mmd`), `S7_callbacks_stub.py` and `S7_strategy_driver.py`; ask whether each method signature is what the downstream agent should implement and whether the flow matches how they would trade it (the flow sheet of `S7_formal.xlsx` is editable).

---

# 中文版（仅供人类阅读；agent 请参考上方英文）

## 目标

把已定义的术语转换为下游交易 agent 的接口，并把这个接口串成完整的交易逻辑。`S7_formal.json` 列出每个回调的调用位置、输入、输出类型（通常是 `long/short/uncertain` 这类枚举）及实现者必须阅读的辅助/约束/参数术语 id；每个参数的默认值/单位/范围；以及术语之间带类型的关系（`supports`、`constrains`、`parameterizes`、`triggers`、`sequence`、`conflicts`）。脚本据此渲染关系图和 Python 桩类，方法 docstring 内含定义与说明。同一文件的 `flow` 段是控制流（状态 + 有序规则，见 `references/flow_dsl.md`），`sf_driver.py` 把它渲染为 `S7_strategy_driver.py`：一个状态机，其 `step()` 按总结执行步骤的顺序调用回调并返回交易动作。用脚本化的回调结果做 dry-run，在下游任何实现存在之前就验证控制流。

## 输入

- `S6_terms_defined.json`、`S5_summary_marked.md`、`schemas/formal.schema.json`。

## 产出

| 文件 | 内容 |
|---|---|
| `S7_formal.json` / `.xlsx` | 上述的 callbacks / parameters / relations。 |
| `S7_term_graph.mmd` / `.dot` / `.pdf` | 关系图：节点 = 按 phase 分组的存活术语，回调加粗；边 = 关系。pdf 由 graphviz 渲染（需要 `pixi install`）。 |
| `S7_callbacks_stub.py` | 先是 `templates/callbacks_stub.template.py` 中的标准接口 dataclass（Bar、MarketData、Instrument、Position、EntryDecision、StopDistance、Direction），随后是 `class StrategyCallbacks(ABC)`，每个回调一个带类型的抽象方法，另有 `PARAMETERS` 字典。必须可编译。 |
| `S7_strategy_driver.py` | 由 `flow` 生成：运行时（Action、StepContext、Account、ExecutionPort、RecordingPort、StrategyDriverBase）加 `class StrategyDriver`，其 `step(ctx)` 每条 flow 规则一个带注释的代码块。导入桩模块。必须可编译并通过 dry-run 场景。 |

## 步骤

1. `SF/sf_state.py start S7`；`SF/sf_formal.py scaffold S6_terms_defined.json S7_formal.json`（机械生成回调、参数和由 `supports` 推出的关系）。
2. 编辑 `S7_formal.json`：为每个回调填 `invoked_in`（`execution_steps.<n>` 或 `exit_and_risk.<n>`，对应总结的编号行）、`inputs`（名称 + 类型 + 由哪个术语引出；类型使用标准名 `MarketData`、`Bar`、`Instrument`、`Position`、`Direction` 或标量 `float`/`int`/`bool`/`str`，使所有策略的桩代码类型一致）、`output`（`type: enum` 及英文 `values`，如 `long, short, uncertain`；或 `price`、`bool`，或标准复合类型 `EntryDecision` / `StopDistance`）、`description_en`（定义加上调用方拿到结果后做的决定）；按术语 notes 中记录的 S6 调度答案填 `schedule`（`trigger`：tick / minor_bar / major_bar / timer，`mode`：sync / async）。参数的 `default`/`unit`/`range` 从定义中填。补充脚本推不出的关系：回调之间按执行顺序的 `sequence`、`triggers`（如 favorable_move_confirmed 触发 trailing_stop_level）、冲突日志中"两者皆可"的 `conflicts`。
3. 编写 `flow` 段（scaffold 已为每个回调留了一条占位规则）：先定状态（默认 FLAT / IN_POSITION；只有策略确实有更多阶段，如分批出场，才加状态），再按 `S5_summary_marked.md` 第 4 节逐行、按评估顺序写规则：在哪个状态、哪个 `trigger` 事件（须等于回调的 schedule trigger；`stop_hit` 规则在 `tick`）、什么条件、调哪个回调、结果怎么处理、转到哪个状态、以及对应总结行的 `step_ref`。入场前规则通常在 K 线收盘触发；持仓期大周期规则在 `major_bar`；打止损出场在 `tick`。持仓块里先放确定性出场（打止损、再反转），再放止损管理。至少写两个 `dryrun` 场景（走完每条出场路径的正常路径；打止损路径），每个 tick 带 `event`，回调值只在其触发事件上给出。字段说明见 `references/flow_dsl.md`。
4. `SF/sf_formal.py validate S7_formal.json --terms S6_terms_defined.json`（含 flow 检查）及 `SF/sf_driver.py validate S7_formal.json`。
5. `SF/sf_formal.py gen-stub S7_formal.json --terms S6_terms_defined.json --out S7_callbacks_stub.py`；以下游实现者的视角读一遍桩代码；若 docstring 不足以实现该方法，说明术语定义不完整 → 修 `S6_terms_defined.json`（措辞小改可就地进行；改变含义则 `reopen S6`）。
6. `SF/sf_driver.py gen S7_formal.json --terms S6_terms_defined.json --out S7_strategy_driver.py`，然后 `SF/sf_driver.py dryrun S7_formal.json`。对照第 4 节读一遍生成的 `step()`：每个编号步骤都应以同样顺序出现为一个规则块。有问题改 flow，不改生成的文件。
7. `SF/sf_graph.py render S7_formal.json --terms S6_terms_defined.json --pdf`；看图检查没有支持术语的回调、悬空的辅助术语，以及紫色 flow 边是否构成预期顺序。
8. `SF/sf_formal.py to-xlsx S7_formal.json`；`SF/sf_state.py complete S7`；停止；结束本轮。

## 完成标准

- `sf_formal.py validate` 无错误；每个回调的输入、输出取值、`description_en` 均非空。
- 桩代码可编译；图文件存在（有 graphviz 则含 pdf）。
- `sf_driver.py validate` 通过（每个回调都被某条规则调用、每个状态可达）；driver 可编译；所有 dry-run 场景通过。

## 停止消息

展示回调列表及其输出枚举、flow 表（id / state / when / call / then / next）和 dry-run 轨迹；指引用户查看 `S7_term_graph.pdf`（或 `.mmd`）、`S7_callbacks_stub.py` 和 `S7_strategy_driver.py`；询问每个方法签名是否就是下游 agent 应实现的、以及 flow 是否符合他们的交易方式（`S7_formal.xlsx` 的 flow 表可编辑）。
