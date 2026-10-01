"""
Agents: read the English part only. 中文仅供人类阅读。

S7 driver tests: a flow authored on the fixture terms validates, renders to
a compilable driver, and its dry-run scenarios produce the expected action
traces (including the only-tightens guard and the stop-hit exit); malformed
flows are rejected with specific errors.

S7 driver 测试：基于夹具术语编写的 flow 能通过校验、渲染为可编译的 driver，dry-run 场景产生
期望的动作轨迹（含"只进不退"和打止损出场）；不合规的 flow 会被具体的错误拒绝。
"""
from __future__ import annotations

import copy
import json

import pytest

import sf_driver
import sf_formal
from conftest import load

FLOW = {
    "initial_state": "FLAT",
    "states": [{"id": "FLAT", "name_zh": "空仓"}, {"id": "IN_POSITION", "name_zh": "持仓"}],
    "rules": [
        {"id": "F01", "state": "*", "trigger": "major_bar", "when": "", "call": "CB01", "bind": "direction", "args": {}, "when_result": "", "then": "", "next": "", "step_ref": "execution_steps.1"},
        {"id": "F02", "state": "FLAT", "trigger": "minor_bar", "when": "direction in ('long', 'short')", "call": "CB02", "bind": "entry", "args": {"major_direction": "direction"}, "when_result": "", "then": "", "next": "", "step_ref": "execution_steps.2"},
        {"id": "F03", "state": "FLAT", "trigger": "minor_bar", "when": "entry is not None and entry.decision == 'enter'", "call": "", "bind": "", "args": {}, "uses": {"stop": "2.0"}, "when_result": "", "then": "enter", "next": "IN_POSITION", "step_ref": "execution_steps.3"},
        {"id": "F04", "state": "IN_POSITION", "trigger": "tick", "when": "stop_hit", "call": "", "bind": "", "args": {}, "when_result": "", "then": "close:stop", "next": "FLAT", "step_ref": "exit_and_risk.2"},
        {"id": "F05", "state": "IN_POSITION", "trigger": "major_bar", "when": "", "call": "CB05", "bind": "reversed", "args": {"major_direction": "direction"}, "when_result": "reversed", "then": "close:reversal", "next": "FLAT", "step_ref": "exit_and_risk.2"},
        {"id": "F06", "state": "IN_POSITION", "trigger": "major_bar", "when": "not position.stop_at_cost", "call": "CB06", "bind": "favorable", "args": {}, "when_result": "favorable", "then": "move_stop_to_cost", "next": "", "step_ref": "execution_steps.3"},
        {"id": "F07", "state": "IN_POSITION", "trigger": "major_bar", "when": "position.stop_at_cost", "call": "CB04", "bind": "new_stop", "args": {}, "when_result": "new_stop is not None", "then": "move_stop", "next": "", "step_ref": "exit_and_risk.1"},
    ],
    "dryrun": [
        {"name": "trend_then_reversal", "multiplier": 10, "account": {"capital": 1000000, "per_trade_loss_ratio": 0.01},
         "ticks": [
             {"event": "major_bar", "last_price": 100, "CB01": "long"},
             {"event": "minor_bar", "last_price": 100, "CB02": {"decision": "enter", "entry_price": 100}},
             {"event": "tick", "last_price": 101},
             {"event": "major_bar", "last_price": 103, "CB01": None, "CB05": False, "CB06": True},
             {"event": "major_bar", "last_price": 106, "CB01": "long", "CB05": False, "CB04": 103.0},
             {"event": "major_bar", "last_price": 107, "CB01": "long", "CB05": False, "CB04": 102.0},
             {"event": "major_bar", "last_price": 104, "CB01": "uncertain", "CB05": True}],
         "expect": ["enter", "move_stop_to_cost", "move_stop", "close:reversal"]},
        {"name": "stop_hit", "multiplier": 10,
         "ticks": [
             {"event": "major_bar", "last_price": 100, "CB01": "short"},
             {"event": "minor_bar", "last_price": 100, "CB02": {"decision": "enter", "entry_price": 100}},
             {"event": "tick", "last_price": 101},
             {"event": "tick", "last_price": 102},
             {"event": "minor_bar", "last_price": 103, "CB02": {"decision": "no_enter"}}],
         "expect": ["enter", "close:stop"]},
    ],
}


def formal_with_flow(ws):
    """
    Scaffold formal.json from the fixture terms, give the callbacks typed
    inputs/outputs that match FLOW, attach FLOW and save.

    由夹具术语生成 formal.json，为回调设置与 FLOW 匹配的类型化输入/输出，附上 FLOW 并保存。
    """
    w = str(ws)
    sf_formal.main(["--workspace", w, "scaffold", "S6_terms_defined.json", "S7_formal.json"])
    formal = load(ws / "S7_formal.json")
    spec = {  # term_id: (inputs, output)
        "T001": ([("major_tf_data", "MarketData"), ("instrument", "Instrument")], {"type": "enum", "values": ["long", "short", "uncertain"]}),
        "T002": ([("minor_tf_data", "MarketData"), ("major_direction", "Direction")], {"type": "EntryDecision", "values": []}),
        "T003": ([("major_tf_data", "MarketData"), ("position", "Position")], {"type": "bool", "values": []}),
        "T004": ([("major_tf_data", "MarketData"), ("position", "Position")], {"type": "price", "values": []}),
        "T005": ([("major_direction", "str"), ("position", "Position")], {"type": "bool", "values": []}),
    }
    sched = {"T001": ("major_bar", "async"), "T002": ("minor_bar", "sync"), "T003": ("major_bar", "async"),
             "T004": ("major_bar", "async"), "T005": ("major_bar", "async")}
    ids = {}
    for cb in formal["callbacks"]:
        ins, out = spec[cb["term_id"]]
        cb["inputs"] = [{"name": n, "type": t, "source_term_id": None, "description_en": ""} for n, t in ins]
        cb["output"] = {**out, "description_en": ""}
        cb["schedule"] = {"trigger": sched[cb["term_id"]][0], "mode": sched[cb["term_id"]][1]}
        ids[cb["term_id"]] = cb["id"]
    # fixture callbacks: T001 direction, T002 entry, T003 favourable move, T004 trailing, T005 reversal.
    # FLOW uses a constant stop distance (uses.stop = "2.0") so no stop callback is needed.
    remap = {"CB01": ids["T001"], "CB02": ids["T002"], "CB04": ids["T004"], "CB05": ids["T005"], "CB06": ids["T003"]}
    flow = copy.deepcopy(FLOW)
    for r in flow["rules"]:
        if r["call"]:
            r["call"] = remap[r["call"]]
    for sc in flow["dryrun"]:
        sc["ticks"] = [{(remap[k] if k.startswith("CB") else k): v for k, v in t.items()} for t in sc["ticks"]]
    formal["flow"] = flow
    (ws / "S7_formal.json").write_text(json.dumps(formal, ensure_ascii=False, indent=2), encoding="utf-8")
    return formal


def test_validate_gen_dryrun(ws):
    """
    The authored flow validates, the driver renders and compiles, and both
    dry-run scenarios pass with the expected traces.

    编写的 flow 通过校验，driver 可渲染、可编译，两个 dry-run 场景按期望轨迹通过。
    """
    formal = formal_with_flow(ws)
    errors, _ = sf_driver.validate_flow(formal)
    assert errors == []
    w = str(ws)
    sf_formal.main(["--workspace", w, "gen-stub", "S7_formal.json", "--terms", "S6_terms_defined.json", "--out", "S7_callbacks_stub.py"])
    sf_driver.main(["--workspace", w, "gen", "S7_formal.json", "--terms", "S6_terms_defined.json", "--out", "S7_strategy_driver.py", "--strategy-name", "demo"])
    code = (ws / "S7_strategy_driver.py").read_text(encoding="utf-8")
    assert "class StrategyDriver(StrategyDriverBase)" in code and "# F03 [execution_steps.3] on minor_bar" in code
    assert "def on_event(self, event: Event, ctx: StepContext)" in code
    sf_driver.main(["--workspace", w, "dryrun", "S7_formal.json", "--driver", "S7_strategy_driver.py"])
    mod = sf_driver.load_module(ws / "S7_strategy_driver.py")
    trace, expect = sf_driver.run_scenario(formal, mod, formal["flow"]["dryrun"][0], verbose=False)
    assert trace == expect


def test_validate_rejects_bad_flows(ws):
    """
    Unused callback, unknown name in a condition, unreachable state, and
    a call whose input cannot be resolved are all reported.

    未使用的回调、条件中的未知名字、不可达状态、无法解析输入的调用都会被报告。
    """
    formal = formal_with_flow(ws)
    bad = copy.deepcopy(formal); bad["flow"]["rules"] = [r for r in bad["flow"]["rules"] if r["id"] != "F07"]
    errs, _ = sf_driver.validate_flow(bad)
    assert any("never called" in e for e in errs)
    bad = copy.deepcopy(formal); bad["flow"]["rules"][1]["when"] = "foo == 1"
    errs, _ = sf_driver.validate_flow(bad)
    assert any("unknown name 'foo'" in e for e in errs)
    bad = copy.deepcopy(formal); bad["flow"]["states"].append({"id": "ORPHAN"})
    errs, _ = sf_driver.validate_flow(bad)
    assert any("unreachable" in e for e in errs)
    bad = copy.deepcopy(formal); bad["flow"]["rules"][1]["args"] = {}
    errs, _ = sf_driver.validate_flow(bad)
    assert any("cannot be resolved" in e for e in errs)
    assert sf_driver.check_expression("__import__('os')", {"x"}) is not None
    assert sf_driver.check_expression("a.b.c", {"a"}) is not None
    bad = copy.deepcopy(formal); bad["flow"]["rules"][4]["trigger"] = "tick"   # reversal callback is scheduled on major_bar
    errs, _ = sf_driver.validate_flow(bad)
    assert any("differs from" in e for e in errs)
    bad = copy.deepcopy(formal); bad["flow"]["rules"][3]["trigger"] = "major_bar"   # stop_hit must be on tick
    errs, _ = sf_driver.validate_flow(bad)
    assert any("stop_hit rule must run on tick" in e for e in errs)
    bad = copy.deepcopy(formal); bad["callbacks"][0].pop("schedule")
    errs, _ = sf_driver.validate_flow(bad)
    assert any("schedule.trigger" in e for e in errs)


def test_flow_xlsx_roundtrip(ws):
    """
    The flow sheet survives to-xlsx -> from-xlsx (args as JSON cells).

    flow 表经 to-xlsx -> from-xlsx 往返后保持不变（args 以 JSON 单元格存储）。
    """
    formal_with_flow(ws)
    w = str(ws)
    sf_formal.main(["--workspace", w, "to-xlsx", "S7_formal.json"])
    sf_formal.main(["--workspace", w, "from-xlsx", "S7_formal.xlsx"])
    f = load(ws / "S7_formal.json")
    assert len(f["flow"]["rules"]) == 7 and f["flow"]["rules"][1]["args"] == {"major_direction": "direction"}
    assert f["flow"]["rules"][6]["when_result"] == "new_stop is not None"


def test_cache_and_async(ws):
    """
    Async callback returning None keeps the cached direction (tick 4 of the
    first scenario), callbacks are only consulted on their trigger event, and
    a stop hit is detected on a tick between major bars.

    异步回调返回 None 时沿用缓存方向（场景一第 4 个事件），回调只在触发事件上被咨询，
    大周期 K 线之间的 tick 能检测到止损触发。
    """
    formal = formal_with_flow(ws)
    w = str(ws)
    sf_formal.main(["--workspace", w, "gen-stub", "S7_formal.json", "--terms", "S6_terms_defined.json", "--out", "S7_callbacks_stub.py"])
    sf_driver.main(["--workspace", w, "gen", "S7_formal.json", "--terms", "S6_terms_defined.json", "--out", "S7_strategy_driver.py", "--strategy-name", "demo"])
    mod = sf_driver.load_module(ws / "S7_strategy_driver.py")
    callbacks, holder = sf_driver.build_scripted_callbacks(formal, mod, {})
    trace, expect = sf_driver.run_scenario(formal, mod, formal["flow"]["dryrun"][0], verbose=False)
    assert trace == expect
    trace, expect = sf_driver.run_scenario(formal, mod, formal["flow"]["dryrun"][1], verbose=False)
    assert trace == expect
