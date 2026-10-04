"""
Agents: read the English part only. 中文仅供人类阅读。

Flow-data tests: the flow built from a judged symbol (calls in order, prompt
blocks, results, what the code did in between, threads), a three-round
debate with focus, a symbol whose per-call records are gone, the index, the
localhost server's allow-list, and that the fixture the web template is
tested against still has the shape `build_flow` produces.

flow 数据测试：由已判断品种生成的 flow（按顺序的调用、提示词构成、返回结果、调用之间代码做的事、
线程）、带聚焦的三轮辩论、逐次留痕已不存在的品种、索引、本机服务的放行名单，以及网页模板测试用的
样例数据仍与 `build_flow` 的输出形状一致。
"""
from __future__ import annotations

import json
import re
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from strategies.resonance.cli import write_outputs
from strategies.resonance.config import PACKAGE_DIR, JudgeConfig, ResonanceParams
from strategies.resonance.debate import judge_symbol
from strategies.resonance.evidence import load_pack
from strategies.resonance.flow import FLOW_SCHEMA, build_flow, prompt_blocks, write_index
from strategies.resonance.schemas import Position
from strategies.resonance.serve import make_server
from strategies.resonance.tests.conftest import FakeRunner

FIXTURE = PACKAGE_DIR / "web" / "tests" / "fixtures" / "flow.sample.json"


def stamp_records(symbol_dir: Path) -> None:
    """
    Give the per-call records of a fake run fixed, realistic times: the two
    sides of a stage start together, the next stage starts three seconds
    after both are back. The fake runner returns instantly, and a sample
    with zero-length calls would not exercise the page's timeline.

    给假运行的逐次留痕写入固定且接近真实的时间：同一阶段的两侧同时开始，下一阶段在两侧都返回三秒后
    开始。假运行器瞬间返回，零时长的样例无法检验页面的时间线。
    """
    seconds = {"thesis": [78, 144], "rebuttal": [146, 60], "defence": [76, 129], "moderator": [5], "manager": [81]}
    stages: dict[tuple, list[Path]] = {}
    for path in symbol_dir.glob("*.response.json"):
        m = re.match(r"(?:debate_r(\d)_)?(?:(long|short)_)?(thesis|rebuttal|defence|moderator|manager)(?:_(long|short))?\.", path.name)
        rnd, kind = int(m.group(1) or 0), m.group(3)
        order = (0, 0) if kind == "thesis" else (9, 0) if kind == "manager" else (rnd, ["rebuttal", "defence", "moderator"].index(kind))
        stages.setdefault((order, kind), []).append(path)
    cursor = datetime(2026, 9, 29, 8, 45, 0, tzinfo=timezone(timedelta(hours=8)))
    for (_, kind), paths in sorted(stages.items()):
        start, ends = cursor + timedelta(seconds=3), []
        for i, path in enumerate(sorted(paths)):
            rec = json.loads(path.read_text(encoding="utf-8"))
            end = start + timedelta(seconds=seconds[kind][i % len(seconds[kind])])
            rec.update(started_at=start.isoformat(timespec="milliseconds"), finished_at=end.isoformat(timespec="milliseconds"))
            path.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
            ends.append(end)
        cursor = max(ends)


def sample_outcome(pack: Path, runs_dir: Path):
    """
    The scenario behind the web fixture: CU with an open short position,
    three rounds (the moderator keeps 多1 in focus), 多2 conceded, the
    objection to 空1 withdrawn.

    网页样例数据对应的场景：CU 持空仓，三轮辩论（主持人一直聚焦 多1），多2 认输，对 空1 的异议被撤回。
    """
    ev = load_pack(pack)["CU"]
    cfg = JudgeConfig(runs_dir=runs_dir, max_workers=1, parallel_sides=False)
    position = Position(vt_symbol="cu2611.SHFE", variety_code="CU", direction="short", volume=2, entry_price=100.0)
    runner = FakeRunner(moderator=lambda rnd: {"continue_debate": True, "reason": "多1 上还有未回应的新证据。", "focus_point_ids": ["多1"]},
                        concede={"多2"}, withdraw={"空1"})
    outcome = judge_symbol(ev, position, cfg, ResonanceParams(), runner=runner)
    stamp_records(runs_dir / ev.pack_date / "CU")
    flow = build_flow(outcome, runs_dir / ev.pack_date / "CU", ev.pack_date, name=ev.variety_name, last_session=ev.last_session,
                      position=position, config={"model": cfg.model, "effort": cfg.effort, "max_debate_rounds": cfg.max_debate_rounds})
    return outcome, flow


def _shape(value):
    """Keys and nesting of a JSON value, ignoring the values themselves.

    一个 JSON 值的键与嵌套结构，忽略具体取值。
    """
    if isinstance(value, dict):
        return {k: _shape(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [_shape(value[0])] if value else []
    return type(value).__name__ if value is not None else "null"


def test_flow_of_one_round(pack: Path, tmp_path: Path):
    """
    One round ended by the moderator: eight steps in call order with times,
    cost and prompt blocks; the glue lines say what the code did; threads
    carry every exchange and the ruling.

    主持人在第一轮后终止：八个步骤按调用顺序排列，带时间、费用和提示词构成；glue 说明代码做了什么；
    线程带全部交锋和裁定。
    """
    ev = load_pack(pack)["CU"]
    cfg = JudgeConfig(runs_dir=tmp_path / "runs", max_workers=1, parallel_sides=False)
    outcome = judge_symbol(ev, None, cfg, ResonanceParams(), runner=FakeRunner())
    flow = build_flow(outcome, cfg.runs_dir / "2026-09-29" / "CU", "2026-09-29", name=ev.variety_name, last_session=ev.last_session)
    assert flow["schema"] == FLOW_SCHEMA and flow["symbol"] == "CU" and flow["name"] == "沪铜" and flow["lastSession"] == "2026-09-28"
    assert [s["id"] for s in flow["steps"]] == ["long_thesis", "short_thesis", "debate_r1_rebuttal_long", "debate_r1_rebuttal_short",
                                                "debate_r1_defence_long", "debate_r1_defence_short", "debate_r1_moderator", "manager"]
    assert [s["label"] for s in flow["steps"]] == ["多方立论", "空方立论", "多方反驳", "空方反驳", "多方再反驳", "空方再反驳", "主持人", "Manager"]
    assert all(s["t0"] is not None and s["t1"] >= s["t0"] and s["cost"] == 0.5 and s["attempts"] == 1 and s["promptChars"] > 0 for s in flow["steps"])
    assert flow["steps"][0]["t0"] == 0 and flow["wall"] is not None and flow["cost"] == 4.0 and flow["cacheFile"].startswith("decision.")
    assert [b["label"] for b in flow["steps"][0]["blocks"]] == ["角色与规则", "决策时点", "策略定义", "证据包"]
    assert [b["label"] for b in flow["steps"][2]["blocks"]] == ["角色与规则", "决策时点", "策略定义", "己方立论", "对方论据", "证据包"]
    assert [b["label"] for b in flow["steps"][7]["blocks"]] == ["角色与规则", "决策时点", "策略定义", "双方立论", "辩论记录", "终止理由", "证据包"]
    assert all(sum(b["chars"] for b in s["blocks"]) == s["promptChars"] for s in flow["steps"])
    glue = {s["id"]: s["glue"] for s in flow["steps"]}
    assert glue["long_thesis"] == "" and glue["short_thesis"] == "给论据编号并建线程：多1–多2、空1–空1，一条论据一个线程。"
    assert glue["debate_r1_rebuttal_short"] == "把 3 条反驳挂到各自线程上。"
    assert glue["debate_r1_defence_short"] == "把 3 条再反驳挂到线程上。还剩 3 个争议线程。未到轮数上限，于是询问主持人。"
    assert glue["debate_r1_moderator"].endswith("判断为终止，进入 Manager。") and "无持仓，结果为 None" in glue["manager"]
    assert flow["steps"][3]["result"] == "2 条反驳" and flow["steps"][3]["items"][0] == {"id": "多1", "tag": "举反例", "text": "反例"}
    assert flow["steps"][7]["result"] == "方向 long，置信度 0.7；裁定 成立 1，被削弱 0，被驳倒 1"
    threads = {t["id"]: t for t in flow["threads"]}
    assert threads["多1"]["verdict"] == "成立" and threads["多2"]["verdict"] is None and threads["空1"]["owner"] == "short"
    assert [(x["speaker"], x["kind"], x["tag"]) for x in threads["多1"]["exchanges"]] == [("short", "反驳", "举反例"), ("long", "再反驳", "坚持")]
    assert flow["rulings"] == [{"round": 1, "by": "moderator", "continue": False, "reason": "双方已无新论点。", "focus": []}]
    assert flow["position"] is None and flow["decision"]["direction"] == "long"


def test_flow_of_three_rounds_and_missing_records(pack: Path, tmp_path: Path):
    """
    Three rounds with focus, a concession and a withdrawn objection: later
    rounds list only the calls that happened, the glue names the closed
    threads and the code's own stop; without per-call records the steps stay
    in order with null timing.

    带聚焦、认输和撤回异议的三轮辩论：后续轮次只列出实际发生的调用，glue 点名被关闭的线程和代码自行
    终止；没有逐次留痕时，步骤仍按顺序排列，时间字段为 null。
    """
    outcome, flow = sample_outcome(pack, tmp_path / "runs")
    later = ["debate_r1_defence_long", "debate_r1_moderator", "debate_r2_rebuttal_short", "debate_r2_defence_long", "debate_r2_moderator",
             "debate_r3_rebuttal_short", "debate_r3_defence_long", "manager"]
    # within a stage the call that came back first is listed first / 同一阶段内先返回的调用排在前面
    assert [s["id"] for s in flow["steps"]] == ["long_thesis", "short_thesis", "debate_r1_rebuttal_short", "debate_r1_rebuttal_long"] + later
    glue = {s["id"]: s["glue"] for s in flow["steps"]}
    assert glue["debate_r1_rebuttal_short"] == "" and glue["debate_r1_rebuttal_long"] == "把 3 条反驳挂到各自线程上。空1 的异议被撤回，线程关闭，不再需要答辩。"
    assert glue["debate_r1_defence_long"] == "把 2 条再反驳挂到线程上。多2 认输，线程关闭。还剩 1 个争议线程。未到轮数上限，于是询问主持人。"
    assert glue["debate_r1_moderator"].endswith("判断为继续，第 2 轮只辩：多1。")
    assert glue["debate_r3_defence_long"].endswith("还剩 1 个争议线程。代码直接终止辩论：已达到 3 轮上限。")
    assert "持有 short 2 手，结果为 True" in glue["manager"] and flow["position"] == {"direction": "short", "volume": 2}
    assert "须针对对方上一轮的再反驳" in flow["steps"][6]["job"] and flow["steps"][6]["id"] == "debate_r2_rebuttal_short" and flow["rounds"] == 3 and [g["by"] for g in flow["rulings"]] == ["moderator", "moderator", "rule"]
    assert {t["id"]: t["status"] for t in flow["threads"]} == {"多1": "争议中", "多2": "所有方认输", "空1": "对方撤回异议"}
    by_id = {s["id"]: s for s in flow["steps"]}
    assert (by_id["long_thesis"]["start"], by_id["long_thesis"]["seconds"], by_id["short_thesis"]["t0"]) == ("08:45:03", 78, 0)
    assert by_id["debate_r1_rebuttal_long"]["t0"] == by_id["debate_r1_rebuttal_short"]["t0"] == by_id["short_thesis"]["t1"] + 3
    assert flow["clock0"] == 8 * 3600 + 45 * 60 + 3 and flow["wall"] == round(by_id["manager"]["t1"])

    bare = build_flow(outcome, tmp_path / "nowhere", "2026-09-29")
    assert [s["id"] for s in bare["steps"]] == ["long_thesis", "short_thesis", "debate_r1_rebuttal_long", "debate_r1_rebuttal_short"] + later and bare["wall"] is None and bare["clock0"] is None and bare["cacheFile"] == ""
    assert all(s["t0"] is None and s["cost"] is None and s["blocks"] == [] and s["result"] for s in bare["steps"])


def test_prompt_blocks_fall_back_to_the_heading():
    """
    A section the table does not know keeps its own heading as the label.

    对照表里没有的段落用它自己的标题作名称。
    """
    blocks = prompt_blocks("Role: **x**\nrules\n\n## Something new\nbody\n\n# Evidence pack — CU\n## 数据覆盖\nrows\n")
    assert [b["label"] for b in blocks] == ["角色与规则", "Something new", "证据包"] and blocks[2]["chars"] == len("# Evidence pack — CU\n## 数据覆盖\nrows\n")


def test_outputs_index_and_server(pack: Path, tmp_path: Path):
    """
    `write_outputs` writes flow.json beside debate.md and an index of every
    pack date; the server hands out those two kinds of file and the built
    template, and refuses everything else under /runs/.

    `write_outputs` 在 debate.md 旁写出 flow.json，并生成覆盖所有包日期的索引；服务只提供这两类文件
    和构建好的模板，/runs/ 下的其他内容一律拒绝。
    """
    ev = load_pack(pack)["CU"]
    cfg = JudgeConfig(runs_dir=tmp_path / "runs", max_workers=1, parallel_sides=False)
    outcome = judge_symbol(ev, None, cfg, ResonanceParams(), runner=FakeRunner())
    run_dir = cfg.runs_dir / "2026-09-29"
    write_outputs(run_dir, {"CU": outcome}, "2026-09-29", None, {"CU": {"name": "沪铜", "last_session": "2026-09-28"}}, {}, {"model": "opus", "effort": "xhigh", "max_debate_rounds": 3})
    flow = json.loads((run_dir / "CU" / "flow.json").read_text(encoding="utf-8"))
    assert flow["name"] == "沪铜" and flow["config"] == {"model": "opus", "effort": "xhigh", "maxRounds": 3}
    index = json.loads((cfg.runs_dir / "index.json").read_text(encoding="utf-8"))
    assert index == {"schema": FLOW_SCHEMA, "runs": [{"packDate": "2026-09-29", "symbols": [
        {"symbol": "CU", "name": "沪铜", "direction": "long", "confidence": 0.7, "rounds": 1, "cost": 4.0}]}]}
    (cfg.runs_dir / "2026-09-30" / "LC").mkdir(parents=True)
    (cfg.runs_dir / "2026-09-30" / "LC" / "flow.json").write_text(json.dumps({**flow, "symbol": "LC", "name": "碳酸锂"}), encoding="utf-8")
    assert [r["packDate"] for r in json.loads(write_index(cfg.runs_dir).read_text(encoding="utf-8"))["runs"]] == ["2026-09-30", "2026-09-29"]

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<p>template</p>", encoding="utf-8")
    server = make_server(cfg.runs_dir, port=0, dist_dir=dist)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def status(path: str) -> int:
        """HTTP status of a GET.

        一次 GET 的 HTTP 状态码。
        """
        try:
            return opener.open(base + path, timeout=5).status
        except urllib.error.HTTPError as exc:
            return exc.code

    try:
        assert json.loads(opener.open(base + "/runs/index.json", timeout=5).read())["schema"] == FLOW_SCHEMA
        assert json.loads(opener.open(base + "/runs/2026-09-29/CU/flow.json", timeout=5).read())["symbol"] == "CU"
        assert b"template" in opener.open(base + "/", timeout=5).read()
        for blocked in ("/runs/2026-09-29/CU/manager.prompt.md", "/runs/2026-09-29/CU/manager.response.json", "/runs/2026-09-29/decisions.json",
                        "/runs/2026-09-29/CU/" + flow["cacheFile"], "/runs/../config.py", "/runs/2026-09-29/XX/flow.json"):
            assert status(blocked) == 404, blocked
    finally:
        server.shutdown()
        server.server_close()


def test_web_fixture_matches_the_contract(pack: Path, tmp_path: Path):
    """
    The sample flow the web template is tested against has exactly the shape
    `build_flow` produces today. If this fails the contract changed:
    regenerate the fixture (`uv run python -m strategies.resonance.tests.make_web_fixture`)
    and update `web/src/types.ts`.

    网页模板测试所用的样例 flow 与 `build_flow` 当前的输出形状完全一致。若此测试失败，说明数据约定
    变了：重新生成样例（`uv run python -m strategies.resonance.tests.make_web_fixture`）并更新
    `web/src/types.ts`。
    """
    _, flow = sample_outcome(pack, tmp_path / "runs")
    assert _shape(json.loads(FIXTURE.read_text(encoding="utf-8"))) == _shape(flow)
