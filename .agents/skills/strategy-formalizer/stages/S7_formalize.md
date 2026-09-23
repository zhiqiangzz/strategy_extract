# S7 — Formalize: callbacks, relations, graph, stub

> **Agents: follow the English part only (above the "中文版" divider). The Chinese part is a translation for human readers and adds no instructions.**
>
> **说明：agent 执行时只需参考上半部分的英文；下半部分的中文仅供人类阅读，内容相同，不含额外指令。**

## Goal

Turn the defined terms into an interface for the downstream trading agent. `S7_formal.json` lists each callback with its invocation point, inputs, output type (usually an enum such as `long/short/uncertain`) and the ids of every auxiliary, constraint and parameter term the implementer must read; each parameter with default/unit/range; and typed relations between terms (`supports`, `constrains`, `parameterizes`, `triggers`, `sequence`, `conflicts`). From it the scripts render a graph and a Python stub class whose method docstrings carry the definitions and notes, so the downstream agent has everything in one file.

## Inputs

- `S6_terms_defined.json`, `S5_summary_marked.md`, `schemas/formal.schema.json`.

## Outputs

| File | Content |
|---|---|
| `S7_formal.json` / `.xlsx` | callbacks / parameters / relations as described above. |
| `S7_term_graph.mmd` / `.dot` / `.pdf` | Graph: nodes = live terms grouped by phase, callbacks bold; edges = relations. The pdf is rendered by graphviz (needs `pixi install`). |
| `S7_callbacks_stub.py` | The standard interface dataclasses from `templates/callbacks_stub.template.py` (Bar, MarketData, Instrument, Position, EntryDecision, StopDistance, Direction) followed by `class StrategyCallbacks(ABC)` with one abstract, typed method per callback and a `PARAMETERS` dict. Must compile. |

## Procedure

1. `SF/sf_state.py start S7`; `SF/sf_formal.py scaffold S6_terms_defined.json S7_formal.json` (creates callbacks, parameters and `supports`-derived relations mechanically).
2. Edit `S7_formal.json`: for each callback set `invoked_in` (`execution_steps.<n>` or `exit_and_risk.<n>` matching the numbered lines of the summary), `inputs` (name + type + which term motivates it; use the standard type names `MarketData`, `Bar`, `Instrument`, `Position`, `Direction` or scalars `float`/`int`/`bool`/`str`, so the stub is typed identically for every strategy), `output` (`type: enum` with English `values`, e.g. `long, short, uncertain`; or `price`, `bool`, or a standard compound type `EntryDecision` / `StopDistance`), and `description_en` (the definition plus the decision the caller makes with the result). Fill parameters' `default`/`unit`/`range` from the definitions. Add relations the scaffold cannot infer: `sequence` between callbacks in execution order, `triggers` (e.g. favorable_move_confirmed triggers trailing_stop_level), `conflicts` for anything the conflict log left as "both allowed".
3. `SF/sf_formal.py validate S7_formal.json --terms S6_terms_defined.json`.
4. `SF/sf_formal.py gen-stub S7_formal.json --terms S6_terms_defined.json --out S7_callbacks_stub.py`; read the stub once as the downstream implementer would; if a docstring is not enough to implement the method, the term definition is incomplete → fix the definition in `S6_terms_defined.json` (small wording fixes are allowed here; a change of meaning means `reopen S6`).
5. `SF/sf_graph.py render S7_formal.json --terms S6_terms_defined.json --pdf`; look at the graph for callbacks with no supporting terms and for auxiliary terms attached to nothing.
6. `SF/sf_formal.py to-xlsx S7_formal.json`; `SF/sf_state.py complete S7`; stop; end the turn.

## Done criteria

- `sf_formal.py validate` passes with no errors; every callback has non-empty inputs, output values and `description_en`.
- Stub compiles; graph files exist (pdf if graphviz is available).

## Stop message

Show the callback list with their output enums and point the user to `S7_term_graph.pdf` (or `.mmd`) and `S7_callbacks_stub.py`; ask whether each method signature is what the downstream agent should implement.

---

# 中文版（仅供人类阅读；agent 请参考上方英文）

## 目标

把已定义的术语转换为下游交易 agent 的接口。`S7_formal.json` 列出每个回调的调用位置、输入、输出类型（通常是 `long/short/uncertain` 这类枚举）及实现者必须阅读的辅助/约束/参数术语 id；每个参数的默认值/单位/范围；以及术语之间带类型的关系（`supports`、`constrains`、`parameterizes`、`triggers`、`sequence`、`conflicts`）。脚本据此渲染关系图和 Python 桩类，方法 docstring 内含定义与说明，下游 agent 在一个文件里得到全部信息。

## 输入

- `S6_terms_defined.json`、`S5_summary_marked.md`、`schemas/formal.schema.json`。

## 产出

| 文件 | 内容 |
|---|---|
| `S7_formal.json` / `.xlsx` | 上述的 callbacks / parameters / relations。 |
| `S7_term_graph.mmd` / `.dot` / `.pdf` | 关系图：节点 = 按 phase 分组的存活术语，回调加粗；边 = 关系。pdf 由 graphviz 渲染（需要 `pixi install`）。 |
| `S7_callbacks_stub.py` | 先是 `templates/callbacks_stub.template.py` 中的标准接口 dataclass（Bar、MarketData、Instrument、Position、EntryDecision、StopDistance、Direction），随后是 `class StrategyCallbacks(ABC)`，每个回调一个带类型的抽象方法，另有 `PARAMETERS` 字典。必须可编译。 |

## 步骤

1. `SF/sf_state.py start S7`；`SF/sf_formal.py scaffold S6_terms_defined.json S7_formal.json`（机械生成回调、参数和由 `supports` 推出的关系）。
2. 编辑 `S7_formal.json`：为每个回调填 `invoked_in`（`execution_steps.<n>` 或 `exit_and_risk.<n>`，对应总结的编号行）、`inputs`（名称 + 类型 + 由哪个术语引出；类型使用标准名 `MarketData`、`Bar`、`Instrument`、`Position`、`Direction` 或标量 `float`/`int`/`bool`/`str`，使所有策略的桩代码类型一致）、`output`（`type: enum` 及英文 `values`，如 `long, short, uncertain`；或 `price`、`bool`，或标准复合类型 `EntryDecision` / `StopDistance`）、`description_en`（定义加上调用方拿到结果后做的决定）。参数的 `default`/`unit`/`range` 从定义中填。补充脚本推不出的关系：回调之间按执行顺序的 `sequence`、`triggers`（如 favorable_move_confirmed 触发 trailing_stop_level）、冲突日志中"两者皆可"的 `conflicts`。
3. `SF/sf_formal.py validate S7_formal.json --terms S6_terms_defined.json`。
4. `SF/sf_formal.py gen-stub S7_formal.json --terms S6_terms_defined.json --out S7_callbacks_stub.py`；以下游实现者的视角读一遍桩代码；若 docstring 不足以实现该方法，说明术语定义不完整 → 修 `S6_terms_defined.json`（措辞小改可就地进行；改变含义则 `reopen S6`）。
5. `SF/sf_graph.py render S7_formal.json --terms S6_terms_defined.json --pdf`；看图检查没有支持术语的回调和悬空的辅助术语。
6. `SF/sf_formal.py to-xlsx S7_formal.json`；`SF/sf_state.py complete S7`；停止；结束本轮。

## 完成标准

- `sf_formal.py validate` 无错误；每个回调的输入、输出取值、`description_en` 均非空。
- 桩代码可编译；图文件存在（有 graphviz 则含 pdf）。

## 停止消息

展示回调列表及其输出枚举，指引用户查看 `S7_term_graph.pdf`（或 `.mmd`）和 `S7_callbacks_stub.py`；询问每个方法签名是否就是下游 agent 应实现的。
