"""
Agents: read the English part only. 中文仅供人类阅读。

Judge tests: evidence loading and rendering, the four-step debate with a
fake runner, the T021 reversal rule, caching, and the setting-file
conversion (without DB) including risk budget and vt_symbol rules.

判断层测试：证据加载与渲染、用假运行器跑四步辩论、T021 反转规则、缓存，以及不访问 DB 的设置文件
转换（风险预算与 vt_symbol 规则）。
"""
from __future__ import annotations

import json
from pathlib import Path

from strategies.resonance.config import JudgeConfig, ResonanceParams
from strategies.resonance.debate import JudgeOutcome, apply_reversal_rule, judge_many, judge_symbol
from strategies.resonance.evidence import load_pack
from strategies.resonance.positions import parse_positions, variety_of
from strategies.resonance.schemas import ContractSetting, Decision, Position, ResonanceSetting, Warmup, json_schema_for
from strategies.resonance.signal_writer import vt_symbol_for, write_setting
from strategies.resonance.tests.conftest import FakeRunner


def test_load_and_render(pack: Path):
    """
    Both symbols load; LC reports A3 missing; evidence ids appear in the text.

    两个品种都能加载；LC 标记缺 A3；文本中含证据 id。
    """
    ev = load_pack(pack)
    assert set(ev) == {"CU", "LC"}
    assert ev["LC"].missing == ["A3"] and ev["CU"].missing == []
    txt = ev["CU"].render("compact")
    assert "A1.macd" in txt and "A2.curve" in txt and "A3.A3_CU_1" in txt and "A4.ev1" in txt
    assert ev["CU"].verdict_table()["A3"].startswith("bullish")
    assert ev["LC"].verdict_table()["A3"] == "unavailable"


def test_debate_and_cache(pack: Path, tmp_path: Path):
    """
    Four CLI calls per symbol in order, a Decision comes back, the second
    run hits the cache (no calls), and the transcript files exist.

    每品种按顺序四次 CLI 调用，返回 Decision；第二次运行命中缓存（无调用）；留痕文件存在。
    """
    ev = load_pack(pack)
    cfg = JudgeConfig(runs_dir=tmp_path / "runs", max_workers=1)
    runner = FakeRunner()
    out = judge_symbol(ev["CU"], None, cfg, ResonanceParams(), runner=runner)
    assert [c[2].split("**")[1] for c in runner.calls] == ["Long Thesis Agent", "Short Thesis Agent", "Cross-Examination Agent", "Manager"]
    assert out.decision.direction == "long" and out.decision.reversal is None and out.cost_usd == 2.0
    assert (tmp_path / "runs" / "2026-09-29" / "CU" / "manager.prompt.md").exists()
    out2 = judge_symbol(ev["CU"], None, cfg, ResonanceParams(), runner=runner)
    assert out2.cached and len(runner.calls) == 4
    # the schema sent to the CLI forbids extra fields
    assert json.loads(runner.calls[3][runner.calls[3].index("--json-schema") + 1])["additionalProperties"] is False


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
    With an open long in LC and a manager saying short, LC comes back with
    reversal=True; the manager prompt mentions the position.

    LC 持多仓而 Manager 判空时，LC 返回 reversal=True；Manager 提示词提到持仓。
    """
    ev = load_pack(pack)
    cfg = JudgeConfig(runs_dir=tmp_path / "runs", max_workers=2, use_cache=False)
    runner = FakeRunner(manager_output={"symbol": "LC", "direction": "short", "confidence": 0.8, "uncertain_is_high_confidence": False, "reversal": False,
                                        "reasoning": "r", "key_drivers": [], "risk_flags": [], "evidence_quality": "partial"})
    positions = {"LC": Position(vt_symbol="lc2701.GFEX", variety_code="LC", direction="long", volume=1, entry_price=120000)}
    outs = judge_many(ev, positions, cfg, ResonanceParams(), runner=runner)
    assert outs["LC"].decision.reversal is True and outs["CU"].decision.reversal is None
    manager_prompts = [c[2] for c in runner.calls if "**Manager**" in c[2]]
    assert any("open LONG position of 1 lots" in m for m in manager_prompts)


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
