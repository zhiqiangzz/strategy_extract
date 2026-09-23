# S7 — Formalize: callbacks, relations, graph, stub / 形式化：回调、关系、图、桩代码

> Agents: read the English blocks only. 中文仅供人类阅读。

## Goal / 目标

Turn the defined terms into an interface for the downstream trading agent. `S7_formal.json` lists each callback with its invocation point, inputs, output type (usually an enum such as `long/short/uncertain`) and the ids of every auxiliary, constraint and parameter term the implementer must read; each parameter with default/unit/range; and typed relations between terms (`supports`, `constrains`, `parameterizes`, `triggers`, `sequence`, `conflicts`). From it the scripts render a graph and a Python stub class whose method docstrings carry the definitions and notes, so the downstream agent has everything in one file.

把已定义的术语转换为下游交易 agent 的接口。`S7_formal.json` 列出每个回调的调用位置、输入、输出类型（通常是 `long/short/uncertain` 这类枚举）及实现者必须阅读的辅助/约束/参数术语 id；每个参数的默认值/单位/范围；以及术语之间带类型的关系（`supports`、`constrains`、`parameterizes`、`triggers`、`sequence`、`conflicts`）。脚本据此渲染关系图和 Python 桩类，方法 docstring 内含定义与说明，下游 agent 在一个文件里得到全部信息。

## Inputs / 输入

- `S6_terms_defined.json`, `S5_summary_marked.md`, `schemas/formal.schema.json`.

## Outputs / 产出

| File | Content |
|---|---|
| `S7_formal.json` / `.xlsx` | callbacks / parameters / relations as described above. |
| `S7_term_graph.mmd` / `.dot` / `.png` | Graph: nodes = live terms grouped by phase, callbacks bold; edges = relations. png is optional (needs `pixi install`). |
| `S7_callbacks_stub.py` | `class StrategyCallbacks(ABC)` with one abstract method per callback and a `PARAMETERS` dict. Must compile. |

## Procedure / 步骤

1. `SF/sf_state.py start S7`; `SF/sf_formal.py scaffold S6_terms_defined.json S7_formal.json` (creates callbacks, parameters and `supports`-derived relations mechanically).
2. Edit `S7_formal.json`: for each callback set `invoked_in` (`execution_steps.<n>` or `exit_and_risk.<n>` matching the numbered lines of the summary), `inputs` (name + type + which term motivates it), `output` (`type: enum` and `values` in English, e.g. `long, short, uncertain`; or `price`, `bool`), and `description_en` (the definition plus the decision the caller makes with the result). Fill parameters' `default`/`unit`/`range` from the definitions. Add relations the scaffold cannot infer: `sequence` between callbacks in execution order, `triggers` (e.g. favourable_move_confirmed triggers trailing_stop_level), `conflicts` for anything the conflict log left as "both allowed".
3. `SF/sf_formal.py validate S7_formal.json --terms S6_terms_defined.json`.
4. `SF/sf_formal.py gen-stub S7_formal.json --terms S6_terms_defined.json --out S7_callbacks_stub.py`; read the stub once as the downstream implementer would; if a docstring is not enough to implement the method, the term definition is incomplete → fix the definition in `S6_terms_defined.json` (small wording fixes are allowed here; a change of meaning means `reopen S6`).
5. `SF/sf_graph.py render S7_formal.json --terms S6_terms_defined.json --png`; look at the graph for callbacks with no supporting terms and for auxiliary terms attached to nothing.
6. `SF/sf_formal.py to-xlsx S7_formal.json`; `SF/sf_state.py complete S7`; stop; end the turn.

1. `start S7`；`scaffold` 机械生成回调、参数和由 `supports` 推出的关系。
2. 编辑 `S7_formal.json`：为每个回调填 `invoked_in`（对应总结的编号行）、`inputs`、`output`（英文枚举值）和 `description_en`；参数填默认值/单位/范围；补充脚本推不出的关系（回调之间的 `sequence`、`triggers`、冲突日志中"两者皆可"的 `conflicts`）。
3. `validate`。
4. `gen-stub`，以下游实现者的视角读一遍桩代码；docstring 不足以实现 → 术语定义不完整 → 修 `S6_terms_defined.json`（措辞小改可就地，改变含义需 `reopen S6`）。
5. `render --png`，看图检查没有支持术语的回调和悬空的辅助术语。
6. `to-xlsx`、`complete S7`、停止、结束本轮。

## Done criteria / 完成标准

- `sf_formal.py validate` passes with no errors; every callback has non-empty inputs, output values and `description_en`.
- Stub compiles; graph files exist (png if graphviz is available).

## Stop message / 停止消息

Show the callback list with their output enums and point the user to `S7_term_graph.png` (or `.mmd`) and `S7_callbacks_stub.py`; ask whether each method signature is what the downstream agent should implement.
