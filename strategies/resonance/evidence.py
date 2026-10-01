"""
Agents: read the English part only. 中文仅供人类阅读。

evidence.py — load an A5 evidence pack (A1–A4) and render it for the LLM.

`load_pack(pack_dir)` reads `manifest.json` and, for every symbol, the four
state payloads: A1 `A1/llm/<S>/state_payload.json` (technical indicators on
daily bars), A2 `A2/<S>/state_payload.json` (fundamental factors), A3
`A3/per_symbol/<S>/state_payload.json` (Jin10 news; may be missing or
unusable), A4 `A4/per_symbol/<S>/state_payload.json` (research reports;
optionally the SHORT/MEDIUM/LONG horizon views from
`A4/full_research_result.json`). `Evidence.render(level)` turns one symbol's
pack into the Markdown block that goes into every prompt: `compact` keeps the
per-agent verdicts, scores, summaries, top events and caveats (≈4–6k tokens);
`full` appends the raw payload JSON. Each item carries a stable evidence id
(`A1.macd`, `A2.curve`, `A3.<event_id>`, `A4.ev3`) so theses can cite it.

evidence.py 读取 A5 证据包（A1–A4）并渲染给 LLM。`load_pack(pack_dir)` 读 `manifest.json`，
对每个品种读四个 state payload：A1（日线技术指标）、A2（基本面因子）、A3（金十新闻，可能缺失或
不可用）、A4（研报；可选附加 `A4/full_research_result.json` 中的短/中/长期视角）。
`Evidence.render(level)` 把一个品种的证据渲染成每个提示词都包含的 Markdown 块：`compact` 保留各
代理的结论、分数、摘要、重点事件和注意事项（约 4–6k token）；`full` 附加原始 JSON。每条证据带
稳定 id（`A1.macd`、`A2.curve`、`A3.<event_id>`、`A4.ev3`），供论证引用。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


def _load(p: Path) -> Optional[dict]:
    """
    Read a JSON file or return None when absent/invalid.

    读取 JSON，缺失或非法时返回 None。
    """
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


@dataclass
class Evidence:
    """
    One symbol's evidence from the four agents plus run metadata.

    一个品种来自四个代理的证据及运行元数据。
    """
    symbol: str
    pack_date: str
    a1: Optional[dict] = None
    a2: Optional[dict] = None
    a3: Optional[dict] = None
    a4: Optional[dict] = None
    a4_horizons: list[dict] = field(default_factory=list)
    a1_bars: list[dict] = field(default_factory=list)
    daily_bars: list[dict] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    @property
    def variety_name(self) -> str:
        """
        Chinese variety name as reported by A1 (fallback: symbol).

        A1 报告的中文品种名（缺省用代码）。
        """
        return (self.a1 or {}).get("futures_name") or self.symbol

    @property
    def contract_code(self) -> str:
        """
        Contract code A1 used (e.g. CU2611).

        A1 使用的合约代码（如 CU2611）。
        """
        return (self.a1 or {}).get("contract_code") or ""

    def verdict_table(self) -> dict[str, str]:
        """
        The four agents' own one-line verdicts (for the report).

        四个代理各自的一行结论（用于报告）。
        """
        out: dict[str, str] = {}
        if self.a1:
            adv = (self.a1.get("cross_index_analysis") or {}).get("indicator_advice") or {}
            rule = (self.a1.get("cross_index_analysis") or {}).get("rule_evaluation") or {}
            out["A1"] = f"{adv.get('advice_type', '?')} ({adv.get('support_level', '?')}, rule score {rule.get('support_score', '?')})"
        if self.a2:
            fs = self.a2.get("fundamental_summary") or {}
            out["A2"] = f"{fs.get('advice_type', '?')} (score {fs.get('support_score', '?')}, conf {fs.get('confidence', '?')})"
        if self.a3 and self.a3.get("usable_by_downstream", True):
            ns = self.a3.get("news_summary") or {}
            out["A3"] = f"{ns.get('overall_direction', '?')} (conf {ns.get('confidence', '?')})"
        else:
            out["A3"] = "unavailable"
        if self.a4:
            out["A4"] = f"{self.a4.get('direction', '?')} (conf {self.a4.get('confidence_level', '?')})"
        return out

    def render(self, level: str = "compact") -> str:
        """
        Markdown evidence block with stable ids; `full` appends raw JSON.

        带稳定 id 的 Markdown 证据块；`full` 附加原始 JSON。
        """
        L: list[str] = [f"# Evidence pack {self.pack_date} — {self.symbol} ({self.variety_name}, contract {self.contract_code})", ""]
        if self.missing:
            L.append(f"Missing or unusable sources: {', '.join(self.missing)}")
            L.append("")
        L += self._render_a1() + self._render_a2() + self._render_a3() + self._render_a4()
        if self.daily_bars:
            L.append("## Recent daily bars (main contract, newest last) — id D")
            L.append("date | open | high | low | close | volume | open_interest")
            for b in self.daily_bars:
                L.append(f"{b.get('trading_date')} | {b.get('open')} | {b.get('high')} | {b.get('low')} | {b.get('close')} | {b.get('volume')} | {b.get('open_interest')}")
            L.append("")
        if level == "full":
            L.append("## Raw payloads")
            for tag, payload in (("A1", self.a1), ("A2", self.a2), ("A3", self.a3), ("A4", self.a4)):
                if payload:
                    L.append(f"### {tag} raw\n```json\n{json.dumps(payload, ensure_ascii=False)[:60000]}\n```")
        return "\n".join(L)

    def _render_a1(self) -> list[str]:
        """
        A1: data quality, latest bar, each indicator's state/direction/score,
        rule evaluation, interpreter advice and the interpretation gap.

        A1：数据质量、最新 K 线、各指标状态/方向/分数、规则评估、解读建议与解读差异。
        """
        a = self.a1
        if not a:
            return ["## A1 technical indicators: not available", ""]
        dq = a.get("data_quality") or {}
        lb = a.get("latest_bar") or {}
        L = ["## A1 — technical indicators (daily bars, deterministic calculators + rule layer + LLM interpreter)",
             f"as_of {a.get('as_of')}; data_quality {dq.get('status')} (bars {dq.get('bars_used')}, roll_detected {dq.get('roll_detected')}, warnings {dq.get('warnings')})",
             f"latest bar {lb.get('trading_date')}: O {lb.get('open')} H {lb.get('high')} L {lb.get('low')} C {lb.get('close')} vol {lb.get('volume')} OI {lb.get('open_interest')}",
             "", "id | indicator | state | direction | score | strength | event | key values"]
        for name, r in (a.get("single_indicator_results") or {}).items():
            cv = r.get("current_values") or {}
            keyvals = ", ".join(f"{k}={v}" for k, v in list(cv.items())[:5])
            L.append(f"A1.{name} | {name} | {r.get('state')} | {r.get('direction')} | {r.get('direction_score')} | {r.get('strength')} | {r.get('event')} ({r.get('bars_since_event')} bars ago) | {keyvals}")
        cx = a.get("cross_index_analysis") or {}
        rule = cx.get("rule_evaluation") or {}
        adv = cx.get("indicator_advice") or {}
        gap = cx.get("interpretation_gap") or {}
        L += ["", f"A1.rule — rule layer: alignment {rule.get('alignment')}, support_score {rule.get('support_score')}, confidence {rule.get('confidence')}, conflicts {rule.get('conflicts')}, risk_flags {rule.get('risk_flags')}",
              f"A1.advice — interpreter: {adv.get('advice_type')} / support {adv.get('support_level')} / alignment {adv.get('alignment')}: {adv.get('advice_summary')}",
              f"  main_support: {adv.get('main_support')}", f"  main_conflicts: {adv.get('main_conflicts')}",
              f"  confirmation_conditions: {adv.get('confirmation_conditions')}", f"  invalidation_conditions: {adv.get('invalidation_conditions')}",
              f"  limitations: {adv.get('limitations')}"]
        if gap.get("exists"):
            L.append(f"A1.gap — rule layer vs interpreter disagree: rule says {(gap.get('rule_layer_view') or {}).get('message')!r}; interpreter says {(gap.get('interpreter_layer_view') or {}).get('message')!r}; downstream_resolution_needed={gap.get('downstream_resolution_needed')}")
        return L + [""]

    def _render_a2(self) -> list[str]:
        """
        A2: five fundamental factors with direction/score/confidence/freshness
        and the rule-generated summary.

        A2：五个基本面因子的方向/分数/置信度/新鲜度及规则生成的总结。
        """
        a = self.a2
        if not a:
            return ["## A2 fundamentals: not available", ""]
        dq = a.get("data_quality") or {}
        L = ["## A2 — fundamental factors (curve, inventory, basis, external parity, chain margin)",
             f"as_of {a.get('as_of')}; data_quality {dq.get('status')}; latest_source_date {dq.get('latest_source_date')} (stale {dq.get('stale_calendar_days')} calendar days)",
             "", "id | factor | state | direction | score | confidence | freshness_days | summary"]
        for name, f in (a.get("factor_states") or {}).items():
            L.append(f"A2.{name} | {name} | {f.get('state')} | {f.get('direction')} | {f.get('direction_score')} | {f.get('confidence')} | {f.get('freshness_days')} | {f.get('summary')}")
            if f.get("limitations"):
                L.append(f"    limitations: {f.get('limitations')}")
        fs = a.get("fundamental_summary") or {}
        L += ["", f"A2.summary — {fs.get('advice_type')} / support {fs.get('support_level')} score {fs.get('support_score')} conf {fs.get('confidence')} alignment {fs.get('alignment')}",
              f"  bullish: {fs.get('bullish_factors')}; bearish: {fs.get('bearish_factors')}; neutral: {fs.get('neutral_factors')}",
              f"  summary_zh: {fs.get('summary')}", f"  supporting_points: {fs.get('supporting_points')}", f"  conflicts: {fs.get('conflicts')}",
              f"  risk_flags: {fs.get('risk_flags')}", f"  data_caveats: {fs.get('data_caveats')}", f"  requires_confirmation: {fs.get('requires_confirmation')}"]
        return L + [""]

    def _render_a3(self) -> list[str]:
        """
        A3: news summary and the used events with direction/horizon/relevance.

        A3：新闻总结及使用的事件（方向/期限/相关度）。
        """
        a = self.a3
        if not a or not a.get("usable_by_downstream", True):
            return ["## A3 news: not available or marked unusable for this symbol (treat news as unknown, not neutral)", ""]
        dq = a.get("data_quality") or {}
        ns = a.get("news_summary") or {}
        L = ["## A3 — Jin10 news (previous day 08:15 → today 08:15)",
             f"as_of {a.get('as_of')}; data_quality {dq.get('status')} (news {dq.get('news_count')}, used {dq.get('used_news_count')}, latest {dq.get('latest_news_time')})",
             f"A3.summary — overall_direction {ns.get('overall_direction')} conf {ns.get('confidence')}: {ns.get('summary')}",
             f"  bullish {ns.get('bullish_event_ids')} bearish {ns.get('bearish_event_ids')} two_sided {ns.get('two_sided_event_ids')} short_term {ns.get('short_term_relevant_event_ids')}; risk_flags {ns.get('risk_flags')}",
             "", "id | time | direction | horizon | relevance | conf | title"]
        for e in a.get("news_events") or []:
            L.append(f"A3.{e.get('event_id')} | {str(e.get('published_at'))[:16]} | {e.get('direction')} | {e.get('horizon')} | {e.get('relevance_to_symbol')} | {e.get('confidence')} | {str(e.get('title'))[:140]}")
        return L + [""]

    def _render_a4(self) -> list[str]:
        """
        A4: research-report direction with evidence sentences and, if
        available, the SHORT/MEDIUM/LONG horizon views.

        A4：研报方向及证据句，若有则附短/中/长期视角。
        """
        a = self.a4
        if not a:
            return ["## A4 research reports: not available", ""]
        L = ["## A4 — research reports (email/PDF retrieval + verified analysis)",
             f"A4.summary — direction {a.get('direction')} confidence {a.get('confidence_level')}: {a.get('summary')}", ""]
        for i, ev in enumerate(a.get("evidence") or [], 1):
            text = ev if isinstance(ev, str) else json.dumps(ev, ensure_ascii=False)
            L.append(f"A4.ev{i} | {str(text)[:400]}")
        for h in self.a4_horizons:
            L.append(f"A4.{str(h.get('horizon', '')).lower()} | horizon {h.get('horizon')}: {h.get('direction')} score {h.get('directional_score')} conf {h.get('confidence')} verified={h.get('verified', h.get('passed'))}: {str(h.get('thesis') or h.get('summary') or '')[:300]}")
        return L + [""]


def load_pack(pack_dir: Path, symbols: Optional[list[str]] = None, a1_bars_tail: int = 20) -> dict[str, Evidence]:
    """
    Load every symbol in the pack (or the given subset) into Evidence objects.

    把证据包中的每个品种（或指定子集）加载为 Evidence 对象。
    """
    pack_dir = Path(pack_dir)
    manifest = _load(pack_dir / "manifest.json") or {}
    pack_date = manifest.get("trade_date") or pack_dir.name
    all_syms = list(manifest.get("symbols") or [])
    if not all_syms and (pack_dir / "A1" / "llm").exists():
        all_syms = sorted(p.name for p in (pack_dir / "A1" / "llm").iterdir() if p.is_dir())
    wanted = [s.upper() for s in symbols] if symbols else all_syms
    research = _load(pack_dir / "A4" / "full_research_result.json") or {}
    horizons_by_sym: dict[str, list[dict]] = {}
    for c in research.get("commodities") or []:
        sym = (c.get("symbol") or c.get("code") or "").upper()
        views = ((c.get("draft") or {}).get("horizon_views")) or []
        if sym and views:
            horizons_by_sym[sym] = views
    out: dict[str, Evidence] = {}
    for s in wanted:
        ev = Evidence(symbol=s, pack_date=pack_date)
        ev.a1 = _load(pack_dir / "A1" / "llm" / s / "state_payload.json")
        if ev.a1 is None:
            ev.missing.append("A1")
        bars = (_load(pack_dir / "A1" / "llm" / s / "input_bars.json") or {}).get("bars") or []
        ev.a1_bars = bars[-a1_bars_tail:]
        ev.a2 = _load(pack_dir / "A2" / s / "state_payload.json")
        if ev.a2 is None:
            ev.missing.append("A2")
        ev.a3 = _load(pack_dir / "A3" / "per_symbol" / s / "state_payload.json")
        if ev.a3 is None or not ev.a3.get("usable_by_downstream", True):
            ev.missing.append("A3")
        ev.a4 = _load(pack_dir / "A4" / "per_symbol" / s / "state_payload.json")
        if ev.a4 is None:
            ev.missing.append("A4")
        ev.a4_horizons = horizons_by_sym.get(s, [])
        if ev.a1_bars:
            ev.daily_bars = [{"trading_date": b.get("trading_date"), "open": b.get("open"), "high": b.get("high"), "low": b.get("low"),
                              "close": b.get("close"), "volume": b.get("volume"), "open_interest": b.get("open_interest")} for b in ev.a1_bars]
        out[s] = ev
    return out
