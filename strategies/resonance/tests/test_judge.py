"""
Agents: read the English part only. 中文仅供人类阅读。

Judge tests: evidence loading and rendering (source names, evidence ids, the
数据覆盖 table), the decision-time block in every prompt, the debate with a
fake runner (opening statements, rounds, moderator, round limit, focus,
concessions, withdrawn objections, unanswered threads), the T021 reversal
rule, caching, the report and debate record, and the setting-file conversion
(without DB) including risk budget and vt_symbol rules.

判断层测试：证据加载与渲染（来源名称、证据编号、数据覆盖表）、每个提示词里的决策时点段落、用假
运行器跑辩论（立论、多轮、主持人、轮数上限、聚焦、认输、撤回异议、未回应）、T021 反转规则、缓存、
报告与辩论记录，以及不访问 DB 的设置文件转换（风险预算与 vt_symbol 规则）。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from strategies.resonance.cli import render_report, write_outputs
from strategies.resonance.config import JudgeConfig, ResonanceParams
from strategies.resonance.debate import apply_reversal_rule, judge_many, judge_symbol
from strategies.resonance.evidence import FUNDAMENTAL, NEWS, RESEARCH, TECHNICAL, load_pack
from strategies.resonance.positions import parse_positions, variety_of
from strategies.resonance.schemas import ContractSetting, Decision, Position, ResonanceSetting, Warmup
from strategies.resonance.signal_writer import vt_symbol_for, write_setting
from strategies.resonance.tests.conftest import FakeRunner

UPSTREAM_CODE = re.compile(r"(?<![A-Za-z0-9_])A[1-5](?![A-Za-z0-9])")
ANCHOR = "You stand before the open of trading day 2026-09-29"


def _cfg(tmp_path: Path, **kw) -> JudgeConfig:
    """Judge config writing into a temp runs dir, sides run in order.

    写入临时 runs 目录的判断配置，两侧按顺序执行。
    """
    return JudgeConfig(**{"runs_dir": tmp_path / "runs", "max_workers": 1, "parallel_sides": False, **kw})


def test_load_and_render(pack: Path):
    """
    Both symbols load; LC reports 新闻 missing; evidence ids and verdicts use
    the source names; no upstream agent code survives rendering.

    两个品种都能加载；LC 标记缺新闻；证据编号与结论使用来源名称；渲染结果中不残留上游代号。
    """
    ev = load_pack(pack)
    assert set(ev) == {"CU", "LC"}
    assert ev["LC"].missing == [NEWS] and ev["CU"].missing == []
    txt = ev["CU"].render("compact")
    for evidence_id in ("技术指标.macd", "基本面.curve", "新闻.20260928_001", "研报.ev1", "id 日线"):
        assert evidence_id in txt
    assert "bullish ['新闻.20260928_001']" in txt
    assert set(ev["CU"].verdict_table()) == {TECHNICAL, FUNDAMENTAL, NEWS, RESEARCH}
    assert ev["CU"].verdict_table()[NEWS].startswith("bullish") and ev["LC"].verdict_table()[NEWS] == "unavailable"
    for sym in ev:
        for level in ("compact", "full"):
            assert not UPSTREAM_CODE.search(ev[sym].render(level))
    assert "需 汇总 复核" in ev["CU"].render("full")


def test_coverage_only_reports_past_gaps(pack: Path):
    """
    The decision time is the open of the pack date and the last session is
    the day before; a factor that ends earlier is a gap, an up-to-date
    source is not, a missing source is named, and no date on or after the
    pack date is called missing.

    决策时点是包日期开盘前，最后交易日是前一天；更早截止的因子算缺口，最新的来源不算，缺失的来源被
    点名，包日期当天及之后的日期不会被说成缺失。
    """
    ev = load_pack(pack)
    cu = ev["CU"]
    assert cu.pack_date == "2026-09-29" and cu.last_session == "2026-09-28"
    rows = {r["id"]: r for r in cu.coverage()}
    assert rows[TECHNICAL]["gap"] == "none" and rows["基本面.basis"]["gap"] == "none"
    assert rows["基本面.curve"]["through"] == "2026-09-24"
    assert rows["基本面.curve"]["gap"] == "4 calendar day(s): nothing for 2026-09-25 → 2026-09-28"
    assert "inventory latest date 2026-09-04" in rows["基本面 (upstream warnings)"]["note"]
    assert rows[NEWS]["through"] == "window 2026-09-28 08:15 → 2026-09-29 08:15" and rows[NEWS]["gap"] == "none"
    assert rows[RESEARCH]["through"] == "reports received in the 1 day(s) before 2026-09-29 08:40"
    assert {r["id"]: r for r in ev["LC"].coverage()}[NEWS]["gap"].startswith("no usable news for this symbol")
    txt = cu.render()
    assert "Decision time: before the open of trading day 2026-09-29. Last completed session: 2026-09-28." in txt
    dated_gaps = [r["gap"] for e in ev.values() for r in e.coverage() if "nothing for" in r["gap"]]
    assert dated_gaps and all(max(re.findall(r"\d{4}-\d{2}-\d{2}", g)) <= "2026-09-28" for g in dated_gaps)


def test_debate_and_cache(pack: Path, tmp_path: Path):
    """
    One round when the moderator stops: eight calls in order, every prompt
    anchored to the decision time, threads numbered per side, the manager
    sees the debate record, unknown point ids are dropped from the ruling,
    the second run hits the cache, and the transcript files exist.

    主持人在第一轮后终止时：按顺序八次调用，每个提示词都锚定决策时点，线程分方编号，Manager 能看到
    辩论记录，裁定中不存在的论据编号被丢弃，第二次运行命中缓存，留痕文件存在。
    """
    ev = load_pack(pack)
    cfg = _cfg(tmp_path)
    runner = FakeRunner()
    out = judge_symbol(ev["CU"], None, cfg, ResonanceParams(), runner=runner)
    assert runner.roles() == ["多方立论", "空方立论", "多方反驳", "空方反驳", "多方再反驳", "空方再反驳", "主持人", "Manager"]
    assert all(ANCHOR in c[2] and "the last completed session is 2026-09-28" in c[2] for c in runner.calls)
    assert all("{" + name + "}" not in c[2] for c in runner.calls for name in ("time_anchor", "pack_date", "targets", "transcript", "round_note", "own_opening"))
    efforts = [c[c.index("--effort") + 1] for c in runner.calls]
    assert efforts[6] == "medium" and set(efforts[:6] + efforts[7:]) == {"xhigh"}
    d = out.debate
    assert [t.point_id for t in d.threads] == ["多1", "多2", "空1"] and [t.owner for t in d.threads] == ["long", "long", "short"]
    assert all([(x.round, x.speaker, x.kind) for x in t.exchanges] == [(1, "short" if t.owner == "long" else "long", "rebuttal"), (1, t.owner, "defence")] for t in d.threads)
    assert d.rounds_held == 1 and [(r.decided_by, r.continue_debate) for r in d.rulings] == [("moderator", False)]
    # 多方 rebuts the 空方 point and nothing else / 多方只反驳空方的论据
    assert "### 空1" in runner.calls[2][2] and "### 多1" not in runner.calls[2][2] and "多1：均线向上" in runner.calls[2][2]
    manager = runner.calls[7][2]
    assert "### 多1" in manager and "第1轮 空方反驳〔举反例〕：反例（证据：日线）" in manager and "第1轮后，主持人：终止。双方已无新论点。" in manager
    assert out.decision.direction == "long" and out.decision.reversal is None and out.cost_usd == 4.0
    assert [v.point_id for v in out.decision.point_verdicts] == ["多1", "空1"]
    rec = tmp_path / "runs" / "2026-09-29" / "CU"
    for name in ("long_thesis", "debate_r1_rebuttal_short", "debate_r1_defence_long", "debate_r1_moderator", "manager"):
        assert (rec / f"{name}.prompt.md").exists()
    out2 = judge_symbol(ev["CU"], None, cfg, ResonanceParams(), runner=runner)
    assert out2.cached and len(runner.calls) == 8 and out2.debate == d and out2.long_thesis == out.long_thesis
    # the schema sent to the CLI forbids extra fields and requires every field, nested models included
    schema = json.loads(runner.calls[7][runner.calls[7].index("--json-schema") + 1])
    assert schema["additionalProperties"] is False and {"point_verdicts", "debate_summary", "reversal"} <= set(schema["required"])
    assert schema["$defs"]["PointVerdict"]["additionalProperties"] is False


def test_round_limit_and_focus(pack: Path, tmp_path: Path):
    """
    A moderator that always continues is cut off by the round limit (three
    rounds, 17 calls; two with `max_debate_rounds=2`), and its focus list
    restricts the later rounds to the named threads.

    总是要求继续的主持人会被轮数上限截断（三轮 17 次调用；`max_debate_rounds=2` 时两轮），其聚焦列表
    把后续轮次限制在点名的线程上。
    """
    ev = load_pack(pack)
    go_on = FakeRunner(moderator=lambda rnd: {"continue_debate": True, "reason": "仍有新证据未回应。", "focus_point_ids": []})
    out = judge_symbol(ev["CU"], None, _cfg(tmp_path / "a"), ResonanceParams(), runner=go_on)
    assert len(go_on.calls) == 17 and out.debate.rounds_held == 3 and all(len(t.exchanges) == 6 for t in out.debate.threads)
    assert [(r.decided_by, r.continue_debate) for r in out.debate.rulings] == [("moderator", True), ("moderator", True), ("rule", False)]
    assert out.debate.rulings[0].focus_point_ids == ["多1", "多2", "空1"] and "3 轮上限" in out.debate.rulings[2].reason
    # round 2 answers the latest reply instead of repeating round 1 / 第二轮针对上一轮的再反驳
    r2 = next(c[2] for c in go_on.calls if "round 2 of" in c[2] and FakeRunner.role(c) == "空方反驳")
    assert "latest 再反驳" in r2 and "第1轮 多方再反驳〔坚持〕" in r2

    two = FakeRunner(moderator=go_on.moderator)
    out = judge_symbol(ev["CU"], None, _cfg(tmp_path / "b", max_debate_rounds=2), ResonanceParams(), runner=two)
    assert out.debate.rounds_held == 2 and two.roles().count("主持人") == 1 and out.debate.rulings[-1].decided_by == "rule"

    focused = FakeRunner(moderator=lambda rnd: {"continue_debate": True, "reason": "只剩 多1 值得再辩。", "focus_point_ids": ["多1", "空7"]})
    out = judge_symbol(ev["CU"], None, _cfg(tmp_path / "c"), ResonanceParams(), runner=focused)
    assert focused.roles()[7:] == ["空方反驳", "多方再反驳", "主持人", "空方反驳", "多方再反驳", "Manager"]
    assert out.debate.rulings[0].focus_point_ids == ["多1"]
    assert {t.point_id: len(t.exchanges) for t in out.debate.threads} == {"多1": 6, "多2": 2, "空1": 2}


def test_concede_withdraw_and_silence(pack: Path, tmp_path: Path):
    """
    Conceded points and withdrawn objections close their threads; when none
    is left the code ends the debate without asking the moderator; a side
    that says nothing about a thread is marked as not having answered.

    认输和撤回异议会关闭线程；没有争议线程时由代码终止辩论而不询问主持人；对某个线程不发言的一方被
    标记为未回应。
    """
    ev = load_pack(pack)
    all_conceded = FakeRunner(concede={"多1", "多2", "空1"})
    out = judge_symbol(ev["CU"], None, _cfg(tmp_path / "a"), ResonanceParams(), runner=all_conceded)
    assert "主持人" not in all_conceded.roles() and len(all_conceded.calls) == 7
    assert {t.status for t in out.debate.threads} == {"conceded"}
    assert [(r.decided_by, r.continue_debate) for r in out.debate.rulings] == [("rule", False)] and "已无争议论据" in out.debate.rulings[0].reason

    withdrawn = FakeRunner(withdraw={"空1"})
    out = judge_symbol(ev["CU"], None, _cfg(tmp_path / "b"), ResonanceParams(), runner=withdrawn)
    threads = {t.point_id: t for t in out.debate.threads}
    assert threads["空1"].status == "objection_withdrawn" and len(threads["空1"].exchanges) == 1
    assert withdrawn.roles() == ["多方立论", "空方立论", "多方反驳", "空方反驳", "多方再反驳", "主持人", "Manager"]
    assert "Role: **主持人**" in withdrawn.calls[5][2] and "still in dispute (多1, 多2)" in withdrawn.calls[5][2]

    silent = FakeRunner(silent_rebuttal={"多2"}, silent_defence={"空1"})
    out = judge_symbol(ev["CU"], None, _cfg(tmp_path / "c"), ResonanceParams(), runner=silent)
    threads = {t.point_id: t for t in out.debate.threads}
    assert [x.unanswered for x in threads["多2"].exchanges] == [True] and [x.unanswered for x in threads["空1"].exchanges] == [False, True]
    manager = silent.calls[-1][2]
    assert "第1轮 空方反驳：（未回应）" in manager and "第1轮 空方再反驳：（未回应）" in manager


def test_reversal_rule():
    """
    T021: opposite direction or high-confidence uncertain → reversal; a
    low-confidence uncertain or same direction → no reversal; flat → None.

    T021：方向相反或高置信度不确定 → 反转；低置信度不确定或同向 → 不反转；空仓 → None。
    """
    p = ResonanceParams()
    pos = Position(vt_symbol="cu2611.SHFE", variety_code="CU", direction="long", volume=2)
    base = dict(symbol="CU", confidence=0.5, reasoning="", key_drivers=[], evidence_quality="good")
    assert apply_reversal_rule(Decision(direction="short", **base), pos, p).reversal is True
    assert apply_reversal_rule(Decision(direction="long", **base), pos, p).reversal is False
    assert apply_reversal_rule(Decision(direction="uncertain", **base), pos, p).reversal is False
    assert apply_reversal_rule(Decision(direction="uncertain", uncertain_is_high_confidence=True, **base), pos, p).reversal is True
    assert apply_reversal_rule(Decision(direction="uncertain", **{**base, "confidence": 0.8}), pos, p).reversal is True
    assert apply_reversal_rule(Decision(direction="short", **base), None, p).reversal is None


def test_judge_many_with_position(pack: Path, tmp_path: Path):
    """
    Symbols and the two sides of a step run concurrently; with an open long
    in LC and a manager saying short, LC comes back with reversal=True; the
    manager prompt mentions the position.

    品种之间、同一步的两侧都并行；LC 持多仓而 Manager 判空时，LC 返回 reversal=True；Manager 提示词
    提到持仓。
    """
    ev = load_pack(pack)
    cfg = JudgeConfig(runs_dir=tmp_path / "runs", max_workers=2, use_cache=False)
    runner = FakeRunner(manager_output={"symbol": "LC", "direction": "short", "confidence": 0.8, "uncertain_is_high_confidence": False, "reversal": False,
                                        "point_verdicts": [], "debate_summary": "", "reasoning": "r", "key_drivers": [], "risk_flags": [], "evidence_quality": "partial"})
    positions = {"LC": Position(vt_symbol="lc2701.GFEX", variety_code="LC", direction="long", volume=1, entry_price=120000)}
    outs = judge_many(ev, positions, cfg, ResonanceParams(), runner=runner)
    assert outs["LC"].decision.reversal is True and outs["CU"].decision.reversal is None
    assert len(runner.calls) == 16 and not any(o.error for o in outs.values())
    manager_prompts = [c[2] for c in runner.calls if FakeRunner.role(c) == "Manager"]
    assert any("open LONG position of 1 lots" in m for m in manager_prompts)


def test_report_and_debate_record(pack: Path, tmp_path: Path):
    """
    The report names the sources in Chinese, lists every point with its
    exchange and ruling and links the debate record; the record holds the
    opening statements, the threads with their rulings and why the debate
    ended. A failed symbol still gets its report row.

    报告用中文来源名，列出每条论据的交锋与裁定并链接辩论记录；记录包含双方立论、带裁定的线程和
    辩论终止的理由。失败的品种仍有报告行。
    """
    ev = load_pack(pack)
    outs = judge_many({"CU": ev["CU"]}, {}, _cfg(tmp_path), ResonanceParams(), runner=FakeRunner())
    report = render_report(outs, "2026-09-29", 1_000_000)
    assert "| 品种 | 技术指标 | 基本面 | 新闻 | 研报 | **方向** |" in report and not UPSTREAM_CODE.search(report)
    assert "| 多1 | 多方 | 中 | 举反例 → 坚持 | 成立 | 均线向上 |" in report and "| 多2 | 多方 | 弱 | 举反例 → 坚持 | - | 基差走强 |" in report
    assert "第1轮后，主持人：终止。双方已无新论点。" in report and "[完整辩论记录](CU/debate.md)" in report
    write_outputs(tmp_path / "out", outs, "2026-09-29", 1_000_000)
    record = (tmp_path / "out" / "CU" / "debate.md").read_text(encoding="utf-8")
    for part in ("决策时点：2026-09-29 开盘前", "### 多方立论", "## 空方论据", "### 空1（空方，强度 弱，争议中）", "- 论据：期限结构转弱", "**裁定：被驳倒。**被举反例", "## 辩论进程", "## Manager 裁决"):
        assert part in record
    failed = judge_many({"LC": ev["LC"]}, {}, _cfg(tmp_path / "f"), ResonanceParams(), runner=lambda cmd, **kw: (_ for _ in ()).throw(RuntimeError("boom")))
    assert failed["LC"].error and failed["LC"].decision.direction == "uncertain" and "| LC |" in render_report(failed, "2026-09-29", None)


def test_cli_judge_and_report(pack: Path, tmp_path: Path, monkeypatch):
    """
    `judge --dry-run` writes decisions.json (with the theses and the debate),
    report.md and the debate record; `report` re-renders the same files from
    decisions.json alone. With `--runs-dir` all three commands use that
    directory (a relative one is taken from the current directory); without
    it they use the default of JudgeConfig.

    `judge --dry-run` 写出 decisions.json（含立论与辩论）、report.md 和辩论记录；`report` 仅凭
    decisions.json 重新渲染出相同的文件。带 `--runs-dir` 时三个命令都使用该目录（相对路径相对当前
    目录）；不带时使用 JudgeConfig 的默认值。
    """
    from strategies.resonance import cli
    runner, real_many, served = FakeRunner(), cli.judge_many, []
    monkeypatch.setattr(cli, "judge_many", lambda *a, **kw: real_many(*a, runner=runner, **kw))
    monkeypatch.setattr(cli, "serve", lambda runs_dir, port: served.append((runs_dir, port)) or 0)
    monkeypatch.chdir(tmp_path)
    runs = ["--runs-dir", "runs"]
    monkeypatch.setattr(cli, "from_control_api", lambda url, account: ({}, None))
    assert cli.main(["judge", "--pack", str(pack), "--symbols", "CU", "--dry-run", "--capital", "1000000", "--max-rounds", "2", "--workers", "5", *runs]) == 0
    run_dir = tmp_path / "runs" / "2026-09-29"
    saved = json.loads((run_dir / "decisions.json").read_text(encoding="utf-8"))
    assert saved["debates"]["CU"]["rounds_held"] == 1 and set(saved["theses"]["CU"]) == {"long", "short"} and set(saved["verdicts"]["CU"]) == {TECHNICAL, FUNDAMENTAL, NEWS, RESEARCH}
    record = (run_dir / "CU" / "debate.md").read_text(encoding="utf-8")
    (run_dir / "CU" / "debate.md").unlink()
    (run_dir / "report.md").unlink()
    assert cli.main(["report", "--pack-date", "2026-09-29", *runs]) == 0
    assert (run_dir / "CU" / "debate.md").read_text(encoding="utf-8") == record
    assert "| 多1 | 多方 | 中 | 举反例 → 坚持 | 成立 | 均线向上 |" in (run_dir / "report.md").read_text(encoding="utf-8")
    assert json.loads((tmp_path / "runs" / "index.json").read_text(encoding="utf-8"))["runs"][0]["packDate"] == "2026-09-29"
    assert cli.main(["web", "--port", "8791", *runs]) == 0 and cli.main(["web"]) == 0
    assert served == [((tmp_path / "runs").resolve(), 8791), (JudgeConfig().runs_dir, 8770)]


def test_setting_file_roundtrip(tmp_path: Path):
    """
    vt_symbol rules (CZCE 3-digit month, others 4 digits lower case), risk
    budget, and a setting file that validates after write/read.

    vt_symbol 规则（CZCE 三位月份，其余小写四位）、风险预算，以及写出后可重新校验的设置文件。
    """
    assert vt_symbol_for("CU", "SHFE", "CU2611") == "cu2611.SHFE"
    assert vt_symbol_for("MA", "CZCE", "MA2610") == "MA610.CZCE"
    assert variety_of("MA610.CZCE") == "MA" and variety_of("cu2611.SHFE") == "CU"
    cs = ContractSetting(variety_code="CU", variety_name="沪铜", decision_id="2026-09-29/CU", direction="long", confidence=0.7,
                         risk_budget_cny=1_000_000 * 0.01, multiplier=5, price_tick=10, params=ResonanceParams(),
                         warmup=Warmup(bars_30m=[[1759100400, 1, 2, 0.5, 1.5, 10]], bars_1d=[["2026-09-26", 1, 2, 0.5, 1.5, 100]]))
    s = ResonanceSetting(generated_at="t", pack_date="2026-09-29", account="acct", contracts={"cu2611.SHFE": cs})
    out = write_setting(s, tmp_path / "resonance_setting_acct.json")
    back = ResonanceSetting(**json.loads(out.read_text(encoding="utf-8")))
    assert back.contracts["cu2611.SHFE"].risk_budget_cny == 10000.0 and back.contracts["cu2611.SHFE"].params.entry_lookback == 20


def test_parse_positions_shapes():
    """
    Control-API rows with is_long or direction fields both parse; zero
    volume is ignored.

    control API 的 is_long 或 direction 两种字段都能解析；零手数忽略。
    """
    rows = {"ok": True, "positions": [{"vt_symbol": "cu2611.SHFE", "symbol": "cu2611", "is_long": False, "volume": 3, "yd_volume": 1},
                                      {"vt_symbol": "rb2701.SHFE", "direction": "LONG", "volume": 0}]}
    p = parse_positions(rows)
    assert list(p) == ["CU"] and p["CU"].direction == "short" and p["CU"].volume == 3
