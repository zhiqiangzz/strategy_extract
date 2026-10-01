"""
Agents: read the English part only. 中文仅供人类阅读。

debate.py — the LLM decision layer: Long Thesis → Short Thesis →
Cross-Examination → Manager, one symbol at a time.

`judge_symbol(evidence, position, cfg, params)` runs the four structured
calls through `claude_cli.run_claude`, validates each with the pydantic
models in `schemas.py`, and returns a `Decision` (callback CB01
major_timeframe_direction; with a position also CB05 major_trend_reversal).
The reversal flag is recomputed in code from the manager's direction and
confidence so the rule in T021 cannot be bent by prose. Every step's prompt,
raw response and cost are written under `runs/<pack_date>/<symbol>/`, and a
finished decision is cached there keyed by pack date, symbol, prompt version
and position state so reruns are free. `judge_many` fans out over symbols
with a thread pool.

debate.py 是 LLM 决策层：多头论证 → 空头论证 → 交叉质证 → Manager，逐个品种执行。
`judge_symbol(evidence, position, cfg, params)` 通过 `claude_cli.run_claude` 做四次结构化调用，
每次用 `schemas.py` 的 pydantic 模型校验，返回 `Decision`（回调 CB01 大周期方向判定；有持仓时
也是 CB05 趋势反转）。反转标志由代码根据 Manager 的方向和置信度重算，T021 的规则不会被文字
绕过。每一步的提示词、原始响应和费用写到 `runs/<包日期>/<品种>/`，完成的决策按包日期、品种、
提示词版本和持仓状态缓存，重跑不花钱。`judge_many` 用线程池并行多个品种。
"""
from __future__ import annotations

import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .claude_cli import ClaudeResult, run_claude
from .config import PROMPT_VERSION, PROMPTS_DIR, JudgeConfig, ResonanceParams
from .evidence import Evidence
from .schemas import CrossExam, Decision, Position, Thesis, json_schema_for


@dataclass
class JudgeOutcome:
    """
    Decision plus the intermediate artefacts and cost of one symbol.

    一个品种的决策、中间产物和费用。
    """
    symbol: str
    decision: Decision
    long_thesis: Optional[Thesis] = None
    short_thesis: Optional[Thesis] = None
    cross_exam: Optional[CrossExam] = None
    cost_usd: float = 0.0
    duration_s: float = 0.0
    cached: bool = False
    error: Optional[str] = None
    verdicts: dict[str, str] = field(default_factory=dict)


def _prompt(name: str) -> str:
    """
    Read a prompt template from prompts/.

    从 prompts/ 读取提示词模板。
    """
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def _fill(template: str, **kw: str) -> str:
    """
    Substitute `{name}` placeholders without touching other braces (the
    evidence contains JSON).

    替换 `{name}` 占位符而不碰其他花括号（证据中含 JSON）。
    """
    out = template
    for k, v in kw.items():
        out = out.replace("{" + k + "}", v)
    return out


def apply_reversal_rule(decision: Decision, position: Optional[Position], params: ResonanceParams) -> Decision:
    """
    Recompute `reversal` from T021: with a position, reversal is true if the
    direction is the opposite of the position, or if the direction is
    uncertain with high confidence (the manager's flag or confidence ≥
    threshold). Without a position reversal is None.

    按 T021 重算 `reversal`：有持仓时，方向与持仓相反、或方向为高置信度不确定（Manager 的标志
    或置信度 ≥ 阈值）则为 true；无持仓则为 None。
    """
    if position is None:
        decision.reversal = None
        return decision
    opposite = decision.direction in ("long", "short") and decision.direction != position.direction
    high_unc = decision.direction == "uncertain" and (
        decision.uncertain_is_high_confidence or decision.confidence >= params.reversal_uncertain_conf_threshold)
    decision.reversal = bool(opposite or high_unc)
    return decision


def cache_key(evidence: Evidence, position: Optional[Position], cfg: JudgeConfig) -> str:
    """
    Stable key for the decision cache.

    决策缓存的稳定键。
    """
    pos = f"{position.direction}:{position.volume}" if position else "flat"
    raw = f"{evidence.pack_date}|{evidence.symbol}|{PROMPT_VERSION}|{cfg.model}|{cfg.effort}|{cfg.evidence_level}|{pos}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def judge_symbol(evidence: Evidence, position: Optional[Position], cfg: JudgeConfig, params: ResonanceParams,
                 runner: Optional[Callable] = None) -> JudgeOutcome:
    """
    Run the four-step debate for one symbol and return the outcome. `runner`
    is passed to run_claude (tests inject a scripted subprocess).

    对一个品种执行四步辩论并返回结果。`runner` 透传给 run_claude（测试注入脚本化子进程）。
    """
    t0 = time.perf_counter()
    rec = cfg.runs_dir / evidence.pack_date / evidence.symbol
    key = cache_key(evidence, position, cfg)
    cache_file = rec / f"decision.{key}.json"
    if cfg.use_cache and cache_file.exists():
        d = json.loads(cache_file.read_text(encoding="utf-8"))
        return JudgeOutcome(symbol=evidence.symbol, decision=Decision(**d["decision"]),
                           long_thesis=Thesis(**d["long_thesis"]) if d.get("long_thesis") else None,
                           short_thesis=Thesis(**d["short_thesis"]) if d.get("short_thesis") else None,
                           cross_exam=CrossExam(**d["cross_exam"]) if d.get("cross_exam") else None,
                           cost_usd=d.get("cost_usd", 0.0), cached=True, verdicts=evidence.verdict_table())
    definitions = _prompt("_definitions")
    ev_text = evidence.render(cfg.evidence_level)
    common = dict(symbol=evidence.symbol, variety_name=evidence.variety_name, definitions=definitions, evidence=ev_text)
    cost = 0.0

    def call(name: str, template_kw: dict, model_cls):
        """Run one debate step and accumulate its cost.

        执行一次辩论步骤并累加成本。
        """
        nonlocal cost
        prompt = _fill(_prompt(name), **common, **template_kw)
        res: ClaudeResult = run_claude(prompt, json_schema_for(model_cls), model=cfg.model, effort=cfg.effort,
                                       timeout_s=cfg.timeout_s, retries=cfg.retries, record_dir=rec, record_name=name,
                                       runner=runner)
        cost += res.cost_usd
        return model_cls(**res.output)

    long_t = call("long_thesis", {}, Thesis)
    short_t = call("short_thesis", {}, Thesis)
    cx = call("cross_exam", {"long_thesis": long_t.model_dump_json(indent=1), "short_thesis": short_t.model_dump_json(indent=1)}, CrossExam)
    if position is None:
        pos_clause = ("No position is open in this symbol. Set `reversal` to null; it is not applicable.")
    else:
        pos_clause = (f"An open {position.direction.upper()} position of {position.volume} lots (entry {position.entry_price}) exists. "
                      "Set `reversal` = true only if your direction is the opposite of the position, or your direction is "
                      "uncertain with uncertain_is_high_confidence = true (T021). Otherwise false.")
    verdicts = "\n".join(f"- {k}: {v}" for k, v in evidence.verdict_table().items())
    dec = call("manager", {"long_thesis": long_t.model_dump_json(indent=1), "short_thesis": short_t.model_dump_json(indent=1),
                           "cross_exam": cx.model_dump_json(indent=1), "position_clause": pos_clause, "verdicts": verdicts}, Decision)
    dec.symbol = evidence.symbol
    dec = apply_reversal_rule(dec, position, params)
    out = JudgeOutcome(symbol=evidence.symbol, decision=dec, long_thesis=long_t, short_thesis=short_t, cross_exam=cx,
                       cost_usd=cost, duration_s=time.perf_counter() - t0, verdicts=evidence.verdict_table())
    rec.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps({"decision": dec.model_dump(), "long_thesis": long_t.model_dump(), "short_thesis": short_t.model_dump(),
                                      "cross_exam": cx.model_dump(), "cost_usd": cost, "position": position.model_dump() if position else None,
                                      "prompt_version": PROMPT_VERSION, "model": cfg.model, "effort": cfg.effort},
                                     ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def judge_many(evidences: dict[str, Evidence], positions: dict[str, Position], cfg: JudgeConfig, params: ResonanceParams,
               runner: Optional[Callable] = None, on_done: Optional[Callable[[JudgeOutcome], None]] = None) -> dict[str, JudgeOutcome]:
    """
    Judge several symbols in parallel; a failed symbol yields an outcome
    with direction `uncertain`, evidence_quality `poor` and `error` set, so
    one failure never blocks the run.

    并行判断多个品种；失败的品种返回 direction 为 uncertain、evidence_quality 为 poor 且带
    `error` 的结果，单个失败不阻塞整次运行。
    """
    out: dict[str, JudgeOutcome] = {}
    with ThreadPoolExecutor(max_workers=cfg.max_workers) as pool:
        futs = {pool.submit(judge_symbol, ev, positions.get(sym), cfg, params, runner): sym for sym, ev in evidences.items()}
        for fut in as_completed(futs):
            sym = futs[fut]
            try:
                res = fut.result()
            except Exception as exc:  # noqa: BLE001 - reported per symbol
                res = JudgeOutcome(symbol=sym, decision=Decision(symbol=sym, direction="uncertain", confidence=0.0, reasoning=f"judge failed: {exc}",
                                                                 key_drivers=[], evidence_quality="poor"), error=str(exc),
                                   verdicts=evidences[sym].verdict_table())
            out[sym] = res
            if on_done:
                on_done(res)
    return out
