"""
Agents: read the English part only. 中文仅供人类阅读。

debate.py — the LLM decision layer: opening statements → a multi-round
debate → manager, one symbol at a time.

`judge_symbol(evidence, position, cfg, params)` runs the structured calls
through `claude_cli.run_claude` and validates each with the pydantic models
in `schemas.py`:

1. Opening (立论): the long side (多方) and the short side (空方) each write a
   `Thesis`. Every key point becomes a thread, numbered 多1… / 空1….
2. Rounds (`run_debate`): in each round the other side rebuts every thread
   in play (反驳: counterexample, limitation, insufficient support, missing
   or unclear causality, data issue), then the owner answers each rebuttal
   (再反驳: maintain, narrow or concede). A conceded point or a withdrawn
   objection closes the thread. After a round the moderator (主持人) decides
   whether another round is worth holding and says why; the code stops the
   debate itself when no thread is contested or `max_debate_rounds` is
   reached.
3. Manager: rules on every thread and returns the `Decision` (callback CB01
   major_timeframe_direction; with a position also CB05
   major_trend_reversal). The reversal flag is recomputed in code from the
   manager's direction and confidence so the rule in T021 cannot be bent by
   prose.

Every prompt carries the decision-time block of `prompts/_time_anchor.md`
(the judgement stands at the open of the pack date). Every step's prompt,
raw response and cost are written under `runs/<pack_date>/<symbol>/`, and a
finished decision is cached there keyed by pack date, symbol, prompt
version, model settings and position state so reruns are free. `judge_many`
fans out over symbols with a thread pool; within a symbol the two sides of a
step run concurrently.

debate.py 是 LLM 决策层：立论 → 多轮辩论 → Manager，逐个品种执行。`judge_symbol(evidence, position,
cfg, params)` 通过 `claude_cli.run_claude` 做结构化调用，每次用 `schemas.py` 的 pydantic 模型校验：
（1）立论：多方和空方各写一份 `Thesis`，每条论据成为一个线程，编号 多1… / 空1…。（2）多轮辩论
（`run_debate`）：每轮先由对方逐条反驳仍在辩的线程（举反例、局限性、论证不充分、无因果或因果不明、
数据问题），再由论据所有方逐条再反驳（坚持、收窄或认输）；认输或撤回异议即关闭线程。每轮结束后由
主持人判断是否值得再打一轮并给出理由；已无争议论据或达到 `max_debate_rounds` 时由代码直接终止。
（3）Manager：对每个线程给出裁定并返回 `Decision`（回调 CB01 大周期方向判定；有持仓时也是 CB05
趋势反转）。反转标志由代码根据 Manager 的方向和置信度重算，T021 的规则不会被文字绕过。每个提示词都
带 `prompts/_time_anchor.md` 的决策时点段落（判断站在包日期开盘前）。每一步的提示词、原始响应和费用
写到 `runs/<包日期>/<品种>/`，完成的决策按包日期、品种、提示词版本、模型设置和持仓状态缓存，重跑
不花钱。`judge_many` 用线程池并行多个品种；同一品种内，一步里的多空两侧并行调用。
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, Optional

from .claude_cli import run_claude
from .config import PROMPT_VERSION, PROMPTS_DIR, JudgeConfig, ResonanceParams
from .evidence import Evidence
from .schemas import (Debate, DebateThread, Decision, DefenceTurn, Exchange, ModeratorRuling, PointVerdict, Position,
                      RebuttalTurn, RoundRuling, Thesis, json_schema_for)

SIDES = ("long", "short")
SIDE_ZH = {"long": "多方", "short": "空方"}
POINT_PREFIX = {"long": "多", "short": "空"}
ATTACK_ZH = {"counterexample": "举反例", "limitation": "局限性", "insufficient_support": "论证不充分",
             "causality": "无因果或因果不明", "data_issue": "数据问题", "other": "其他"}
STANCE_ZH = {"maintain": "坚持", "narrow": "收窄", "concede": "认输"}
STATUS_ZH = {"contested": "争议中", "conceded": "所有方认输", "objection_withdrawn": "对方撤回异议"}
STRENGTH_ZH = {"weak": "弱", "moderate": "中", "strong": "强"}
VERDICT_ZH = {"stands": "成立", "weakened": "被削弱", "refuted": "被驳倒"}


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
    debate: Optional[Debate] = None
    cost_usd: float = 0.0
    duration_s: float = 0.0
    cached: bool = False
    error: Optional[str] = None
    verdicts: dict[str, str] = field(default_factory=dict)


def other(side: str) -> str:
    """
    The opposing side.

    对方。
    """
    return "short" if side == "long" else "long"


def _prompt(name: str) -> str:
    """
    Read a prompt template from prompts/.

    从 prompts/ 读取提示词模板。
    """
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def _fill(template: str, **kw: str) -> str:
    """
    Substitute `{name}` placeholders in one pass: other braces are left alone
    (the evidence contains JSON) and substituted text is never rescanned
    (debate speeches are embedded in later prompts).

    一次性替换 `{name}` 占位符：不碰其他花括号（证据中含 JSON），替换进去的文本也不会被再次扫描
    （辩论发言会嵌入后续提示词）。
    """
    return re.sub(r"\{([a-z_]+)\}", lambda m: kw[m.group(1)] if m.group(1) in kw else m.group(0), template)


def render_exchange(x: Exchange) -> str:
    """
    One speech as a Markdown bullet.

    把一次发言渲染成一条 Markdown 列表项。
    """
    who, what = SIDE_ZH[x.speaker], "反驳" if x.kind == "rebuttal" else "再反驳"
    if x.unanswered:
        return f"- 第{x.round}轮 {who}{what}：（未回应）"
    tag = ("撤回异议" if x.withdrawn else ATTACK_ZH.get(x.attack_type, "其他")) if x.kind == "rebuttal" else STANCE_ZH.get(x.stance, "坚持")
    line = f"- 第{x.round}轮 {who}{what}〔{tag}〕：{x.argument}"
    if x.evidence_refs:
        line += f"（证据：{', '.join(x.evidence_refs)}）"
    if x.revised_claim:
        line += f"\n  - 收窄后的论据：{x.revised_claim}"
    return line


def render_thread(t: DebateThread, verdict: Optional[PointVerdict] = None) -> str:
    """
    One thread as a Markdown list under its heading: the point, the
    exchanges in order and, if given, the manager's ruling.

    一个线程，渲染为标题下的 Markdown 列表：论据、按顺序的交锋，以及（若给出）Manager 的裁定。
    """
    L = [f"### {t.point_id}（{SIDE_ZH[t.owner]}，强度 {STRENGTH_ZH[t.strength]}，{STATUS_ZH[t.status]}）",
         f"- 论据：{t.claim}", f"- 推理：{t.reasoning}", f"- 证据：{', '.join(t.evidence_refs) or '无'}"]
    L += [render_exchange(x) for x in t.exchanges]
    if verdict:
        L += ["", f"**裁定：{VERDICT_ZH[verdict.verdict]}。**{verdict.reason}"]
    return "\n".join(L)


def render_threads(threads: list[DebateThread], verdicts: Optional[dict[str, PointVerdict]] = None) -> str:
    """
    Several threads, blank-line separated ("（无）" when there are none).

    多个线程，以空行分隔（没有时为 "（无）"）。
    """
    return "\n\n".join(render_thread(t, (verdicts or {}).get(t.point_id)) for t in threads) or "（无）"


def render_rulings(debate: Debate) -> str:
    """
    Why the debate continued or stopped after each round.

    每轮之后辩论继续或终止的理由。
    """
    lines = []
    for r in debate.rulings:
        line = f"- 第{r.round}轮后，{'主持人' if r.decided_by == 'moderator' else '规则'}：{'继续' if r.continue_debate else '终止'}。{r.reason}"
        if r.focus_point_ids:
            line += f"（下一轮聚焦：{', '.join(r.focus_point_ids)}）"
        lines.append(line)
    return "\n".join(lines) or "- 没有进行辩论（双方均未提出论据）。"


def render_opening(thesis: Thesis, points: bool = False) -> str:
    """
    An opening statement: thesis, self-assessed confidence and falsifiers;
    with `points`, also the numbered claims.

    立论：总论点、自评置信度和证伪条件；`points` 为真时附带编号的论据。
    """
    L = [f"立论：{thesis.thesis}", f"自评置信度：{thesis.confidence}", f"证伪条件：{'；'.join(thesis.falsifiers) or '无'}"]
    if points:
        L += [f"{POINT_PREFIX[thesis.stance]}{i}：{p.claim}" for i, p in enumerate(thesis.key_points, 1)]
    return "\n".join(L)


def build_threads(theses: dict[str, Thesis]) -> list[DebateThread]:
    """
    One thread per key point, numbered per side in the order given
    (多1, 多2, …, 空1, …).

    每条论据一个线程，按给出的顺序分方编号（多1、多2、…、空1、…）。
    """
    return [DebateThread(point_id=f"{POINT_PREFIX[side]}{i}", owner=side, claim=p.claim, reasoning=p.reasoning,
                         evidence_refs=p.evidence_refs, strength=p.strength)
            for side in SIDES for i, p in enumerate(theses[side].key_points, 1)]


def run_debate(theses: dict[str, Thesis], max_rounds: int, moderator_effort: str, call: Callable, both: Callable) -> Debate:
    """
    Hold the rounds. `call(record_name, template, kw, model_cls, effort)`
    runs one structured call; `both(jobs)` runs the two sides' calls of one
    step. Stops when the moderator says so, when no thread is contested, or
    after `max_rounds`; the reason is recorded in `Debate.rulings`.

    进行多轮辩论。`call(record_name, template, kw, model_cls, effort)` 执行一次结构化调用；
    `both(jobs)` 执行一步里两侧的调用。主持人判定终止、已无争议线程、或达到 `max_rounds` 时停止；
    理由记录在 `Debate.rulings`。
    """
    debate = Debate(threads=build_threads(theses))
    focus: Optional[set[str]] = None
    for r in range(1, max_rounds + 1):
        in_play = [t for t in debate.threads if t.status == "contested" and (focus is None or t.point_id in focus)]
        if not in_play:
            break
        note = ("This is the first exchange: each thread shows only the opening argument." if r == 1 else
                "Each thread already holds earlier rebuttals and the other side's latest 再反驳. Answer that latest 再反驳 (and the narrowed claim, "
                "if one was given): bring a new objection or new evidence and do not repeat an attack already made. If the 再反驳 settles your "
                "objection, set `withdrawn` = true.")
        attackers = [s for s in SIDES if any(t.owner == other(s) for t in in_play)]
        turns = both([(f"debate_r{r}_rebuttal_{s}", "debate_rebuttal",
                       {"side_zh": SIDE_ZH[s], "opponent_zh": SIDE_ZH[other(s)], "stance": s, "round": str(r), "round_note": note,
                        "own_opening": render_opening(theses[s], points=True),
                        "targets": render_threads([t for t in in_play if t.owner == other(s)])}, RebuttalTurn, None) for s in attackers])
        for s, turn in zip(attackers, turns):
            said = {x.point_id: x for x in turn.rebuttals}
            for t in (t for t in in_play if t.owner == other(s)):
                x = said.get(t.point_id)
                if x is None:
                    t.exchanges.append(Exchange(round=r, speaker=s, kind="rebuttal", argument="", unanswered=True))
                    continue
                t.exchanges.append(Exchange(round=r, speaker=s, kind="rebuttal", argument=x.argument, evidence_refs=x.evidence_refs,
                                            attack_type=x.attack_type, withdrawn=x.withdrawn))
                if x.withdrawn:
                    t.status = "objection_withdrawn"
        to_answer = [t for t in in_play if t.status == "contested" and not t.exchanges[-1].unanswered]
        defenders = [s for s in SIDES if any(t.owner == s for t in to_answer)]
        turns = both([(f"debate_r{r}_defence_{s}", "debate_defence",
                       {"side_zh": SIDE_ZH[s], "opponent_zh": SIDE_ZH[other(s)], "stance": s, "round": str(r),
                        "targets": render_threads([t for t in to_answer if t.owner == s])}, DefenceTurn, None) for s in defenders])
        for s, turn in zip(defenders, turns):
            said = {x.point_id: x for x in turn.defences}
            for t in (t for t in to_answer if t.owner == s):
                x = said.get(t.point_id)
                if x is None:
                    t.exchanges.append(Exchange(round=r, speaker=s, kind="defence", argument="", unanswered=True))
                    continue
                t.exchanges.append(Exchange(round=r, speaker=s, kind="defence", argument=x.argument, evidence_refs=x.evidence_refs,
                                            stance=x.stance, revised_claim=x.revised_claim if x.stance == "narrow" else None))
                if x.stance == "concede":
                    t.status = "conceded"
        debate.rounds_held = r
        contested = [t.point_id for t in debate.threads if t.status == "contested"]
        if not contested:
            ruling = RoundRuling(round=r, continue_debate=False, decided_by="rule", reason="已无争议论据：全部论据已认输或异议已撤回。")
        elif r == max_rounds:
            ruling = RoundRuling(round=r, continue_debate=False, decided_by="rule", reason=f"已达到 {max_rounds} 轮上限。")
        else:
            m: ModeratorRuling = call(f"debate_r{r}_moderator", "debate_moderator",
                                      {"round": str(r), "max_rounds": str(max_rounds), "open_ids": ", ".join(contested),
                                       "transcript": render_threads(debate.threads)}, ModeratorRuling, moderator_effort)
            keep = [p for p in m.focus_point_ids if p in contested] or contested
            ruling = RoundRuling(round=r, continue_debate=m.continue_debate, decided_by="moderator", reason=m.reason,
                                 focus_point_ids=keep if m.continue_debate else [])
        debate.rulings.append(ruling)
        if not ruling.continue_debate:
            break
        focus = set(ruling.focus_point_ids)
    return debate


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
    raw = (f"{evidence.pack_date}|{evidence.symbol}|{PROMPT_VERSION}|{cfg.model}|{cfg.effort}|{cfg.evidence_level}|"
           f"{cfg.max_debate_rounds}|{cfg.moderator_effort}|{pos}")
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def judge_symbol(evidence: Evidence, position: Optional[Position], cfg: JudgeConfig, params: ResonanceParams,
                 runner: Optional[Callable] = None) -> JudgeOutcome:
    """
    Run the opening statements, the debate and the manager for one symbol
    and return the outcome. `runner` is passed to run_claude (tests inject a
    scripted subprocess).

    对一个品种执行立论、辩论和 Manager 裁决并返回结果。`runner` 透传给 run_claude（测试注入脚本化
    子进程）。
    """
    t0 = time.perf_counter()
    rec = cfg.runs_dir / evidence.pack_date / evidence.symbol
    cache_file = rec / f"decision.{cache_key(evidence, position, cfg)}.json"
    if cfg.use_cache and cache_file.exists():
        d = json.loads(cache_file.read_text(encoding="utf-8"))
        return JudgeOutcome(symbol=evidence.symbol, decision=Decision(**d["decision"]), long_thesis=Thesis(**d["long_thesis"]),
                            short_thesis=Thesis(**d["short_thesis"]), debate=Debate(**d["debate"]),
                            cost_usd=d.get("cost_usd", 0.0), cached=True, verdicts=evidence.verdict_table())
    common = dict(symbol=evidence.symbol, variety_name=evidence.variety_name, pack_date=evidence.pack_date,
                  definitions=_prompt("_definitions"), evidence=evidence.render(cfg.evidence_level),
                  time_anchor=_fill(_prompt("_time_anchor"), pack_date=evidence.pack_date, last_session=evidence.last_session))
    costs: list[float] = []

    def call(record_name: str, template: str, kw: dict, model_cls, effort: Optional[str] = None):
        """Run one structured step and record its cost.

        执行一次结构化调用并记录成本。
        """
        res = run_claude(_fill(_prompt(template), **common, **kw), json_schema_for(model_cls), model=cfg.model, effort=effort or cfg.effort,
                         timeout_s=cfg.timeout_s, retries=cfg.retries, record_dir=rec, record_name=record_name, runner=runner)
        costs.append(res.cost_usd)
        return model_cls(**res.output)

    def both(jobs: list[tuple]) -> list:
        """Run the calls of one step, concurrently when configured.

        执行一步里的各个调用，按配置并行。
        """
        if cfg.parallel_sides and len(jobs) > 1:
            with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
                return list(pool.map(lambda j: call(*j), jobs))
        return [call(*j) for j in jobs]

    long_t, short_t = both([("long_thesis", "long_thesis", {}, Thesis, None), ("short_thesis", "short_thesis", {}, Thesis, None)])
    long_t.stance, short_t.stance = "long", "short"
    debate = run_debate({"long": long_t, "short": short_t}, cfg.max_debate_rounds, cfg.moderator_effort, call, both)
    if position is None:
        pos_clause = ("No position is open in this symbol. Set `reversal` to null; it is not applicable.")
    else:
        pos_clause = (f"An open {position.direction.upper()} position of {position.volume} lots (entry {position.entry_price}) exists. "
                      "Set `reversal` = true only if your direction is the opposite of the position, or your direction is "
                      "uncertain with uncertain_is_high_confidence = true (T021). Otherwise false.")
    dec = call("manager", "manager", {"long_opening": render_opening(long_t), "short_opening": render_opening(short_t),
                                      "transcript": render_threads(debate.threads), "rulings": render_rulings(debate),
                                      "position_clause": pos_clause}, Decision)
    dec.symbol = evidence.symbol
    known = {t.point_id for t in debate.threads}
    dec.point_verdicts = [v for v in dec.point_verdicts if v.point_id in known]
    dec = apply_reversal_rule(dec, position, params)
    out = JudgeOutcome(symbol=evidence.symbol, decision=dec, long_thesis=long_t, short_thesis=short_t, debate=debate,
                       cost_usd=sum(costs), duration_s=time.perf_counter() - t0, verdicts=evidence.verdict_table())
    rec.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps({"decision": dec.model_dump(), "long_thesis": long_t.model_dump(), "short_thesis": short_t.model_dump(),
                                      "debate": debate.model_dump(), "cost_usd": out.cost_usd, "position": position.model_dump() if position else None,
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
