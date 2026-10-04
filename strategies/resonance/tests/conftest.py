"""
Agents: read the English part only. 中文仅供人类阅读。

Shared fixtures: a tiny evidence pack built from trimmed real payload shapes,
and a scripted fake `claude` runner that answers every step of the debate
(opening statements, rebuttals, replies, moderator, manager) with
pre-defined structured outputs, so the debate can be tested without the CLI.

共享夹具：由裁剪过的真实 payload 形状构成的微型证据包，以及为辩论每一步（立论、反驳、再反驳、
主持人、Manager）返回预设结构化输出的假 `claude` 运行器，使辩论可以在没有 CLI 的情况下测试。
"""
from __future__ import annotations

import json
import re
import subprocess
import threading
from pathlib import Path

import pytest

from strategies.resonance.evidence import BARS_PATH, FUNDAMENTAL, NEWS, RESEARCH, SOURCES, TECHNICAL


def _technical(symbol: str, direction: str, score: float) -> dict:
    """Minimal 技术指标 payload with two indicators agreeing on `direction`.

    最小技术指标载荷：两个指标同向 `direction`。
    """
    return {"agent": f"{SOURCES[TECHNICAL][0]}", "symbol": symbol, "contract_code": f"{symbol}2611", "futures_name": {"CU": "沪铜", "LC": "碳酸锂"}.get(symbol, symbol),
            "as_of": "2026-09-28T15:00:00+08:00", "data_quality": {"status": "VALID", "bars_used": 60, "roll_detected": True, "warnings": []},
            "latest_bar": {"trading_date": "2026-09-28", "open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 1000, "open_interest": 5000},
            "single_indicator_results": {"ema20": {"state": "X", "direction": direction, "direction_score": score, "strength": abs(score), "event": None, "bars_since_event": None, "current_values": {"close": 100.5}},
                                         "macd": {"state": "Y", "direction": direction, "direction_score": score, "strength": abs(score), "event": None, "bars_since_event": None, "current_values": {"dif": 1}}},
            "cross_index_analysis": {"rule_evaluation": {"alignment": "aligned", "support_score": score, "confidence": 0.5, "conflicts": [], "risk_flags": []},
                                     "indicator_advice": {"advice_type": "LONG_BIAS_CANDIDATE" if score > 0 else "SHORT_BIAS_CANDIDATE", "support_level": "moderate", "alignment": "aligned", "advice_summary": "s", "main_support": [], "main_conflicts": [], "confirmation_conditions": [], "invalidation_conditions": [], "limitations": []},
                                     "interpretation_gap": {"exists": False}}}


def _fundamental(symbol: str, score: float) -> dict:
    """Minimal 基本面 payload: a curve factor four days behind the last session and a fresh basis factor.

    最小基本面载荷：一个落后最后交易日四天的期限结构因子和一个最新的基差因子。
    """
    factor = {"state": "Mild_Back", "direction": "bullish" if score > 0 else "bearish", "direction_score": score, "confidence": 0.7, "summary": "f", "limitations": []}
    return {"symbol": symbol, "as_of": "2026-09-28T20:30:00+08:00", "data_quality": {"status": "VALID", "latest_source_date": "2026-09-28", "stale_calendar_days": 0, "warnings": ["inventory latest date 2026-09-04 is stale relative to 2026-09-28"]},
            "factor_states": {"curve": {**factor, "source_date": "2026-09-24", "freshness_days": 4}, "basis": {**factor, "source_date": "2026-09-28", "freshness_days": 0}},
            "fundamental_summary": {"advice_type": "BULLISH_FUNDAMENTAL_BIAS" if score > 0 else "BEARISH_FUNDAMENTAL_BIAS", "support_level": "moderate", "support_score": score, "confidence": 0.7, "alignment": "aligned",
                                    "bullish_factors": [], "bearish_factors": [], "neutral_factors": [], "summary": "基本面", "supporting_points": [], "conflicts": [], "risk_flags": [], "data_caveats": [], "requires_confirmation": []}}


def build_pack(tmp_path: Path) -> Path:
    """
    Two-symbol pack dated 2026-09-29: CU (bullish everywhere) and LC
    (conflicting, no 新闻). Files sit at the upstream paths listed in
    `evidence.SOURCES`.

    日期为 2026-09-29 的两品种证据包：CU（各来源看多）与 LC（冲突，缺新闻）。文件位于
    `evidence.SOURCES` 列出的上游路径。
    """
    root = tmp_path / "2026-09-29"
    news_code = SOURCES[NEWS][0]

    def put(label: str, sym: str, payload: dict) -> None:
        """Write one source's payload for one symbol.

        写出一个品种某个来源的 payload。
        """
        p = root / SOURCES[label][1].format(symbol=sym)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(payload), encoding="utf-8")

    root.mkdir(parents=True)
    (root / "manifest.json").write_text(json.dumps({"trade_date": "2026-09-29", "symbols": ["CU", "LC"], "agents": {
        news_code: {"since": "2026-09-28T08:15:00+08:00", "as_of": "2026-09-29T08:15:00+08:00"},
        SOURCES[RESEARCH][0]: {"as_of": "2026-09-29T08:40:00+08:00", "lookback_days": 1}}}), encoding="utf-8")
    for sym, direction, tech_score, fund_score in (("CU", "bullish", 0.6, 0.8), ("LC", "bearish", -0.9, 0.5)):
        put(TECHNICAL, sym, _technical(sym, direction, tech_score))
        (root / BARS_PATH.format(symbol=sym)).write_text(json.dumps({"bars": [{"trading_date": f"2026-09-{d:02d}", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1, "open_interest": 1} for d in range(1, 29)]}), encoding="utf-8")
        put(FUNDAMENTAL, sym, _fundamental(sym, fund_score))
        put(RESEARCH, sym, {"symbol": sym, "summary": "研报", "direction": "NEUTRAL_TO_BULLISH", "confidence_level": 0.5, "evidence": ["e1"]})
    put(NEWS, "CU", {"usable_by_downstream": True, "symbol": "CU", "as_of": "2026-09-29T08:15:00+08:00", "data_quality": {"status": "VALID", "news_count": 4, "used_news_count": 1},
                     "news_events": [{"event_id": f"{news_code}_CU_20260928_001", "published_at": "2026-09-28T10:00:00", "direction": "bullish", "horizon": "short_term", "relevance_to_symbol": 0.8, "confidence": 0.6,
                                      "title": "copper strike", "limitations": [f"需 {news_code[0]}5 复核"]}],
                     "news_summary": {"overall_direction": "bullish", "confidence": 0.6, "summary": "新闻", "bullish_event_ids": [f"{news_code}_CU_20260928_001"]}})
    return root


@pytest.fixture
def pack(tmp_path: Path) -> Path:
    """
    The pack of `build_pack` in the test's temp dir.

    在测试的临时目录里生成 `build_pack` 的证据包。
    """
    return build_pack(tmp_path)


class FakeRunner:
    """
    Fake subprocess runner. It reads the role from the prompt's first line
    (`Role: **…**`) and the point ids from the thread headings (`### 多1`),
    and returns a scripted structured output. `concede` / `withdraw` /
    `silent_rebuttal` / `silent_defence` are sets of point ids that change
    the scripted behaviour; `moderator(round)` returns the moderator's
    ruling. Every call is recorded.

    假子进程运行器。从提示词首行（`Role: **…**`）读角色、从线程标题（`### 多1`）读论据编号，返回预设
    的结构化输出。`concede` / `withdraw` / `silent_rebuttal` / `silent_defence` 是改变预设行为的论据
    编号集合；`moderator(round)` 返回主持人的判断。每次调用都会被记录。
    """

    def __init__(self, manager_output: dict | None = None, moderator=None, concede=(), withdraw=(), silent_rebuttal=(), silent_defence=()):
        """Configure the scripted behaviour.

        配置预设行为。
        """
        self.calls: list[list[str]] = []
        self._lock = threading.Lock()
        self.manager_output = manager_output or {"symbol": "X", "direction": "long", "confidence": 0.7, "uncertain_is_high_confidence": False, "reversal": None,
                                                 "point_verdicts": [{"point_id": "多1", "verdict": "stands", "reason": "反驳未能动摇"}, {"point_id": "空1", "verdict": "refuted", "reason": "被举反例"},
                                                                    {"point_id": "多9", "verdict": "stands", "reason": "不存在的编号"}],
                                                 "debate_summary": "多方占优", "reasoning": "理由", "key_drivers": ["多1: 技术指标.macd"], "risk_flags": [], "evidence_quality": "good"}
        self.moderator = moderator or (lambda rnd: {"continue_debate": False, "reason": "双方已无新论点。", "focus_point_ids": []})
        self.concede, self.withdraw = set(concede), set(withdraw)
        self.silent_rebuttal, self.silent_defence = set(silent_rebuttal), set(silent_defence)

    @staticmethod
    def role(cmd: list[str]) -> str:
        """The role tag of a recorded call.

        一次已记录调用的角色标签。
        """
        return cmd[2].split("**")[1]

    def roles(self) -> list[str]:
        """Role tags of all recorded calls, in call order.

        全部已记录调用的角色标签，按调用顺序。
        """
        return [self.role(c) for c in self.calls]

    def __call__(self, cmd, **kw):
        """Return the scripted response for the prompt's role.

        按提示词的角色返回预设响应。
        """
        with self._lock:
            self.calls.append(cmd)
        prompt, role = cmd[2], self.role(cmd)
        ids = re.findall(r"^### ((?:多|空)\d+)", prompt, re.M)
        if role == "多方立论":
            out = {"stance": "long", "thesis": "多", "confidence": 0.6, "falsifiers": ["f"],
                   "key_points": [{"claim": "均线向上", "reasoning": "因为…", "evidence_refs": ["技术指标.macd"], "strength": "moderate"},
                                  {"claim": "基差走强", "reasoning": "因为…", "evidence_refs": ["基本面.basis"], "strength": "weak"}]}
        elif role == "空方立论":
            out = {"stance": "short", "thesis": "空", "confidence": 0.3, "falsifiers": [],
                   "key_points": [{"claim": "期限结构转弱", "reasoning": "因为…", "evidence_refs": ["基本面.curve"], "strength": "weak"}]}
        elif role.endswith("再反驳"):
            out = {"defences": [{"point_id": i, "stance": "concede" if i in self.concede else "maintain", "argument": "答辩", "evidence_refs": [], "revised_claim": None}
                                for i in ids if i not in self.silent_defence]}
        elif role.endswith("反驳"):
            out = {"rebuttals": [{"point_id": i, "attack_type": "counterexample", "argument": "反例", "evidence_refs": ["日线"], "withdrawn": i in self.withdraw}
                                 for i in ids if i not in self.silent_rebuttal]}
        elif role == "主持人":
            out = self.moderator(int(re.search(r"Round (\d+) of at most", prompt).group(1)))
        else:
            out = dict(self.manager_output)
        raw = {"type": "result", "subtype": "success", "is_error": False, "result": json.dumps(out), "structured_output": out,
               "total_cost_usd": 0.5, "modelUsage": {"claude-opus-5-5": {}}}
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(raw), stderr="")
