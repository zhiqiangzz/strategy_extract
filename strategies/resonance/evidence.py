"""
Agents: read the English part only. 中文仅供人类阅读。

evidence.py — load an evidence pack of Multi-Agent-Trading-Platform (the
output of its 汇总 run) and render it for the LLM.

A pack dated D holds what was known before trading day D from four sources,
named here and in every prompt and report by their Chinese names: 技术指标
(technical indicators on daily bars), 基本面 (fundamental factors), 新闻
(Jin10 news; may be missing or unusable) and 研报 (research reports,
optionally with the SHORT/MEDIUM/LONG horizon views). `SOURCES` is the only
place where the upstream directory names of a pack appear.

`load_pack(pack_dir)` reads `manifest.json` and the four state payloads of
every symbol, and works out the last completed session before D.
`Evidence.render(level)` turns one symbol's pack into the Markdown block that
goes into the prompts: a header with the decision time, the 数据覆盖 table
(`Evidence.coverage()`: up to which date each source has data and which past
dates it lacks), then per-source verdicts, scores, summaries, events and
caveats (`compact`, ≈4–6k tokens); `full` appends the raw payload JSON. Each
item carries a stable evidence id (`技术指标.macd`, `基本面.curve`,
`新闻.20260929_001`, `研报.ev3`, `日线`) so arguments can cite it.

evidence.py 读取 Multi-Agent-Trading-Platform 汇总运行产出的证据包并渲染给 LLM。日期为 D 的证据包
是 D 这个交易日之前已知的信息，来自四个来源，在这里以及所有提示词和报告中都用中文名称呼：技术指标
（日线技术指标）、基本面（基本面因子）、新闻（金十新闻，可能缺失或不可用）、研报（可选附加短/中/长期
视角）。上游证据包的目录名只出现在 `SOURCES` 这一处。`load_pack(pack_dir)` 读 `manifest.json` 和每个
品种的四个 state payload，并算出 D 之前最后一个完整交易日。`Evidence.render(level)` 把一个品种的
证据渲染成提示词里的 Markdown 块：带决策时点的标题、数据覆盖表（`Evidence.coverage()`：每个来源的
数据截至哪天、缺哪些过去的日期），然后是各来源的结论、分数、摘要、事件和注意事项（`compact`，约
4–6k token）；`full` 附加原始 JSON。每条证据带稳定编号（`技术指标.macd`、`基本面.curve`、
`新闻.20260929_001`、`研报.ev3`、`日线`），供论据引用。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

TECHNICAL, FUNDAMENTAL, NEWS, RESEARCH, DAILY = "技术指标", "基本面", "新闻", "研报", "日线"

# source label -> (upstream agent directory in a pack, per-symbol payload path); the upstream names exist only here
# 来源名称 -> （证据包内的上游目录，逐品种 payload 路径）；上游命名只出现在这里
SOURCES: dict[str, tuple[str, str]] = {
    TECHNICAL: ("A1", "A1/llm/{symbol}/state_payload.json"),
    FUNDAMENTAL: ("A2", "A2/{symbol}/state_payload.json"),
    NEWS: ("A3", "A3/per_symbol/{symbol}/state_payload.json"),
    RESEARCH: ("A4", "A4/per_symbol/{symbol}/state_payload.json"),
}
BARS_PATH = "A1/llm/{symbol}/input_bars.json"
RESEARCH_FULL_PATH = "A4/full_research_result.json"
_UPSTREAM_LABEL = {code: label for label, (code, _) in SOURCES.items()} | {"A5": "汇总"}
_UPSTREAM_CODE = re.compile(r"(?<![A-Za-z0-9_])(A[1-5])(?![A-Za-z0-9])")
_NEWS_ID = re.compile(r"(?<![A-Za-z0-9_])" + SOURCES[NEWS][0] + r"_[A-Za-z]+_(?=\d)")


def _load(p: Path) -> Optional[dict]:
    """
    Read a JSON file or return None when absent/invalid.

    读取 JSON，缺失或非法时返回 None。
    """
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _day(value: object) -> Optional[date]:
    """
    The calendar date at the start of an ISO date/datetime string, or None.

    取 ISO 日期/时间字符串开头的日期，无法解析时返回 None。
    """
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _minute(value: object) -> str:
    """
    "2026-09-30T08:15:00+08:00" -> "2026-09-30 08:15" (empty for None).

    把 ISO 时间截到分钟并去掉 T；None 返回空串。
    """
    return str(value)[:16].replace("T", " ") if value else ""


def _num(value: object) -> object:
    """
    Round a float to two decimals for display; anything else is returned
    unchanged.

    显示用：浮点数保留两位小数，其他值原样返回。
    """
    return round(value, 2) if isinstance(value, float) else value


def _news_id(event_id: object) -> str:
    """
    Upstream news event id -> evidence id: the upstream prefix and symbol are
    dropped, the date and sequence stay ("新闻.20260929_001").

    上游新闻事件 id -> 证据编号：去掉上游前缀和品种，保留日期与序号。
    """
    return f"{NEWS}.{_NEWS_ID.sub('', str(event_id))}"


def _localize(text: str) -> str:
    """
    Replace upstream agent codes that appear inside payload text with the
    source names used everywhere else.

    把 payload 文本里出现的上游代号替换为统一使用的来源名称。
    """
    text = _NEWS_ID.sub(f"{NEWS}.", text)
    return _UPSTREAM_CODE.sub(lambda m: _UPSTREAM_LABEL[m.group(1)], text)


def _gap(through: Optional[date], last_session: Optional[date]) -> str:
    """
    Describe what a source lacks between its last observation and the last
    completed session: "none", or the missing past dates.

    描述一个来源从最后一条数据到最后一个完整交易日之间缺什么："none" 或缺失的过去日期。
    """
    if through is None:
        return "no dated observation"
    if last_session is None or through >= last_session:
        return "none"
    days = (last_session - through).days
    first = through + timedelta(days=1)
    span = first.isoformat() if days == 1 else f"{first.isoformat()} → {last_session.isoformat()}"
    return f"{days} calendar day(s): nothing for {span}"


@dataclass
class Evidence:
    """
    One symbol's evidence from the four sources plus the timing of the pack.

    一个品种来自四个来源的证据及证据包的时间信息。
    """
    symbol: str
    pack_date: str
    last_session: str = ""
    technical: Optional[dict] = None
    fundamental: Optional[dict] = None
    news: Optional[dict] = None
    research: Optional[dict] = None
    research_horizons: list[dict] = field(default_factory=list)
    research_status: str = ""
    daily_bars: list[dict] = field(default_factory=list)
    timing: dict = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)

    @property
    def variety_name(self) -> str:
        """
        Chinese variety name as reported by 技术指标 (fallback: symbol).

        技术指标 payload 报告的中文品种名（缺省用代码）。
        """
        return (self.technical or {}).get("futures_name") or self.symbol

    @property
    def contract_code(self) -> str:
        """
        Contract code the 技术指标 bars are built on (e.g. CU2611).

        技术指标所用 K 线的合约代码（如 CU2611）。
        """
        return (self.technical or {}).get("contract_code") or ""

    @property
    def daily_atr(self) -> Optional[float]:
        """
        Daily ATR as of the last session: the value of the 技术指标 `atr_14`
        indicator, else the mean true range of the daily bars in the pack
        (at most the last 14), else None.

        截至最后交易日的日线 ATR：取技术指标 `atr_14` 的值；没有则用证据包内日线（最多最近 14 根）的
        平均真实波幅；仍没有则为 None。
        """
        value = ((((self.technical or {}).get("single_indicator_results") or {}).get("atr_14") or {}).get("current_values") or {}).get("atr")
        if isinstance(value, (int, float)) and value > 0:
            return float(value)
        bars = [b for b in self.daily_bars if all(isinstance(b.get(k), (int, float)) for k in ("high", "low", "close"))]
        ranges = [max(b["high"] - b["low"], abs(b["high"] - p["close"]), abs(b["low"] - p["close"])) for p, b in zip(bars, bars[1:])][-14:]
        return sum(ranges) / len(ranges) if ranges else None

    @property
    def news_usable(self) -> bool:
        """
        True when a 新闻 payload exists and is not marked unusable upstream.

        存在新闻 payload 且上游未标记为不可用时为 True。
        """
        return bool(self.news) and bool(self.news.get("usable_by_downstream", True))

    def verdict_table(self) -> dict[str, str]:
        """
        The four sources' own one-line verdicts (for the report).

        四个来源各自的一行结论（用于报告）。
        """
        out: dict[str, str] = {}
        if self.technical:
            adv = (self.technical.get("cross_index_analysis") or {}).get("indicator_advice") or {}
            rule = (self.technical.get("cross_index_analysis") or {}).get("rule_evaluation") or {}
            out[TECHNICAL] = f"{adv.get('advice_type', '?')} ({adv.get('support_level', '?')}, rule score {_num(rule.get('support_score', '?'))})"
        if self.fundamental:
            fs = self.fundamental.get("fundamental_summary") or {}
            out[FUNDAMENTAL] = f"{fs.get('advice_type', '?')} (score {_num(fs.get('support_score', '?'))}, conf {_num(fs.get('confidence', '?'))})"
        if self.news_usable:
            ns = self.news.get("news_summary") or {}
            out[NEWS] = f"{ns.get('overall_direction', '?')} (conf {_num(ns.get('confidence', '?'))})"
        else:
            out[NEWS] = "unavailable"
        if self.research:
            out[RESEARCH] = f"{self.research.get('direction', '?')} (conf {_num(self.research.get('confidence_level', '?'))})"
        return out

    def coverage(self) -> list[dict[str, str]]:
        """
        One row per source (per factor for 基本面): `id`, `through` (what the
        data covers), `gap` (past dates it lacks relative to the last
        completed session, or "none") and `note`. This is the only basis on
        which a prompt may call data missing.

        每个来源一行（基本面按因子）：`id`、`through`（数据覆盖到哪）、`gap`（相对最后一个完整交易日
        缺哪些过去的日期，或 "none"）、`note`。提示词只能据此说数据缺失。
        """
        last = _day(self.last_session)
        rows: list[dict[str, str]] = []
        t = self.technical
        if t:
            dq = t.get("data_quality") or {}
            through = _day((t.get("latest_bar") or {}).get("trading_date")) or _day(dq.get("latest_bar_time"))
            rows.append({"id": TECHNICAL, "through": f"daily bar of {through}" if through else "unknown", "gap": _gap(through, last),
                         "note": f"{dq.get('bars_used', '?')} daily bars, status {dq.get('status', '?')}"})
        else:
            rows.append({"id": TECHNICAL, "through": "unavailable", "gap": "source absent", "note": ""})
        f = self.fundamental
        if f:
            dq = f.get("data_quality") or {}
            as_of = _day(f.get("as_of"))
            for name, st in (f.get("factor_states") or {}).items():
                through = _day(st.get("source_date"))
                if through is None and "source_date" not in st and as_of and st.get("freshness_days") is not None:
                    through = as_of - timedelta(days=int(st["freshness_days"]))
                rows.append({"id": f"{FUNDAMENTAL}.{name}", "through": through.isoformat() if through else "no data",
                             "gap": _gap(through, last) if through else "factor absent", "note": ""})
            if dq.get("warnings"):
                rows.append({"id": f"{FUNDAMENTAL} (upstream warnings)", "through": str(dq.get("latest_source_date") or "?"),
                             "gap": "see note", "note": "; ".join(str(w) for w in dq["warnings"])})
        else:
            rows.append({"id": FUNDAMENTAL, "through": "unavailable", "gap": "source absent", "note": ""})
        window = " → ".join(x for x in (_minute(self.timing.get("news_since")), _minute(self.timing.get("news_as_of"))) if x)
        n = self.news
        if self.news_usable:
            dq = n.get("data_quality") or {}
            used, total = dq.get("used_news_count"), dq.get("news_count")
            note = f"{used} of {total} items in the window concern this symbol, status {dq.get('status', '?')}"
            if dq.get("latest_news_time"):
                note += f", latest {_minute(dq.get('latest_news_time'))}"
            rows.append({"id": NEWS, "through": f"window {window}" if window else f"up to {_minute(n.get('as_of'))}",
                         "gap": "none" if used else "window covered, but no item concerns this symbol", "note": note})
        else:
            why = "; ".join(str(w) for w in ((n or {}).get("data_quality") or {}).get("errors") or []) or ("marked unusable upstream" if n else "no payload")
            rows.append({"id": NEWS, "through": "unavailable", "gap": f"no usable news for this symbol{f' in the window {window}' if window else ''}", "note": why})
        if self.research:
            as_of, back = _minute(self.timing.get("research_as_of")), self.timing.get("research_lookback_days")
            through = f"reports received in the {back} day(s) before {as_of}" if as_of and back else (f"reports up to {as_of}" if as_of else "as provided")
            rows.append({"id": RESEARCH, "through": through, "gap": "none", "note": f"status {self.research_status}" if self.research_status else ""})
        else:
            rows.append({"id": RESEARCH, "through": "unavailable", "gap": "source absent", "note": ""})
        return rows

    def render(self, level: str = "compact") -> str:
        """
        Markdown evidence block with the decision time, the 数据覆盖 table and
        stable ids; `full` appends raw JSON.

        带决策时点、数据覆盖表和稳定编号的 Markdown 证据块；`full` 附加原始 JSON。
        """
        L: list[str] = [f"# Evidence pack — {self.symbol} ({self.variety_name}, contract {self.contract_code})",
                        f"Decision time: before the open of trading day {self.pack_date}. Last completed session: {self.last_session}.", ""]
        if self.missing:
            L += [f"Missing or unusable sources: {', '.join(self.missing)}", ""]
        L += ["## 数据覆盖 — what each source covers as of the decision time", "id | data through | gap before the decision time | note"]
        L += [f"{r['id']} | {r['through']} | {r['gap']} | {r['note']}" for r in self.coverage()]
        L.append("")
        L += self._render_technical() + self._render_fundamental() + self._render_news() + self._render_research()
        if self.daily_bars:
            L.append(f"## {DAILY} — recent daily bars (main contract, newest last) — id {DAILY}")
            L.append("date | open | high | low | close | volume | open_interest")
            for b in self.daily_bars:
                L.append(f"{b.get('trading_date')} | {b.get('open')} | {b.get('high')} | {b.get('low')} | {b.get('close')} | {b.get('volume')} | {b.get('open_interest')}")
            L.append("")
        if level == "full":
            L.append("## Raw payloads")
            for tag, payload in ((TECHNICAL, self.technical), (FUNDAMENTAL, self.fundamental), (NEWS, self.news), (RESEARCH, self.research)):
                if payload:
                    L.append(f"### {tag} raw\n```json\n{json.dumps(payload, ensure_ascii=False)[:60000]}\n```")
        return _localize("\n".join(L))

    def _render_technical(self) -> list[str]:
        """
        技术指标: data quality, latest bar, each indicator's
        state/direction/score, rule evaluation, interpreter advice and the
        interpretation gap.

        技术指标：数据质量、最新 K 线、各指标状态/方向/分数、规则评估、解读建议与解读差异。
        """
        a = self.technical
        if not a:
            return [f"## {TECHNICAL}: not available", ""]
        dq = a.get("data_quality") or {}
        lb = a.get("latest_bar") or {}
        L = [f"## {TECHNICAL} — daily bars, deterministic calculators + rule layer + LLM interpreter",
             f"as_of {a.get('as_of')}; data_quality {dq.get('status')} (bars {dq.get('bars_used')}, roll_detected {dq.get('roll_detected')}, warnings {dq.get('warnings')})",
             f"latest bar {lb.get('trading_date')}: O {lb.get('open')} H {lb.get('high')} L {lb.get('low')} C {lb.get('close')} vol {lb.get('volume')} OI {lb.get('open_interest')}",
             "", "id | indicator | state | direction | score | strength | event | key values"]
        for name, r in (a.get("single_indicator_results") or {}).items():
            cv = r.get("current_values") or {}
            keyvals = ", ".join(f"{k}={v}" for k, v in list(cv.items())[:5])
            L.append(f"{TECHNICAL}.{name} | {name} | {r.get('state')} | {r.get('direction')} | {r.get('direction_score')} | {r.get('strength')} | {r.get('event')} ({r.get('bars_since_event')} bars ago) | {keyvals}")
        cx = a.get("cross_index_analysis") or {}
        rule = cx.get("rule_evaluation") or {}
        adv = cx.get("indicator_advice") or {}
        gap = cx.get("interpretation_gap") or {}
        L += ["", f"{TECHNICAL}.rule — rule layer: alignment {rule.get('alignment')}, support_score {rule.get('support_score')}, confidence {rule.get('confidence')}, conflicts {rule.get('conflicts')}, risk_flags {rule.get('risk_flags')}",
              f"{TECHNICAL}.advice — interpreter: {adv.get('advice_type')} / support {adv.get('support_level')} / alignment {adv.get('alignment')}: {adv.get('advice_summary')}",
              f"  main_support: {adv.get('main_support')}", f"  main_conflicts: {adv.get('main_conflicts')}",
              f"  confirmation_conditions: {adv.get('confirmation_conditions')}", f"  invalidation_conditions: {adv.get('invalidation_conditions')}",
              f"  limitations: {adv.get('limitations')}"]
        if gap.get("exists"):
            L.append(f"{TECHNICAL}.gap — rule layer vs interpreter disagree: rule says {(gap.get('rule_layer_view') or {}).get('message')!r}; interpreter says {(gap.get('interpreter_layer_view') or {}).get('message')!r}; downstream_resolution_needed={gap.get('downstream_resolution_needed')}")
        return L + [""]

    def _render_fundamental(self) -> list[str]:
        """
        基本面: the fundamental factors with direction/score/confidence/source
        date and the rule-generated summary.

        基本面：各基本面因子的方向/分数/置信度/数据日期及规则生成的总结。
        """
        a = self.fundamental
        if not a:
            return [f"## {FUNDAMENTAL}: not available", ""]
        dq = a.get("data_quality") or {}
        L = [f"## {FUNDAMENTAL} — fundamental factors (curve, inventory, basis, external parity, chain margin)",
             f"as_of {a.get('as_of')}; data_quality {dq.get('status')}; latest_source_date {dq.get('latest_source_date')}; warnings {dq.get('warnings')}",
             "", "id | factor | state | direction | score | confidence | source_date | summary"]
        for name, f in (a.get("factor_states") or {}).items():
            L.append(f"{FUNDAMENTAL}.{name} | {name} | {f.get('state')} | {f.get('direction')} | {f.get('direction_score')} | {f.get('confidence')} | {f.get('source_date')} | {f.get('summary')}")
            if f.get("limitations"):
                L.append(f"    limitations: {f.get('limitations')}")
        fs = a.get("fundamental_summary") or {}
        L += ["", f"{FUNDAMENTAL}.summary — {fs.get('advice_type')} / support {fs.get('support_level')} score {fs.get('support_score')} conf {fs.get('confidence')} alignment {fs.get('alignment')}",
              f"  bullish: {fs.get('bullish_factors')}; bearish: {fs.get('bearish_factors')}; neutral: {fs.get('neutral_factors')}",
              f"  summary_zh: {fs.get('summary')}", f"  supporting_points: {fs.get('supporting_points')}", f"  conflicts: {fs.get('conflicts')}",
              f"  risk_flags: {fs.get('risk_flags')}", f"  data_caveats: {fs.get('data_caveats')}", f"  requires_confirmation: {fs.get('requires_confirmation')}"]
        return L + [""]

    def _render_news(self) -> list[str]:
        """
        新闻: news summary and the used events with direction/horizon/relevance.

        新闻：新闻总结及使用的事件（方向/期限/相关度）。
        """
        a = self.news
        if not self.news_usable:
            return [f"## {NEWS}: not available or marked unusable for this symbol (treat news as unknown, not neutral)", ""]
        dq = a.get("data_quality") or {}
        ns = a.get("news_summary") or {}
        window = " → ".join(x for x in (_minute(self.timing.get("news_since")), _minute(self.timing.get("news_as_of") or a.get("as_of"))) if x)
        groups = " ".join(f"{label} {[_news_id(i) for i in ns.get(key) or []]}" for label, key in (
            ("bullish", "bullish_event_ids"), ("bearish", "bearish_event_ids"), ("two_sided", "two_sided_event_ids"), ("short_term", "short_term_relevant_event_ids")))
        L = [f"## {NEWS} — Jin10 news, window {window}",
             f"as_of {a.get('as_of')}; data_quality {dq.get('status')} (news {dq.get('news_count')}, used {dq.get('used_news_count')}, latest {dq.get('latest_news_time')})",
             f"{NEWS}.summary — overall_direction {ns.get('overall_direction')} conf {ns.get('confidence')}: {ns.get('summary')}",
             f"  {groups}; risk_flags {ns.get('risk_flags')}",
             "", "id | time | direction | horizon | relevance | conf | title"]
        for e in a.get("news_events") or []:
            L.append(f"{_news_id(e.get('event_id'))} | {str(e.get('published_at'))[:16]} | {e.get('direction')} | {e.get('horizon')} | {e.get('relevance_to_symbol')} | {e.get('confidence')} | {str(e.get('title'))[:140]}")
        return L + [""]

    def _render_research(self) -> list[str]:
        """
        研报: research-report direction with evidence sentences and, if
        available, the SHORT/MEDIUM/LONG horizon views.

        研报：研报方向及证据句，若有则附短/中/长期视角。
        """
        a = self.research
        if not a:
            return [f"## {RESEARCH}: not available", ""]
        L = [f"## {RESEARCH} — research reports (email/PDF retrieval + verified analysis)",
             f"{RESEARCH}.summary — direction {a.get('direction')} confidence {a.get('confidence_level')}: {a.get('summary')}", ""]
        for i, ev in enumerate(a.get("evidence") or [], 1):
            text = ev if isinstance(ev, str) else json.dumps(ev, ensure_ascii=False)
            L.append(f"{RESEARCH}.ev{i} | {str(text)[:400]}")
        for h in self.research_horizons:
            L.append(f"{RESEARCH}.{str(h.get('horizon', '')).lower()} | horizon {h.get('horizon')}: {h.get('direction')} score {h.get('directional_score')} conf {h.get('confidence')} verified={h.get('verified', h.get('passed'))}: {str(h.get('thesis') or h.get('summary') or '')[:300]}")
        return L + [""]


def _last_session(pack_date: str, *candidates: object) -> str:
    """
    The last completed session before the pack date: the first candidate
    timestamp that falls before it, else the previous weekday.

    包日期之前最后一个完整交易日：取第一个早于包日期的候选时间，否则取上一个工作日。
    """
    day = _day(pack_date)
    for c in candidates:
        d = _day(c)
        if d and (day is None or d < day):
            return d.isoformat()
    if day is None:
        return ""
    prev = day - timedelta(days=1)
    while prev.weekday() >= 5:
        prev -= timedelta(days=1)
    return prev.isoformat()


def load_pack(pack_dir: Path, symbols: Optional[list[str]] = None, bars_tail: int = 20) -> dict[str, Evidence]:
    """
    Load every symbol in the pack (or the given subset) into Evidence objects.

    把证据包中的每个品种（或指定子集）加载为 Evidence 对象。
    """
    pack_dir = Path(pack_dir)
    manifest = _load(pack_dir / "manifest.json") or {}
    pack_date = manifest.get("trade_date") or pack_dir.name
    agents = manifest.get("agents") or {}
    run = {label: agents.get(code) or {} for label, (code, _) in SOURCES.items()}
    technical_as_of = (manifest.get("as_of") or {}).get(SOURCES[TECHNICAL][0].lower()) or run[TECHNICAL].get("as_of")
    timing = {"news_since": run[NEWS].get("since"), "news_as_of": run[NEWS].get("as_of"),
              "research_as_of": run[RESEARCH].get("as_of"), "research_lookback_days": run[RESEARCH].get("lookback_days")}
    all_syms = list(manifest.get("symbols") or [])
    bars_root = (pack_dir / BARS_PATH).parents[1]
    if not all_syms and bars_root.exists():
        all_syms = sorted(p.name for p in bars_root.iterdir() if p.is_dir())
    wanted = [s.upper() for s in symbols] if symbols else all_syms
    research = _load(pack_dir / RESEARCH_FULL_PATH) or {}
    horizons_by_sym: dict[str, list[dict]] = {}
    status_by_sym: dict[str, str] = {}
    for c in research.get("commodities") or []:
        sym = (c.get("symbol") or c.get("code") or "").upper()
        views = ((c.get("draft") or {}).get("horizon_views")) or []
        if sym and views:
            horizons_by_sym[sym] = views
        if sym and c.get("status"):
            status_by_sym[sym] = str(c["status"])
    out: dict[str, Evidence] = {}
    for s in wanted:
        ev = Evidence(symbol=s, pack_date=pack_date, timing=dict(timing))
        payloads = {label: _load(pack_dir / path.format(symbol=s)) for label, (_, path) in SOURCES.items()}
        ev.technical, ev.fundamental, ev.news, ev.research = (payloads[k] for k in (TECHNICAL, FUNDAMENTAL, NEWS, RESEARCH))
        ev.missing = [label for label in SOURCES if payloads[label] is None or (label == NEWS and not ev.news_usable)]
        ev.last_session = _last_session(pack_date, technical_as_of, (ev.technical or {}).get("as_of"))
        if not ev.timing.get("news_as_of"):
            ev.timing["news_as_of"] = (ev.news or {}).get("as_of")
        ev.research_horizons = horizons_by_sym.get(s, [])
        ev.research_status = status_by_sym.get(s, "")
        bars = (_load(pack_dir / BARS_PATH.format(symbol=s)) or {}).get("bars") or []
        ev.daily_bars = [{"trading_date": b.get("trading_date"), "open": b.get("open"), "high": b.get("high"), "low": b.get("low"),
                          "close": b.get("close"), "volume": b.get("volume"), "open_interest": b.get("open_interest")} for b in bars[-bars_tail:]]
        out[s] = ev
    return out
