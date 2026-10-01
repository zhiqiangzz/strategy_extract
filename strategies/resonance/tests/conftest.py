"""
Agents: read the English part only. 中文仅供人类阅读。

Shared fixtures: a tiny evidence pack built from trimmed real payload shapes,
and a scripted fake `claude` runner that returns pre-defined structured
outputs per prompt step, so the debate can be tested without the CLI.

共享夹具：由裁剪过的真实 payload 形状构成的微型证据包，以及按提示步骤返回预设结构化输出的
假 `claude` 运行器，使辩论可以在没有 CLI 的情况下测试。
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


def _a1(symbol: str, direction: str, score: float) -> dict:
    """Minimal A1 payload with two indicators agreeing on `direction`.

    最小 A1 载荷：两个指标同向 `direction`。
    """
    return {"agent": "A1", "symbol": symbol, "contract_code": f"{symbol}2611", "futures_name": {"CU": "沪铜", "LC": "碳酸锂"}.get(symbol, symbol),
            "as_of": "2026-09-28T15:00:00+08:00", "data_quality": {"status": "VALID", "bars_used": 60, "roll_detected": True, "warnings": []},
            "latest_bar": {"trading_date": "2026-09-28", "open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 1000, "open_interest": 5000},
            "single_indicator_results": {"ema20": {"state": "X", "direction": direction, "direction_score": score, "strength": abs(score), "event": None, "bars_since_event": None, "current_values": {"close": 100.5}},
                                         "macd": {"state": "Y", "direction": direction, "direction_score": score, "strength": abs(score), "event": None, "bars_since_event": None, "current_values": {"dif": 1}}},
            "cross_index_analysis": {"rule_evaluation": {"alignment": "aligned", "support_score": score, "confidence": 0.5, "conflicts": [], "risk_flags": []},
                                     "indicator_advice": {"advice_type": "LONG_BIAS_CANDIDATE" if score > 0 else "SHORT_BIAS_CANDIDATE", "support_level": "moderate", "alignment": "aligned", "advice_summary": "s", "main_support": [], "main_conflicts": [], "confirmation_conditions": [], "invalidation_conditions": [], "limitations": []},
                                     "interpretation_gap": {"exists": False}}}


def _a2(symbol: str, score: float) -> dict:
    """Minimal A2 payload with one curve factor.

    最小 A2 载荷：一个期限结构因子。
    """
    return {"symbol": symbol, "as_of": "2026-09-29T09:30:00+08:00", "data_quality": {"status": "VALID", "latest_source_date": "2026-09-24", "stale_calendar_days": 5},
            "factor_states": {"curve": {"state": "Mild_Back", "direction": "bullish" if score > 0 else "bearish", "direction_score": score, "confidence": 0.7, "freshness_days": 5, "summary": "curve", "limitations": []}},
            "fundamental_summary": {"advice_type": "BULLISH_FUNDAMENTAL_BIAS" if score > 0 else "BEARISH_FUNDAMENTAL_BIAS", "support_level": "moderate", "support_score": score, "confidence": 0.7, "alignment": "aligned",
                                    "bullish_factors": [], "bearish_factors": [], "neutral_factors": [], "summary": "基本面", "supporting_points": [], "conflicts": [], "risk_flags": [], "data_caveats": [], "requires_confirmation": []}}


@pytest.fixture
def pack(tmp_path: Path) -> Path:
    """
    Two-symbol pack: CU (bullish everywhere) and LC (conflicting, A3 missing).

    两品种证据包：CU（各源看多）与 LC（冲突，缺 A3）。
    """
    root = tmp_path / "2026-09-29"
    (root / "manifest.json").parent.mkdir(parents=True)
    (root / "manifest.json").write_text(json.dumps({"trade_date": "2026-09-29", "symbols": ["CU", "LC"], "agents": {}}), encoding="utf-8")
    for sym, a1dir, a1score, a2score in (("CU", "bullish", 0.6, 0.8), ("LC", "bearish", -0.9, 0.5)):
        (root / "A1" / "llm" / sym).mkdir(parents=True)
        (root / "A1" / "llm" / sym / "state_payload.json").write_text(json.dumps(_a1(sym, a1dir, a1score)), encoding="utf-8")
        (root / "A1" / "llm" / sym / "input_bars.json").write_text(json.dumps({"bars": [{"trading_date": f"2026-09-{d:02d}", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1, "open_interest": 1} for d in range(1, 29)]}), encoding="utf-8")
        (root / "A2" / sym).mkdir(parents=True)
        (root / "A2" / sym / "state_payload.json").write_text(json.dumps(_a2(sym, a2score)), encoding="utf-8")
        (root / "A4" / "per_symbol" / sym).mkdir(parents=True)
        (root / "A4" / "per_symbol" / sym / "state_payload.json").write_text(json.dumps({"symbol": sym, "summary": "研报", "direction": "NEUTRAL_TO_BULLISH", "confidence_level": 0.5, "evidence": ["e1"]}), encoding="utf-8")
    (root / "A3" / "per_symbol" / "CU").mkdir(parents=True)
    (root / "A3" / "per_symbol" / "CU" / "state_payload.json").write_text(json.dumps({"usable_by_downstream": True, "symbol": "CU", "as_of": "x", "data_quality": {"status": "VALID"},
                                                                                       "news_events": [{"event_id": "A3_CU_1", "published_at": "2026-09-28T10:00:00", "direction": "bullish", "horizon": "short_term", "relevance_to_symbol": 0.8, "confidence": 0.6, "title": "copper strike"}],
                                                                                       "news_summary": {"overall_direction": "bullish", "confidence": 0.6, "summary": "新闻", "bullish_event_ids": ["A3_CU_1"]}}), encoding="utf-8")
    return root


class FakeRunner:
    """
    Fake subprocess runner: picks the response by the prompt's first line
    (Long/Short/Cross-Examination/Manager) and records the calls.

    假子进程运行器：按提示词首行（多/空/质证/Manager）选择响应并记录调用。
    """

    def __init__(self, manager_output: dict | None = None):
        """Optionally override the Manager response.

        可选覆盖 Manager 的响应。
        """
        self.calls: list[list[str]] = []
        self.manager_output = manager_output or {"symbol": "X", "direction": "long", "confidence": 0.7, "uncertain_is_high_confidence": False,
                                                 "reversal": None, "reasoning": "理由", "key_drivers": ["A1.macd"], "risk_flags": [], "evidence_quality": "good"}

    def __call__(self, cmd, **kw):
        """Pick the scripted response by the prompt's role banner.

        按提示词中的角色标题选择预设响应。
        """
        self.calls.append(cmd)
        prompt = cmd[2]
        if "Long Thesis Agent" in prompt:
            out = {"stance": "long", "thesis": "多", "key_points": [{"claim": "c", "evidence_refs": ["A1.macd"], "strength": "moderate"}], "falsifiers": ["f"], "confidence": 0.6}
        elif "Short Thesis Agent" in prompt:
            out = {"stance": "short", "thesis": "空", "key_points": [{"claim": "c", "evidence_refs": ["A2.curve"], "strength": "weak"}], "falsifiers": [], "confidence": 0.3}
        elif "Cross-Examination Agent" in prompt:
            out = {"long_rebuttals": [{"claim": "c", "rebuttal": "r", "survives": True}], "short_rebuttals": [], "unresolved_conflicts": ["x"], "data_quality_caveats": [], "net_assessment": "评估"}
        else:
            out = dict(self.manager_output)
        raw = {"type": "result", "subtype": "success", "is_error": False, "result": json.dumps(out), "structured_output": out,
               "total_cost_usd": 0.5, "modelUsage": {"claude-opus-5-5": {}}}
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(raw), stderr="")
