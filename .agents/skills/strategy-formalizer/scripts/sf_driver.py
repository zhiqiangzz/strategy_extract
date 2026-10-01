#!/usr/bin/env python3
"""
Agents: read the English part of every docstring only. 中文段落仅供人类阅读。

sf_driver.py — S7 strategy driver: generate, validate and dry-run the control
flow that wires the callback stubs into a complete trading logic.

The control flow lives in the `flow` section of S7_formal.json: a list of
states (e.g. FLAT, IN_POSITION) and an ordered list of rules. Each rule says:
in which state it applies, under which condition (`when`, a Python boolean
expression over a fixed namespace), which callback to call (`call`) and under
what name to keep its result (`bind`), which built-in action to emit when the
result satisfies `when_result` (`then`: enter, close:<reason>, move_stop_to_cost,
move_stop, set_stop), and which state to move to (`next`). Each rule also names its
`trigger` event (tick / minor_bar / major_bar / timer): the rule runs only on
that event and on other events its callback's last result is read from the
driver's signal cache, so slow major-timeframe judgements and tick-level stop
checks coexist. Callbacks carry a `schedule` (trigger + sync/async) that the
rule triggers must agree with. `gen` renders the rules into a readable
`on_event()` method appended to templates/strategy_driver.template.py; `validate` checks the spec (every
callback used, states reachable, expressions restricted to the namespace,
callback inputs resolvable); `dryrun` imports the generated driver, feeds it
scripted callback results from `flow.dryrun`, applies the actions with
RecordingPort and compares the action trace with the scenario's `expect`.

    sf_driver.py gen      S7_formal.json --terms S6_terms_defined.json --out S7_strategy_driver.py [--stub-module S7_callbacks_stub]
    sf_driver.py validate S7_formal.json
    sf_driver.py dryrun   S7_formal.json --driver S7_strategy_driver.py [--scenario <name>]

sf_driver.py 负责 S7 的策略 driver：生成、校验并 dry-run 把回调桩串成完整交易逻辑的控制流。
控制流写在 S7_formal.json 的 `flow` 段：状态列表（如 FLAT、IN_POSITION）和有序的规则列表。
每条规则说明：适用于哪个状态、满足什么条件（`when`，固定命名空间上的 Python 布尔表达式）、
调用哪个回调（`call`）并以什么名字保存结果（`bind`）、结果满足 `when_result` 时发出哪个内置
动作（`then`：enter、close:<原因>、move_stop_to_cost、move_stop、set_stop）、以及转到哪个状态
（`next`）。每条规则还声明自己的 `trigger`
事件（tick / minor_bar / major_bar / timer）：规则只在该事件上执行，其他事件上从 driver 的信号
缓存读取其回调上次的结果，因此慢速的大周期判断与 tick 级止损检查可以共存。回调带有 `schedule`
（触发事件 + sync/async），规则的 trigger 必须与之一致。`gen` 把规则渲染成可读的 `on_event()`
方法并接在 templates/strategy_driver.template.py 之后；`validate` 检查规格（每个回调被使用、状态可达、表达式只用命名空间内的名字、回调输入可
解析）；`dryrun` 导入生成的 driver，用 `flow.dryrun` 中脚本化的回调结果驱动它，用 RecordingPort
应用动作，并把动作轨迹与场景的 `expect` 比较。
"""
from __future__ import annotations

import argparse
import ast
import importlib.util
import re
import sys
from pathlib import Path

from sf_common import SUMMARY_SECTIONS, TEMPLATES_DIR, fail, load_json, now_iso, read_text, relpath, resolve_workspace, say

ACTIONS = ("enter", "close", "move_stop_to_cost", "move_stop", "set_stop")
EVENTS = ("tick", "minor_bar", "major_bar", "timer")
MODES = ("sync", "async")
CTX_FIELDS = ("instrument", "major_tf_data", "minor_tf_data", "major_tf_context", "position", "last_price", "now", "extra")
BASE_NAMES = {"state", "position", "ctx", "stop_hit", "None", "True", "False"}
STUB_TYPES = ("StrategyCallbacks", "Position", "Instrument", "MarketData", "Bar", "EntryDecision", "StopDistance", "Direction")
RULE_COLUMNS = ("id", "state", "trigger", "when", "call", "bind", "args", "when_result", "then", "next", "step_ref", "note_en", "note_zh")
_ALLOWED_NODES = (ast.Expression, ast.BoolOp, ast.UnaryOp, ast.Compare, ast.Name, ast.Attribute, ast.Constant,
                  ast.Tuple, ast.List, ast.And, ast.Or, ast.Not, ast.USub, ast.BinOp, ast.Add, ast.Sub, ast.Mult,
                  ast.Div, ast.Load, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn,
                  ast.Is, ast.IsNot, ast.IfExp)


def ws_path(ws_arg: str | None, p: str) -> Path:
    """
    Resolve a file argument against the active workspace.

    相对活动 workspace 解析文件参数。
    """
    path = Path(p)
    if path.is_absolute() or path.exists():
        return path
    return resolve_workspace(ws_arg) / p


# --------------------------------------------------------------------------- #
# Expression checking
# --------------------------------------------------------------------------- #


def check_expression(expr: str, names: set[str]) -> str | None:
    """
    Return an error message if `expr` is not a safe condition: it must parse
    as a single Python expression, use only boolean/comparison/arithmetic
    nodes, reference only `names`, and not chain attributes deeper than two
    levels (e.g. `entry.entry_price` is fine, `a.b.c` is not). Returns None
    when the expression is acceptable; an empty expression is acceptable.

    若 `expr` 不是安全条件则返回错误信息：必须能解析为单个 Python 表达式，只使用布尔/比较/算术
    节点，只引用 `names` 中的名字，属性链不超过两级（`entry.entry_price` 可以，`a.b.c` 不行）。
    可接受时返回 None；空表达式可接受。
    """
    if not expr or not expr.strip():
        return None
    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except SyntaxError as exc:
        return f"syntax error: {exc.msg}"
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            return f"disallowed construct {type(node).__name__}"
        if isinstance(node, ast.Attribute):
            depth, cur = 0, node
            while isinstance(cur, ast.Attribute):
                depth += 1
                cur = cur.value
            if depth > 1 or not isinstance(cur, ast.Name):
                return f"attribute chain too deep or not on a name: {ast.unparse(node)}"
            if cur.id not in names:
                return f"unknown name {cur.id!r}"
        elif isinstance(node, ast.Name) and node.id not in names:
            return f"unknown name {node.id!r}"
    return None


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #


def resolve_args(rule: dict, cb: dict, binds_so_far: set[str]) -> tuple[dict[str, str], list[str]]:
    """
    Map every declared input of the callback to a Python expression usable
    inside `step()`: the rule's explicit `args` first, then a bind with the
    same name, then a StepContext field with the same name. Returns
    (mapping, errors).

    为回调声明的每个输入找到 `step()` 内可用的 Python 表达式：优先规则的显式 `args`，其次同名
    的 bind，再次同名的 StepContext 字段。返回 (映射, 错误列表)。
    """
    args = rule.get("args") or {}
    mapping: dict[str, str] = {}
    errors: list[str] = []
    for inp in cb.get("inputs", []):
        name = inp["name"]
        if name in args:
            mapping[name] = args[name]
        elif name in binds_so_far:
            mapping[name] = name
        elif name in CTX_FIELDS:
            mapping[name] = f"ctx.{name}"
        else:
            errors.append(f"{rule['id']}: input {name!r} of {cb['id']} cannot be resolved (add it to args)")
    for extra in args:
        if extra not in {i["name"] for i in cb.get("inputs", [])}:
            errors.append(f"{rule['id']}: args has {extra!r} which is not an input of {cb['id']}")
    return mapping, errors


def validate_flow(formal: dict) -> tuple[list[str], list[str]]:
    """
    Validate the `flow` section against the callbacks: structure, states,
    rule fields, expression safety, argument resolution, every callback used
    at least once, every state reachable from the initial state, `enter`
    rules able to find a direction, entry price and stop, `step_ref` keys
    naming summary sections. Returns (errors, warnings).

    对照回调校验 `flow` 段：结构、状态、规则字段、表达式安全、参数解析、每个回调至少被用一次、
    每个状态从初始状态可达、`enter` 规则能找到方向/入场价/止损、`step_ref` 指向总结章节。
    返回 (错误, 警告)。
    """
    errors: list[str] = []
    warnings: list[str] = []
    flow = formal.get("flow")
    if not flow:
        return ["formal.json has no 'flow' section"], warnings
    cbs = {c["id"]: c for c in formal.get("callbacks", [])}
    for cid, cb in cbs.items():
        sch = cb.get("schedule") or {}
        if sch.get("trigger") not in EVENTS:
            errors.append(f"callback {cid} {cb.get('name_en')}: schedule.trigger must be one of {EVENTS} (got {sch.get('trigger')!r})")
        if sch.get("mode", "sync") not in MODES:
            errors.append(f"callback {cid}: schedule.mode must be sync or async")
    states = [s["id"] if isinstance(s, dict) else s for s in flow.get("states", [])]
    initial = flow.get("initial_state")
    if not states:
        errors.append("flow.states is empty")
    if initial not in states:
        errors.append(f"flow.initial_state {initial!r} is not in states {states}")
    rules = flow.get("rules", [])
    if not rules:
        errors.append("flow.rules is empty")
    ids = [r.get("id") for r in rules]
    if len(set(ids)) != len(ids):
        errors.append(f"duplicate rule ids: {[i for i in ids if ids.count(i) > 1]}")
    binds: set[str] = set()
    used_cbs: set[str] = set()
    reach: dict[str, set[str]] = {s: set() for s in states}
    for r in rules:
        rid = r.get("id", "?")
        if not re.fullmatch(r"F\d{2,}", str(rid)):
            errors.append(f"rule id {rid!r} must look like F01")
        st = r.get("state", "*")
        if st != "*" and st not in states:
            errors.append(f"{rid}: state {st!r} not in states")
        trig = r.get("trigger") or "*"
        if trig != "*" and trig not in EVENTS:
            errors.append(f"{rid}: trigger {trig!r} must be '*' or one of {EVENTS}")
        names = BASE_NAMES | binds
        for key in ("when", "when_result"):
            err = check_expression(r.get(key, "") or "", names | ({r["bind"]} if r.get("bind") and key == "when_result" else set()))
            if err:
                errors.append(f"{rid}: {key}: {err}")
        call = r.get("call") or ""
        if call:
            if call not in cbs:
                errors.append(f"{rid}: call {call!r} is not a callback id")
            else:
                used_cbs.add(call)
                _, errs = resolve_args(r, cbs[call], binds)
                errors += errs
                cb_trig = (cbs[call].get("schedule") or {}).get("trigger")
                if trig == "*":
                    warnings.append(f"{rid}: trigger '*' calls {call} on every event although its schedule is {cb_trig!r}")
                elif cb_trig in EVENTS and cb_trig != trig:
                    errors.append(f"{rid}: trigger {trig!r} differs from {call}'s schedule.trigger {cb_trig!r}")
            if not r.get("bind"):
                warnings.append(f"{rid}: calls {call} but binds no name; the result is discarded")
        if r.get("bind"):
            if not re.fullmatch(r"[a-z_][a-z0-9_]*", r["bind"]):
                errors.append(f"{rid}: bind {r['bind']!r} is not a valid identifier")
            if r["bind"] in BASE_NAMES:
                errors.append(f"{rid}: bind {r['bind']!r} shadows a reserved name")
            binds.add(r["bind"])
        then = r.get("then") or ""
        if then and "stop_hit" in (r.get("when") or "") and trig not in ("tick", "*"):
            errors.append(f"{rid}: a stop_hit rule must run on tick (trigger={trig!r})")
        if then:
            base = then.split(":", 1)[0]
            if base not in ACTIONS:
                errors.append(f"{rid}: then {then!r} is not one of {ACTIONS}")
            if base == "close" and ":" not in then:
                errors.append(f"{rid}: close needs a reason, e.g. close:stop")
            if base == "enter":
                uses = r.get("uses") or {}
                need = {"direction": uses.get("direction", "direction"), "entry_price": uses.get("entry_price", "entry.entry_price"),
                        "stop": uses.get("stop", r.get("bind") or "stop")}
                for k, expr in need.items():
                    err = check_expression(expr, names | binds)
                    if err:
                        errors.append(f"{rid}: enter needs {k} = {expr!r}: {err}")
            if base == "move_stop" and not r.get("bind"):
                errors.append(f"{rid}: move_stop needs the new stop bound by this rule")
        nxt = r.get("next") or ""
        if nxt:
            if nxt not in states:
                errors.append(f"{rid}: next {nxt!r} not in states")
            else:
                for s in (states if st == "*" else [st]):
                    reach[s].add(nxt)
        ref = r.get("step_ref") or ""
        if ref and ref.split(".")[0] not in SUMMARY_SECTIONS:
            errors.append(f"{rid}: step_ref {ref!r} does not start with a summary section key")
        if not ref:
            warnings.append(f"{rid}: no step_ref (S8 cannot map it to an execution step)")
    for cid in cbs:
        if cid not in used_cbs:
            errors.append(f"callback {cid} {cbs[cid].get('name_en')} is never called by any flow rule")
    if initial in reach:
        seen, stack = {initial}, [initial]
        while stack:
            for nxt in reach[stack.pop()]:
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        for s in states:
            if s not in seen:
                errors.append(f"state {s!r} is unreachable from {initial!r}")
    return errors, warnings


# --------------------------------------------------------------------------- #
# Generation
# --------------------------------------------------------------------------- #


def _cond(state_expr: str, when: str) -> str:
    """
    Join the state test and the `when` expression into one `if` condition.

    把状态判断和 `when` 表达式合成一个 `if` 条件。
    """
    parts = [p for p in (state_expr, f"({when.strip()})" if when and when.strip() else "") if p]
    return " and ".join(parts) or "True"


def render_step(formal: dict, terms: dict | None = None) -> str:
    """
    Render the generated `StrategyDriver` class with its `step()` method: all
    bind names initialised to None, then one commented block per rule in
    order. Rules that set `next` end the evaluation (`return actions`).

    渲染生成的 `StrategyDriver` 类及其 `step()` 方法：所有 bind 名初始化为 None，然后按顺序
    为每条规则生成一个带注释的代码块。设置了 `next` 的规则会结束本次评估（`return actions`）。
    """
    flow = formal["flow"]
    cbs = {c["id"]: c for c in formal.get("callbacks", [])}
    tmap = {t["id"]: t for t in (terms or {}).get("terms", [])}
    binds = [r["bind"] for r in flow["rules"] if r.get("bind")]
    L: list[str] = []
    L.append("class StrategyDriver(StrategyDriverBase):")
    L.append('    """')
    L.append("    Generated control flow. Each block below is one flow rule; the comment names")
    L.append("    the rule and the summary line it implements.")
    L.append("")
    L.append("    生成的控制流。下面每个代码块对应一条 flow 规则；注释给出规则编号和它实现的总结行。")
    L.append('    """')
    L.append("")
    meta_items = ", ".join(
        f"{c['name_en']!r}: ({(c.get('schedule') or {}).get('trigger', '')!r}, {(c.get('schedule') or {}).get('mode', 'sync')!r}, {(c.get('output') or {}).get('type', '')!r})"
        for c in formal.get("callbacks", []))
    L.append(f"    callback_meta = {{{meta_items}}}")
    L.append("")
    L.append("    def on_event(self, event: Event, ctx: StepContext) -> list[Action]:")
    L.append('        """')
    L.append("        One evaluation for `event`: rules whose trigger matches run (calling their callback),")
    L.append("        the others are skipped and their bound values come from the signal cache.")
    L.append("")
    L.append("        对 `event` 评估一次：触发事件匹配的规则执行（调用其回调），其余规则跳过，其绑定值取自")
    L.append("        信号缓存。")
    L.append('        """')
    L.append("        self.cache.seq += 1")
    L.append("        actions: list[Action] = []")
    L.append("        state = self.state")
    L.append("        position = ctx.position")
    L.append("        stop_hit = self.stop_hit(ctx) if event == 'tick' else False")
    bind_src = {r["bind"]: cbs[r["call"]]["name_en"] for r in flow["rules"] if r.get("bind") and r.get("call") in cbs}
    for b in dict.fromkeys(binds):
        L.append(f"        {b} = self.cache.get({bind_src[b]!r})" if b in bind_src else f"        {b} = None")
    L.append("")
    binds_so_far: set[str] = set()
    for r in flow["rules"]:
        rid = r["id"]
        cb = cbs.get(r.get("call") or "")
        label = ""
        if cb:
            t = tmap.get(cb["term_id"], {})
            label = f" {cb['name_en']} ({t.get('name_zh', cb.get('name_zh', ''))})"
        note = r.get("note_zh") or r.get("note_en") or ""
        trig = r.get("trigger") or "*"
        L.append(f"        # {rid} [{r.get('step_ref', '')}] on {trig}{label}{': ' + note if note else ''}")
        state_expr = "" if r.get("state", "*") == "*" else f"state == {r['state']!r}"
        if trig != "*":
            state_expr = f"event == {trig!r}" + (f" and {state_expr}" if state_expr else "")
        cond = _cond(state_expr, r.get("when", ""))
        indent = "        " if cond == "True" else "            "
        if cond != "True":
            L.append(f"        if {cond}:")
        body: list[str] = []
        if cb:
            mapping, _ = resolve_args(r, cb, binds_so_far)
            call = f"self._call({cb['name_en']!r}, event" + "".join(f", {k}={v}" for k, v in mapping.items()) + ")"
            if r.get("bind"):
                body.append(f"{r['bind']} = {call}")
            else:
                body.append(call)
        then = r.get("then") or ""
        nxt = r.get("next") or ""
        if then or nxt:
            wr = (r.get("when_result") or "").strip()
            inner: list[str] = []
            if then:
                base, _, reason = then.partition(":")
                if base == "enter":
                    uses = r.get("uses") or {}
                    d, ep, sp = uses.get("direction", "direction"), uses.get("entry_price", "entry.entry_price"), uses.get("stop", r.get("bind") or "stop")
                    inner.append(f"actions.append(self._enter({rid!r}, direction={d}, entry_price={ep}, stop={sp}, ctx=ctx))")
                elif base == "close":
                    inner.append(f"actions.append(self._close({rid!r}, {reason!r}, ctx))")
                elif base == "move_stop_to_cost":
                    inner.append(f"actions.append(self._move_stop_to_cost({rid!r}, ctx))")
                elif base == "move_stop":
                    inner.append(f"_a = self._move_stop({rid!r}, {r['bind']}, ctx)")
                    inner.append("if _a is not None:")
                    inner.append("    actions.append(_a)")
                elif base == "set_stop":
                    inner.append(f"actions.append(self._set_stop({rid!r}, {r.get('bind') or 'stop'}))")
            if nxt:
                inner.append(f"self.state = {nxt!r}")
                inner.append("return actions")
            if wr:
                body.append(f"if {wr}:")
                body += ["    " + x for x in inner]
            else:
                body += inner
        if not body:
            body.append("pass")
        L += [indent + x for x in body]
        L.append("")
        if r.get("bind"):
            binds_so_far.add(r["bind"])
    L.append("        return actions")
    return "\n".join(L) + "\n"


def render_driver(formal: dict, terms: dict | None, strategy_name: str, stub_module: str) -> str:
    """
    Render the complete driver module: the runtime template with its
    placeholders filled (strategy name, timestamp, stub import, initial
    state) followed by the generated class.

    渲染完整的 driver 模块：填好占位符（策略名、时间戳、桩模块导入、初始状态）的运行时模板，
    后接生成的类。
    """
    tpl = read_text(TEMPLATES_DIR / "strategy_driver.template.py")
    stub_import = f"from {stub_module} import ({', '.join(STUB_TYPES)})  # noqa: F401"
    head = (tpl.replace("{strategy_name}", strategy_name).replace("{generated_at}", now_iso())
            .replace("{stub_import}", stub_import).replace("{initial_state}", formal["flow"]["initial_state"]))
    return head.rstrip("\n") + "\n\n\n" + render_step(formal, terms)


# --------------------------------------------------------------------------- #
# Dry run
# --------------------------------------------------------------------------- #


def load_module(path: Path):
    """
    Import a Python file by path with its directory on sys.path (so the
    driver can import its stub module).

    按路径导入 Python 文件，并把所在目录加入 sys.path（driver 要导入它的桩模块）。
    """
    d = str(path.resolve().parent)
    if d not in sys.path:
        sys.path.insert(0, d)
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = mod
    spec.loader.exec_module(mod)
    return mod


def build_scripted_callbacks(formal: dict, mod, scenario: dict):
    """
    Create a StrategyCallbacks subclass whose methods return the value the
    scenario scripts for the current tick (converted into EntryDecision /
    StopDistance when the callback's output type says so) and record every
    call. A callback invoked without a scripted value raises, which is the
    dry-run's way of catching unexpected calls.

    创建 StrategyCallbacks 子类：各方法返回场景为当前 tick 脚本化的值（回调输出类型为
    EntryDecision / StopDistance 时自动构造），并记录每次调用。被调用却没有脚本值的回调会
    抛错，这是 dry-run 捕捉意外调用的方式。
    """
    cbs = formal["callbacks"]
    holder = {"tick": 0, "values": {}, "calls": []}

    def make(cb):
        """
        Build the scripted method for one callback (closure over its id and
        output type).

        为一个回调构造脚本化方法（闭包持有其 id 与输出类型）。
        """
        otype = (cb.get("output") or {}).get("type", "")

        def method(self, **kwargs):
            """
            Return the scripted value for the current tick, building compound
            outputs from dicts; raise when the scenario has no value.

            返回当前 tick 的脚本值（字典自动构造为复合输出）；场景没有给值时抛错。
            """
            vals = holder["values"]
            if cb["id"] not in vals:
                raise RuntimeError(f"tick {holder['tick']}: {cb['name_en']} ({cb['id']}) was called but the scenario gives no value")
            v = vals[cb["id"]]
            if v is None:
                holder["calls"].append((holder["tick"], cb["id"], None))
                return None
            if isinstance(v, dict) and otype in ("EntryDecision", "StopDistance"):
                v = getattr(mod, otype)(**v)
            holder["calls"].append((holder["tick"], cb["id"], v))
            return v
        method.__name__ = cb["name_en"]
        return method

    ns = {cb["name_en"]: make(cb) for cb in cbs}
    Scripted = type("ScriptedCallbacks", (mod.StrategyCallbacks,), ns)
    return Scripted(), holder


def run_scenario(formal: dict, mod, scenario: dict, verbose: bool = True) -> tuple[list[str], list[str]]:
    """
    Execute one dry-run scenario: for each tick build a StepContext (last
    price, current position from the RecordingPort, placeholder market data),
    call `driver.step`, apply the actions, print the trace. Returns
    (trace_labels, expected_labels).

    执行一个 dry-run 场景：每个 tick 构造 StepContext（最新价、RecordingPort 的当前持仓、占位
    行情数据），调用 `driver.step`，应用动作，打印轨迹。返回 (实际标签, 期望标签)。
    """
    from datetime import datetime
    acct = scenario.get("account") or {"capital": 1_000_000, "per_trade_loss_ratio": 0.01}
    account = mod.Account(capital=float(acct["capital"]), per_trade_loss_ratio=float(acct["per_trade_loss_ratio"]))
    callbacks, holder = build_scripted_callbacks(formal, mod, scenario)
    driver = mod.StrategyDriver(callbacks, account)
    port = mod.RecordingPort()
    inst = mod.Instrument(symbol=scenario.get("instrument", "TEST"), multiplier=float(scenario.get("multiplier", 1.0)))
    empty = lambda tf: mod.MarketData(instrument=inst.symbol, timeframe=tf, bars=[])  # noqa: E731
    trace: list[str] = []
    for i, tick in enumerate(scenario.get("ticks", []), 1):
        holder["tick"] = i
        holder["values"] = {k: v for k, v in tick.items() if k.startswith("CB")}
        event = tick.get("event", "tick")
        ctx = mod.StepContext(instrument=inst, major_tf_data=empty("major"), minor_tf_data=empty("minor"),
                              position=port.position, last_price=tick.get("last_price"), now=datetime.now())
        actions = driver.on_event(event, ctx)
        calls = ", ".join(f"{cid}={val!r}" for t, cid, val in holder["calls"] if t == i)
        for a in actions:
            port.apply(a, ctx)
            trace.append(a.label())
        acts = "; ".join(f"{a.rule_id} {a.label()}" + (f" @{a.price}" if a.price is not None and a.kind == 'enter' else "")
                         + (f" stop={a.stop_price}" if a.stop_price is not None else "") + (f" size={a.size}" if a.size else "")
                         for a in actions) or "-"
        if verbose:
            print(f"{i:>2} {event:<9} price={tick.get('last_price')!s:<7} state={driver.state:<12} calls[{calls}] -> {acts}")
    return trace, list(scenario.get("expect", []))


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #


def cmd_gen(args: argparse.Namespace) -> None:
    """
    Validate the flow, render the driver to --out and check it compiles.

    校验 flow，把 driver 渲染到 --out 并检查可编译。
    """
    fpath = ws_path(args.workspace, args.path)
    formal = load_json(fpath)
    terms = load_json(ws_path(args.workspace, args.terms)) if args.terms else None
    errors, warnings = validate_flow(formal)
    for w in warnings:
        say(f"warning: {w}")
    for e in errors:
        say(f"ERROR: {e}")
    if errors:
        raise SystemExit(1)
    out = ws_path(args.workspace, args.out)
    name = args.strategy_name or resolve_workspace(args.workspace).name
    code = render_driver(formal, terms, name, args.stub_module)
    compile(code, str(out), "exec")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(code, encoding="utf-8")
    say(f"wrote {relpath(out)} ({len(formal['flow']['rules'])} rules, imports {args.stub_module})", "已生成 driver")


def cmd_validate(args: argparse.Namespace) -> None:
    """
    Validate the flow section; exit 1 on errors.

    校验 flow 段；有错误则以 1 退出。
    """
    formal = load_json(ws_path(args.workspace, args.path))
    errors, warnings = validate_flow(formal)
    for w in warnings:
        say(f"warning: {w}")
    for e in errors:
        say(f"ERROR: {e}")
    if errors:
        raise SystemExit(1)
    say(f"flow valid: {len(formal['flow']['rules'])} rules, states {[s['id'] if isinstance(s, dict) else s for s in formal['flow']['states']]}", "flow 校验通过")


def cmd_dryrun(args: argparse.Namespace) -> None:
    """
    Run every scenario in flow.dryrun (or the one named by --scenario)
    against the generated driver and compare traces with `expect`; exit 1 on
    any mismatch.

    用生成的 driver 跑 flow.dryrun 中的全部场景（或 --scenario 指定的那个），把轨迹与 `expect`
    比较；任一不符则以 1 退出。
    """
    formal = load_json(ws_path(args.workspace, args.path))
    scenarios = formal.get("flow", {}).get("dryrun") or []
    if isinstance(scenarios, dict):
        scenarios = [scenarios]
    if args.scenario:
        scenarios = [s for s in scenarios if s.get("name") == args.scenario]
    if not scenarios:
        fail("no dry-run scenarios in flow.dryrun", "flow.dryrun 没有场景")
    mod = load_module(ws_path(args.workspace, args.driver))
    failed = 0
    for sc in scenarios:
        print(f"== scenario {sc.get('name', '?')}: {sc.get('note_zh') or sc.get('note_en') or ''}")
        trace, expect = run_scenario(formal, mod, sc)
        ok = trace == expect
        failed += 0 if ok else 1
        say(f"{'PASS' if ok else 'FAIL'} trace={trace} expect={expect}")
    if failed:
        raise SystemExit(1)
    say(f"{len(scenarios)} scenario(s) passed", "dry-run 全部通过")


def build_parser() -> argparse.ArgumentParser:
    """
    Build the CLI.

    构建命令行。
    """
    p = argparse.ArgumentParser(description="S7 strategy driver / 策略 driver")
    p.add_argument("--workspace", "-w")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("gen")
    s.add_argument("path")
    s.add_argument("--terms")
    s.add_argument("--out", default="S7_strategy_driver.py")
    s.add_argument("--stub-module", default="S7_callbacks_stub")
    s.add_argument("--strategy-name")
    s.set_defaults(func=cmd_gen)
    s = sub.add_parser("validate")
    s.add_argument("path")
    s.set_defaults(func=cmd_validate)
    s = sub.add_parser("dryrun")
    s.add_argument("path")
    s.add_argument("--driver", default="S7_strategy_driver.py")
    s.add_argument("--scenario")
    s.set_defaults(func=cmd_dryrun)
    return p


def main(argv: list[str] | None = None) -> None:
    """
    CLI entry point.

    命令行入口。
    """
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
