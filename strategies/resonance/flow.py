"""
Agents: read the English part only. 中文仅供人类阅读。

flow.py — the data file a web page fills its template with: one symbol's
judgement from the first call to the decision.

After every run the judge writes `runs/<pack_date>/<symbol>/flow.json`
(`build_flow` / `write_flows`) and refreshes `runs/index.json`
(`write_index`), the list of pack dates and symbols a page can offer. The
page template in `web/` holds no data of its own; it reads these two files.
`FLOW_SCHEMA` is the version of the contract, and `web/src/types.ts` is its
TypeScript mirror: change them together.

A flow holds: the decision and how the debate ended; the model calls in
order (`steps`), each with who spoke, which prompt template it used, when it
ran, what it cost, what its prompt was made of (`blocks`, the top-level
sections of the recorded prompt with their sizes), a summary of what came
back, and what the code did before the next call (`glue`); and the debate
threads with every exchange and the manager's ruling. Which calls happened
is derived from the debate record; their timing, cost and prompt come from
the per-call records `<step>.response.json` / `<step>.prompt.md`. A step
whose records are gone (another machine, a cleaned directory) keeps its
place in the sequence with the timing fields set to null.

flow.py 生成网页模板要填充的数据文件：一个品种从第一次调用到决策的全过程。每次运行后，判断层写出
`runs/<包日期>/<品种>/flow.json`（`build_flow` / `write_flows`），并刷新 `runs/index.json`
（`write_index`，页面可选的包日期与品种列表）。`web/` 里的页面模板本身不含数据，只读这两个文件。
`FLOW_SCHEMA` 是数据约定的版本号，`web/src/types.ts` 是它的 TypeScript 对应，二者须同步修改。
一份 flow 包含：决策及辩论如何结束；按顺序排列的模型调用（`steps`），每次调用有谁在发言、用了哪个
提示词模板、何时执行、花费多少、提示词由哪些部分组成（`blocks`，留痕提示词的各顶层段落及其大小）、
返回结果的摘要，以及下一次调用之前代码做了什么（`glue`）；还有各辩论线程的全部交锋和 Manager 的
裁定。发生过哪些调用由辩论记录推出；时间、费用和提示词取自逐次调用的留痕文件
`<步骤>.response.json` / `<步骤>.prompt.md`。留痕文件不在（换了机器、目录被清理）的步骤仍保留在
序列里，时间相关字段为 null。
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .debate import (ATTACK_ZH, POINT_PREFIX, SIDE_ZH, SIDES, STANCE_ZH, STATUS_ZH, STRENGTH_ZH, VERDICT_ZH, JudgeOutcome, other)
from .schemas import Debate, Position

FLOW_SCHEMA = 1
PHASE_ZH = {"thesis": "立论", "rebuttal": "反驳", "defence": "再反驳", "moderator": "主持人", "manager": "Manager"}
ROLE_ZH = {**SIDE_ZH, "mod": "主持人", "mgr": "Manager"}
TEMPLATE = {"rebuttal": "debate_rebuttal.md", "defence": "debate_defence.md", "moderator": "debate_moderator.md", "manager": "manager.md"}

# heading of a top-level prompt section -> (label, what it holds); order as in the templates
# 提示词顶层段落的标题 -> （名称，内容）；顺序同模板
_BLOCKS = [
    (r"## Decision time", "决策时点", "站在包日期开盘前；此后的数据是被判断的未来，不是缺失"),
    (r"## Strategy definitions", "策略定义", "T011 / T005 / T021 / T010 / T007 原文"),
    (r"## Your own opening statement", "己方立论", "自己的总论点和论据标题，用于保持前后一致"),
    (r"## (多方|空方)'s arguments to rebut", "对方论据", "要逐条反驳的线程，含已有交锋"),
    (r"## Your arguments and the rebuttals to answer", "己方论据与对方反驳", "自己的线程，每个线程最后一条是对方刚给出的反驳"),
    (r"## Debate so far", "辩论记录", "到目前为止全部线程的交锋"),
    (r"## Opening statements", "双方立论", "双方的总论点、自评置信度、证伪条件"),
    (r"## Debate record", "辩论记录", "全部线程的完整交锋"),
    (r"## How the debate ended", "终止理由", "每轮之后主持人或规则的判断"),
    (r"# Evidence pack", "证据包", "数据覆盖表 + 技术指标 / 基本面 / 新闻 / 研报 / 日线"),
]


def prompt_blocks(prompt: str) -> list[dict]:
    """
    The top-level sections of a recorded prompt with their character counts:
    the role and rules first, then every `## ` section before the evidence
    pack, then the evidence pack as one block.

    留痕提示词的各顶层段落及其字符数：先是角色与规则，然后是证据包之前的每个 `## ` 段落，最后证据包
    整体算一块。
    """
    evidence_at = prompt.find("\n# Evidence pack")
    head = prompt if evidence_at < 0 else prompt[:evidence_at + 1]
    cuts = [m.start() for m in re.finditer(r"^## .*$", head, re.M)] + ([evidence_at + 1] if evidence_at >= 0 else [])
    out = [{"label": "角色与规则", "note": "这一步的任务、输出字段和约束", "chars": cuts[0] if cuts else len(prompt)}]
    for i, pos in enumerate(cuts):
        line_end = prompt.find("\n", pos)
        heading = prompt[pos:line_end if line_end >= 0 else len(prompt)]
        label, note = next(((lab, note) for pat, lab, note in _BLOCKS if re.match(pat, heading)), (heading.lstrip("# ").strip(), ""))
        out.append({"label": label, "note": note, "chars": (cuts[i + 1] if i + 1 < len(cuts) else len(prompt)) - pos})
    return out


def _excerpt(text: str, limit: int = 140) -> str:
    """
    First `limit` characters of a text, with an ellipsis when cut.

    文本的前 `limit` 个字符，被截断时加省略号。
    """
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def _step_plan(debate: Debate) -> list[dict]:
    """
    The calls that produced this debate, in logical order, derived from who
    spoke in which round and which rulings came from the moderator.

    产生这场辩论的各次调用，按逻辑顺序排列；由每轮谁发过言、哪些判断出自主持人推出。
    """
    plan = [{"id": f"{side}_thesis", "role": side, "kind": "thesis", "round": 0, "template": f"{side}_thesis.md"} for side in SIDES]
    for r in range(1, debate.rounds_held + 1):
        for kind in ("rebuttal", "defence"):
            for side in SIDES:
                if any(x.round == r and x.kind == kind and x.speaker == side for t in debate.threads for x in t.exchanges):
                    plan.append({"id": f"debate_r{r}_{kind}_{side}", "role": side, "kind": kind, "round": r, "template": TEMPLATE[kind]})
        if any(g.round == r and g.decided_by == "moderator" for g in debate.rulings):
            plan.append({"id": f"debate_r{r}_moderator", "role": "mod", "kind": "moderator", "round": r, "template": TEMPLATE["moderator"]})
    plan.append({"id": "manager", "role": "mgr", "kind": "manager", "round": 0, "template": TEMPLATE["manager"]})
    for stage, step in enumerate(plan):
        step["stage"] = stage
    return plan


def _timing(symbol_dir: Path, step_id: str) -> Optional[dict]:
    """
    Start, finish, cost and attempts of one call from its response record;
    None when the record is absent. Records written before the times were
    stored fall back to the file time minus the reported duration.

    从响应留痕读一次调用的起止时间、费用和尝试次数；留痕不存在时返回 None。早于记录起止时间的留痕
    退回到文件时间减去上报的耗时。
    """
    path = symbol_dir / f"{step_id}.response.json"
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    raw = rec.get("raw") or {}
    if rec.get("finished_at") and rec.get("started_at"):
        start, end = datetime.fromisoformat(rec["started_at"]), datetime.fromisoformat(rec["finished_at"])
    else:
        end = datetime.fromtimestamp(os.stat(path).st_mtime).astimezone()
        start = end - timedelta(milliseconds=raw.get("duration_ms") or 0)
    return {"start": start, "end": end, "cost": float(raw.get("total_cost_usd") or 0.0), "attempts": int(rec.get("attempt") or 0) + 1}


def _closed_after(debate: Debate, r: int) -> tuple[list[str], list[str]]:
    """
    Point ids whose thread was closed in round `r`: (objection withdrawn,
    point conceded).

    在第 `r` 轮关闭的线程的论据编号：（异议被撤回的，认输的）。
    """
    withdrawn = [t.point_id for t in debate.threads for x in t.exchanges if x.round == r and x.kind == "rebuttal" and x.withdrawn]
    conceded = [t.point_id for t in debate.threads for x in t.exchanges if x.round == r and x.kind == "defence" and x.stance == "concede"]
    return withdrawn, conceded


def _contested_after(debate: Debate, r: int) -> int:
    """
    How many threads were still contested once round `r` was over.

    第 `r` 轮结束时仍在争议的线程数。
    """
    closed = {t.point_id for t in debate.threads for x in t.exchanges
              if x.round <= r and ((x.kind == "rebuttal" and x.withdrawn) or (x.kind == "defence" and x.stance == "concede"))}
    return len(debate.threads) - len(closed)


def _result_and_glue(step: dict, outcome: JudgeOutcome, position: Optional[Position], last_of_stage: bool, cache_file: str) -> tuple[str, list[dict], str]:
    """
    For one call: a one-line summary of what came back, the items it
    returned (`id`, `tag`, excerpt) and, on the last call of a stage, what
    the code did before the next call.

    针对一次调用：返回结果的一行摘要、返回的各条目（编号、标签、摘录），以及（在该阶段最后一次调用上）
    下一次调用之前代码做了什么。
    """
    debate, decision, kind, role, r = outcome.debate, outcome.decision, step["kind"], step["role"], step["round"]
    glue = ""
    if kind == "thesis":
        thesis = outcome.long_thesis if role == "long" else outcome.short_thesis
        pre, n = POINT_PREFIX[role], len(thesis.key_points)
        result = f"{n} 条论据，编号 {pre}1–{pre}{n}；自评置信度 {thesis.confidence}"
        items = [{"id": f"{pre}{i}", "tag": STRENGTH_ZH[p.strength], "text": _excerpt(p.claim)} for i, p in enumerate(thesis.key_points, 1)]
        if last_of_stage:
            counts = "、".join(f"{POINT_PREFIX[s]}1–{POINT_PREFIX[s]}{sum(1 for t in debate.threads if t.owner == s)}" for s in SIDES)
            glue = f"给论据编号并建线程：{counts}，一条论据一个线程。"
    elif kind in ("rebuttal", "defence"):
        said = [(t.point_id, x) for t in debate.threads for x in t.exchanges if x.round == r and x.kind == kind and x.speaker == role]
        real = [(pid, x) for pid, x in said if not x.unanswered]
        silent = [pid for pid, x in said if x.unanswered]
        if kind == "rebuttal":
            dropped = [pid for pid, x in real if x.withdrawn]
            result = f"{len(real)} 条反驳" + (f"，其中 {'、'.join(dropped)} 撤回异议" if dropped else "")
            items = [{"id": pid, "tag": "撤回异议" if x.withdrawn else ATTACK_ZH.get(x.attack_type, "其他"), "text": _excerpt(x.argument)} for pid, x in real]
        else:
            counts = {z: sum(1 for _, x in real if x.stance == s) for s, z in STANCE_ZH.items()}
            result = f"{len(real)} 条再反驳：" + "，".join(f"{z} {n}" for z, n in counts.items() if n)
            items = [{"id": pid, "tag": STANCE_ZH.get(x.stance, "坚持"), "text": _excerpt(x.revised_claim or x.argument)} for pid, x in real]
        if silent:
            result += f"；{'、'.join(silent)} 未回应"
            items += [{"id": pid, "tag": "未回应", "text": ""} for pid in silent]
        if last_of_stage:
            total = sum(1 for t in debate.threads for x in t.exchanges if x.round == r and x.kind == kind and not x.unanswered)
            withdrawn, conceded = _closed_after(debate, r)
            if kind == "rebuttal":
                glue = f"把 {total} 条反驳挂到各自线程上。" + (f"{'、'.join(withdrawn)} 的异议被撤回，线程关闭，不再需要答辩。" if withdrawn else "")
            else:
                ruling = next((g for g in debate.rulings if g.round == r), None)
                left = _contested_after(debate, r)
                glue = f"把 {total} 条再反驳挂到线程上。" + (f"{'、'.join(conceded)} 认输，线程关闭。" if conceded else "") + f"还剩 {left} 个争议线程。"
                if ruling and ruling.decided_by == "rule":
                    glue += f"代码直接终止辩论：{ruling.reason}"
                elif ruling:
                    glue += "未到轮数上限，于是询问主持人。"
    elif kind == "moderator":
        ruling = next(g for g in debate.rulings if g.round == r)
        result = ("继续下一轮" if ruling.continue_debate else "终止辩论") + "，附理由"
        items = [{"id": "理由", "tag": "继续" if ruling.continue_debate else "终止", "text": ruling.reason}]
        glue = "记录主持人的判断和理由。" + (f"判断为继续，第 {r + 1} 轮只辩：{'、'.join(ruling.focus_point_ids)}。" if ruling.continue_debate else "判断为终止，进入 Manager。")
    else:
        counts = {z: sum(1 for v in decision.point_verdicts if v.verdict == k) for k, z in VERDICT_ZH.items()}
        result = f"方向 {decision.direction}，置信度 {decision.confidence}；裁定 " + "，".join(f"{z} {n}" for z, n in counts.items())
        items = [{"id": v.point_id, "tag": VERDICT_ZH[v.verdict], "text": _excerpt(v.reason)} for v in decision.point_verdicts]
        reversal = "无持仓，结果为 None" if position is None else f"持有 {position.direction} {position.volume} 手，结果为 {decision.reversal}"
        glue = (f"丢弃不存在的论据编号；按 T021 用代码重算反转标志（{reversal}）；写出缓存 {cache_file or 'decision.<key>.json'}。"
                "全部品种跑完后由 cli.py 渲染 debate.md、report.md、decisions.json 和 flow.json。")
    return result, items, glue


def _job(step: dict) -> str:
    """
    What one call is asked to do, in a sentence.

    用一句话说明一次调用被要求做什么。
    """
    kind, role, r = step["kind"], step["role"], step["round"]
    if kind == "thesis":
        return f"{SIDE_ZH[role]}只看证据包，写出判断为 {role} 的最强论证，列出 3–6 条论据。"
    if kind == "rebuttal":
        return (f"{SIDE_ZH[role]}逐条反驳{SIDE_ZH[other(role)]}仍在争议的论据，每条指明攻击类型。"
                + ("须针对对方上一轮的再反驳，不得重复已有的攻击。" if r > 1 else ""))
    if kind == "defence":
        return f"{SIDE_ZH[role]}对自己论据受到的反驳逐条回应：坚持、收窄或认输。"
    if kind == "moderator":
        return f"读完第 {r} 轮的全部交锋，判断是否值得再打一轮，并给出理由。"
    return "对每条论据给出裁定，再根据存活的论据决定方向。证据包只用来核对双方的引用。"


def build_flow(outcome: JudgeOutcome, symbol_dir: Path, pack_date: str, name: str = "", last_session: str = "",
               position: Optional[Position] = None, config: Optional[dict] = None) -> dict:
    """
    The flow of one judged symbol (see the module docstring for its parts).
    `symbol_dir` is `runs/<pack_date>/<symbol>/`, where the per-call records
    and the decision cache live.

    一个已判断品种的 flow（各部分见模块说明）。`symbol_dir` 即 `runs/<包日期>/<品种>/`，逐次调用的
    留痕和决策缓存都在这里。
    """
    debate, decision = outcome.debate, outcome.decision
    caches = sorted(symbol_dir.glob("decision.*.json"), key=lambda p: p.stat().st_mtime)
    cache_file = caches[-1].name if caches else ""
    plan = _step_plan(debate)
    timings = {s["id"]: _timing(symbol_dir, s["id"]) for s in plan}
    groups: list[list[dict]] = []
    for s in plan:  # calls of one stage (same round and kind) ran side by side / 同一阶段（同轮同类）的调用并行执行
        if groups and (groups[-1][0]["round"], groups[-1][0]["kind"]) == (s["round"], s["kind"]):
            groups[-1].append(s)
        else:
            groups.append([s])
    known = [t for t in timings.values() if t]
    origin = min((t["start"] for t in known), default=None)
    steps = []
    for group in groups:
        group.sort(key=lambda s: (timings[s["id"]] is None, timings[s["id"]]["end"] if timings[s["id"]] else s["stage"]))
        for i, s in enumerate(group):
            t = timings[s["id"]]
            result, items, glue = _result_and_glue(s, outcome, position, i == len(group) - 1, cache_file)
            prompt_path = symbol_dir / f"{s['id']}.prompt.md"
            prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else None
            steps.append({
                "id": s["id"], "role": s["role"], "kind": s["kind"], "round": s["round"], "phase": PHASE_ZH[s["kind"]],
                "label": ROLE_ZH[s["role"]] + (PHASE_ZH[s["kind"]] if s["role"] in SIDES else ""), "template": s["template"], "job": _job(s),
                "start": t["start"].strftime("%H:%M:%S") if t else None, "end": t["end"].strftime("%H:%M:%S") if t else None,
                "t0": round((t["start"] - origin).total_seconds(), 3) if t else None, "t1": round((t["end"] - origin).total_seconds(), 3) if t else None,
                "seconds": round((t["end"] - t["start"]).total_seconds()) if t else None,
                "cost": round(t["cost"], 2) if t else None, "attempts": t["attempts"] if t else None,
                "promptChars": len(prompt) if prompt is not None else None, "blocks": prompt_blocks(prompt) if prompt is not None else [],
                "result": result, "items": items, "glue": glue})
    verdicts = {v.point_id: v for v in decision.point_verdicts}
    threads = []
    for t in debate.threads:
        v = verdicts.get(t.point_id)
        threads.append({
            "id": t.point_id, "owner": t.owner, "strength": STRENGTH_ZH[t.strength], "status": STATUS_ZH[t.status],
            "claim": t.claim, "reasoning": t.reasoning, "refs": t.evidence_refs,
            "verdict": VERDICT_ZH[v.verdict] if v else None, "verdictReason": v.reason if v else "",
            "exchanges": [{"round": x.round, "speaker": x.speaker, "kind": PHASE_ZH[x.kind], "unanswered": x.unanswered,
                           "tag": "未回应" if x.unanswered else (("撤回异议" if x.withdrawn else ATTACK_ZH.get(x.attack_type, "其他")) if x.kind == "rebuttal" else STANCE_ZH.get(x.stance, "坚持")),
                           "text": x.argument, "revised": x.revised_claim or "", "refs": x.evidence_refs} for x in t.exchanges]})
    return {
        "schema": FLOW_SCHEMA, "symbol": outcome.symbol, "name": name or outcome.symbol, "packDate": pack_date, "lastSession": last_session,
        "config": {"model": (config or {}).get("model"), "effort": (config or {}).get("effort"), "maxRounds": (config or {}).get("max_debate_rounds")},
        "position": {"direction": position.direction, "volume": position.volume} if position else None,
        "decision": {"direction": decision.direction, "confidence": decision.confidence, "quality": decision.evidence_quality, "reversal": decision.reversal,
                     "uncertainIsHighConfidence": decision.uncertain_is_high_confidence, "summary": decision.debate_summary,
                     "reasoning": decision.reasoning, "drivers": decision.key_drivers, "risks": decision.risk_flags},
        "rounds": debate.rounds_held,
        "rulings": [{"round": g.round, "by": g.decided_by, "continue": g.continue_debate, "reason": g.reason, "focus": g.focus_point_ids} for g in debate.rulings],
        "cost": round(outcome.cost_usd, 2),
        "wall": round((max(t["end"] for t in known) - origin).total_seconds()) if known else None,
        "clock0": origin.hour * 3600 + origin.minute * 60 + origin.second + origin.microsecond / 1e6 if origin else None,
        "steps": steps, "threads": threads,
        "theses": {side: {"thesis": th.thesis, "confidence": th.confidence, "falsifiers": th.falsifiers}
                   for side, th in (("long", outcome.long_thesis), ("short", outcome.short_thesis)) if th},
        "cacheFile": cache_file,
    }


def write_flows(run_dir: Path, outcomes: dict[str, JudgeOutcome], pack_date: str, meta: Optional[dict[str, dict]] = None,
                positions: Optional[dict[str, Position]] = None, config: Optional[dict] = None) -> list[Path]:
    """
    Write `<symbol>/flow.json` under `run_dir` for every outcome that has a
    debate and both opening statements; returns the files written. `meta`
    maps symbol -> {"name", "last_session"}.

    为每个带辩论和双方立论的结果在 `run_dir` 下写出 `<品种>/flow.json`；返回写出的文件。`meta` 为
    品种 -> {"name", "last_session"}。
    """
    written = []
    for sym, o in outcomes.items():
        if not (o.debate and o.long_thesis and o.short_thesis):
            continue
        m = (meta or {}).get(sym) or {}
        flow = build_flow(o, run_dir / sym, pack_date, name=m.get("name", ""), last_session=m.get("last_session", ""),
                          position=(positions or {}).get(sym), config=config)
        (run_dir / sym).mkdir(parents=True, exist_ok=True)
        path = run_dir / sym / "flow.json"
        path.write_text(json.dumps(flow, ensure_ascii=False, indent=1), encoding="utf-8")
        written.append(path)
    return written


def write_index(runs_dir: Path) -> Path:
    """
    Rebuild `runs/index.json` from every `<pack_date>/<symbol>/flow.json`
    on disk: pack dates newest first, each with its symbols and their
    decisions.

    根据磁盘上所有的 `<包日期>/<品种>/flow.json` 重建 `runs/index.json`：包日期从新到旧，每个日期
    列出品种及其决策。
    """
    runs: dict[str, list[dict]] = {}
    for path in sorted(Path(runs_dir).glob("*/*/flow.json")):
        try:
            f = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        runs.setdefault(path.parent.parent.name, []).append({
            "symbol": f["symbol"], "name": f.get("name") or f["symbol"], "direction": f["decision"]["direction"],
            "confidence": f["decision"]["confidence"], "rounds": f["rounds"], "cost": f.get("cost")})
    index = {"schema": FLOW_SCHEMA, "runs": [{"packDate": d, "symbols": runs[d]} for d in sorted(runs, reverse=True)]}
    out = Path(runs_dir) / "index.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    return out
