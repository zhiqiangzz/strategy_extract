"""
Agents: read the English part only. 中文仅供人类阅读。

cli.py — command-line entry points.

    uv run python -m strategies.resonance.cli judge --pack scratchpad/2026-09-30 --symbols CU,LC --account 123456 [--dry-run] [--no-reload] [--capital 1000000] [--positions file.json] [--evidence compact|full] [--max-rounds 3] [--workers 5] [--no-cache] [--runs-dir DIR]
    uv run python -m strategies.resonance.cli report --pack-date 2026-09-30 [--runs-dir DIR]
    uv run python -m strategies.resonance.cli plan --pack-date 2026-09-30 [--pack scratchpad/2026-09-30] [--plan-config FILE] [--plan-out FILE] [--runs-dir DIR]
    uv run python -m strategies.resonance.cli web [--port 8770] [--runs-dir DIR]

`judge` loads the evidence pack, fetches positions and capital from the
control API (or from `--positions` / `--capital`), runs the debate per
symbol, writes `runs/<date>/decisions.json`, `report.md`, one
`<symbol>/debate.md` (the full debate record) and one `<symbol>/flow.json`
(the data the web page template is filled with) per symbol, refreshes
`runs/index.json`, and turns the decisions into the order plan
`runs/<date>/order_plan.json` (`orders.py`; parameters in `order_plan.toml`
or `--plan-config`, `--plan-out` copies the plan elsewhere, `--no-plan`
skips it). Unless `--dry-run`, it also builds the setting file (with DB lookups and warm-up bars),
writes it to the vntrader directory (`--setting-out`, default
`third_party/quant_trading/rust_core/.vntrader/resonance_setting_<account>.json`)
and asks the core to reload (`--no-reload` skips that). `report` re-renders
the Markdown and flow files from a saved decisions.json. `plan` recomputes
the order plan from a saved decisions.json without judging again, for
example after changing the parameters. `web` serves the
built page template (`web/dist`) together with the flow files on localhost.
All commands read and write under one runs directory: `strategies/resonance/runs`
by default, `--runs-dir` to use another (pass the same one to each command).

cli.py 是命令行入口。`judge` 读取证据包、从 control API（或 `--positions` / `--capital`）取持仓与
资金、逐品种辩论、写出 `runs/<日期>/decisions.json`、`report.md`，以及每个品种的 `<品种>/debate.md`
（完整辩论记录）和 `<品种>/flow.json`（网页模板要填充的数据），刷新 `runs/index.json`，并把决策变成订单计划
`runs/<日期>/order_plan.json`（`orders.py`；参数在 `order_plan.toml` 或 `--plan-config`，`--plan-out` 另存一份，
`--no-plan` 跳过）；除非 `--dry-run`，否则还会组装设置文件（含 DB 查询与预热 K 线）、写入 vntrader 目录
（`--setting-out`，默认 `third_party/quant_trading/rust_core/.vntrader/resonance_setting_<账户>.json`）
并通知 core 重载（`--no-reload` 跳过）。`report` 从保存的 decisions.json 重新渲染各 Markdown 文件和
flow 文件。`plan` 不重新判断，直接从保存的 decisions.json 重算订单计划（例如改了参数之后）。`web` 在本机提供
构建好的页面模板（`web/dist`）和 flow 数据。所有命令都在同一个 runs 目录下读写：默认是
`strategies/resonance/runs`，用 `--runs-dir` 可换成别的目录（各命令要传同一个）。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from .config import REPO_ROOT, JudgeConfig, ResonanceParams
from .debate import (ATTACK_ZH, SIDE_ZH, SIDES, STANCE_ZH, STRENGTH_ZH, VERDICT_ZH, JudgeOutcome, judge_many, render_opening,
                     render_rulings, render_threads)
from .evidence import FUNDAMENTAL, NEWS, RESEARCH, TECHNICAL, load_pack
from .flow import write_flows, write_index
from .orders import AUDIT_FILE, DbMarketData, PlanResult, build_order_plan, load_plan_config, read_order_plan, write_order_plan
from .positions import from_control_api, from_file
from .schemas import Debate, DebateThread, Decision, Position, Thesis
from .serve import serve
from .signal_writer import build_setting, reload_core, write_setting


def _cell(text: object) -> str:
    """
    Make text safe for one Markdown table cell.

    把文本处理成可放进 Markdown 表格单元格的形式。
    """
    return str(text).replace("|", "\\|").replace("\n", " ")


def _exchange_tags(t: DebateThread) -> str:
    """
    The course of a thread as a chain of tags (举反例 → 坚持 → …).

    把一个线程的交锋过程写成标签链（举反例 → 坚持 → …）。
    """
    tags = []
    for x in t.exchanges:
        if x.unanswered:
            tags.append("未回应")
        elif x.kind == "rebuttal":
            tags.append("撤回异议" if x.withdrawn else ATTACK_ZH.get(x.attack_type, "其他"))
        else:
            tags.append(STANCE_ZH.get(x.stance, "坚持"))
    return " → ".join(tags) or "-"


def _price(value: float | None) -> str:
    """
    A price for display: no trailing ".0", "-" for none.

    显示用的价格：去掉结尾的 ".0"，没有则为 "-"。
    """
    return "-" if value is None else f"{value:.10g}"


def render_plan(plan: PlanResult) -> list[str]:
    """
    The order-plan section of the report: one row per order with how it was
    sized, then the symbols that got no order and why.

    报告中的订单计划部分：每张订单一行及其计算依据，之后是未出单的品种和原因。
    """
    sizing = {s["order_id"]: s for s in plan.sizing}
    L = ["## 订单计划", "",
         f"`{plan.plan.plan_id}`，决策时点 {plan.plan.created_at}，共 {len(plan.plan.orders)} 张订单。文件 `order_plan.json`，计算明细 `{AUDIT_FILE}`。", ""]
    if plan.plan.orders:
        L += ["| 订单 | 合约 | 动作 | 手数 | 入场区间 | 止损 | 目标 | 参考价（时间） | 日线 ATR | 止损距离 | 保证金占用 / 预算 | 最大亏损 / 上限 | 手数受限于 |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for o in plan.plan.orders:
            s = sizing.get(o.order_id)
            zone = f"{_price(o.limit_price[0])} – {_price(o.limit_price[1])}" if o.limit_price else "-"
            tail = (f"{_price(s['reference_price'])}（{s['reference_time']}） | {_price(s['atr'])} | {_price(s['stop_distance'])}（{s['stop_atr']} 倍 ATR） | "
                    f"{s['margin_used']:,.0f} / {s['budget_cny']:,.0f} | {s['max_loss']:,.0f} / {s.get('loss_limit_cny', s['max_loss']):,.0f} | "
                    f"{s['limited_by']}") if s else "- | - | - | - | - | -"
            L.append(f"| {o.order_id} | {o.contract} | {o.action} {o.side} | {o.lots} | {zone} | {_price(o.stop_price)} | {_price(o.target_price)} | {tail} |")
        L.append("")
    if plan.skipped:
        L += ["未出单："] + [f"- {s['symbol']}：{s['reason']}" for s in plan.skipped] + [""]
    return L


def render_report(outcomes: dict[str, JudgeOutcome], pack_date: str, capital: float | None, plan: PlanResult | None = None) -> str:
    """
    Markdown report: one table row per symbol with the four sources'
    verdicts and the manager decision, the order plan when there is one,
    then per symbol the reasoning, how the debate went and the ruling on
    every point.

    Markdown 报告：每品种一行（四个来源的结论与 Manager 决策），有订单计划时附上，之后是每个品种的
    理由、辩论进程和每条论据的裁定。
    """
    L = [f"# 大小周期共振 · 大周期方向判定 — 证据包 {pack_date}", "",
         f"决策时点：{pack_date} 开盘前。生成时间 {datetime.now().astimezone().isoformat(timespec='seconds')}；本金 {capital}；"
         f"总费用 ${sum(o.cost_usd for o in outcomes.values()):.2f}；命中缓存 {sum(1 for o in outcomes.values() if o.cached)}/{len(outcomes)}。", "",
         f"| 品种 | {TECHNICAL} | {FUNDAMENTAL} | {NEWS} | {RESEARCH} | **方向** | 置信度 | 反转 | 证据质量 | 辩论轮数 |", "|---|---|---|---|---|---|---|---|---|---|"]
    for sym in sorted(outcomes):
        o = outcomes[sym]; v = o.verdicts; d = o.decision
        L.append(f"| {sym} | {v.get(TECHNICAL, '-')} | {v.get(FUNDAMENTAL, '-')} | {v.get(NEWS, '-')} | {v.get(RESEARCH, '-')} | **{d.direction}** | {d.confidence:.2f} | {d.reversal} | "
                 f"{d.evidence_quality}{' ERROR' if o.error else ''} | {o.debate.rounds_held if o.debate else '-'} |")
    L.append("")
    if plan:
        L += render_plan(plan)
    for sym in sorted(outcomes):
        o = outcomes[sym]; d = o.decision
        L += [f"## {sym} — {d.direction}（{d.confidence:.2f}）", "", d.reasoning, "",
              f"- 关键论据：{'；'.join(d.key_drivers) or '-'}", f"- 风险：{'；'.join(d.risk_flags) or '-'}",
              f"- 高置信度不确定：{d.uncertain_is_high_confidence}；反转：{d.reversal}；费用 ${o.cost_usd:.2f}；耗时 {o.duration_s:.0f}s" + (f"；错误：{o.error}" if o.error else ""), ""]
        if not o.debate:
            continue
        verdicts = {v.point_id: v for v in d.point_verdicts}
        L += [f"### {sym} 辩论（{o.debate.rounds_held} 轮）", "", render_rulings(o.debate), ""]
        if d.debate_summary:
            L += [d.debate_summary, ""]
        L += ["| 论据 | 方 | 强度 | 交锋 | 裁定 | 内容 |", "|---|---|---|---|---|---|"]
        for t in o.debate.threads:
            pv = verdicts.get(t.point_id)
            L.append(f"| {t.point_id} | {SIDE_ZH[t.owner]} | {STRENGTH_ZH[t.strength]} | {_exchange_tags(t)} | {VERDICT_ZH[pv.verdict] if pv else '-'} | {_cell(t.claim)} |")
        L += ["", f"[完整辩论记录]({sym}/debate.md)", ""]
    return "\n".join(L)


def render_debate_md(o: JudgeOutcome, pack_date: str) -> str:
    """
    The full debate record of one symbol: opening statements, every thread
    with its exchanges and the manager's ruling, why each round continued or
    stopped, and the manager's summary and reasoning.

    一个品种的完整辩论记录：双方立论、每个线程的交锋与 Manager 裁定、每轮继续或终止的理由，以及
    Manager 的总结与理由。
    """
    d = o.decision
    verdicts = {v.point_id: v for v in d.point_verdicts}
    L = [f"# {o.symbol} 辩论记录 — 证据包 {pack_date}", "",
         f"决策时点：{pack_date} 开盘前。结论：**{d.direction}**（置信度 {d.confidence:.2f}，证据质量 {d.evidence_quality}，共 {o.debate.rounds_held} 轮）。", "", "## 立论", ""]
    for side, thesis in zip(SIDES, (o.long_thesis, o.short_thesis)):
        if thesis:
            L += [f"### {SIDE_ZH[side]}立论", "", render_opening(thesis).replace("\n", "\n\n"), ""]
    for side in SIDES:
        L += [f"## {SIDE_ZH[side]}论据", "", render_threads([t for t in o.debate.threads if t.owner == side], verdicts), ""]
    L += ["## 辩论进程", "", render_rulings(o.debate), "", "## Manager 裁决", ""]
    if d.debate_summary:
        L += [d.debate_summary, ""]
    L += [d.reasoning, "", f"- 关键论据：{'；'.join(d.key_drivers) or '-'}", f"- 风险：{'；'.join(d.risk_flags) or '-'}", ""]
    return "\n".join(L)


def write_outputs(run_dir: Path, outcomes: dict[str, JudgeOutcome], pack_date: str, capital: float | None, meta: dict[str, dict] | None = None,
                  positions: dict[str, Position] | None = None, config: dict | None = None, plan: PlanResult | None = None) -> None:
    """
    Write report.md and, per debated symbol, <symbol>/debate.md and
    <symbol>/flow.json; then refresh index.json one level above `run_dir`.
    `meta` (symbol -> name, last session), `positions` and `config` (model
    settings) only feed the flow files; `plan` adds the order-plan section
    to the report.

    写出 report.md，以及每个已辩论品种的 <品种>/debate.md 和 <品种>/flow.json；然后刷新 `run_dir`
    上一级的 index.json。`meta`（品种 -> 名称、最后交易日）、`positions` 和 `config`（模型设置）只用于
    flow 文件；`plan` 用于在报告里加入订单计划部分。
    """
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "report.md").write_text(render_report(outcomes, pack_date, capital, plan), encoding="utf-8")
    for sym, o in outcomes.items():
        if o.debate:
            (run_dir / sym).mkdir(parents=True, exist_ok=True)
            (run_dir / sym / "debate.md").write_text(render_debate_md(o, pack_date), encoding="utf-8")
    write_flows(run_dir, outcomes, pack_date, meta, positions, config)
    write_index(run_dir.parent)


def _runs_dir(args: argparse.Namespace) -> Path:
    """
    The runs directory of a command: `--runs-dir` when given (relative paths
    are taken from the current directory), else the default of JudgeConfig.

    一个命令使用的 runs 目录：给了 `--runs-dir` 就用它（相对路径相对当前目录），否则用 JudgeConfig 的
    默认值。
    """
    return Path(args.runs_dir).expanduser().resolve() if args.runs_dir else JudgeConfig().runs_dir


def make_plan(args: argparse.Namespace, run_dir: Path, pack_date: str, decisions: dict[str, Decision], atr: dict[str, float | None],
              positions: dict[str, Position], errors: dict[str, str]) -> PlanResult | None:
    """
    Build the order plan from the decisions and write it into `run_dir`
    (and to `--plan-out`). Returns None with `--no-plan`, or when building
    fails; a failure is printed and never loses the decisions.

    根据决策生成订单计划并写入 `run_dir`（以及 `--plan-out`）。带 `--no-plan` 或生成失败时返回 None；
    失败只打印出来，不会影响已得到的决策。
    """
    if getattr(args, "no_plan", False):
        return None
    try:
        plan_cfg = load_plan_config(Path(args.plan_config) if args.plan_config else None)
        plan = build_order_plan(pack_date, decisions, atr, positions, plan_cfg, DbMarketData(), errors)
        path = write_order_plan(plan, run_dir, plan_cfg, Path(args.plan_out) if args.plan_out else None)
    except Exception as exc:  # noqa: BLE001 - the judgement is already saved
        print(f"[plan] not written: {exc}", file=sys.stderr)
        return None
    print(f"[plan] {plan.plan.plan_id}: {len(plan.plan.orders)} order(s) -> {path}" + (f" and {args.plan_out}" if args.plan_out else ""))
    for o in plan.plan.orders:
        print(f"[plan] {o.order_id} {o.contract} {o.action} {o.side} {o.lots} lots, limit {o.limit_price}, stop {o.stop_price}, target {o.target_price}")
    for s in plan.skipped:
        print(f"[plan] no order for {s['symbol']}: {s['reason']}")
    return plan


def cmd_judge(args: argparse.Namespace) -> int:
    """
    The `judge` command; returns the exit code.

    `judge` 命令；返回退出码。
    """
    if not args.no_plan:
        load_plan_config(Path(args.plan_config) if args.plan_config else None)  # a bad parameter file fails here, before any model call
    cfg = JudgeConfig(model=args.model, effort=args.effort, evidence_level=args.evidence, max_debate_rounds=args.max_rounds,
                      max_workers=args.workers, use_cache=not args.no_cache, runs_dir=_runs_dir(args))
    params = ResonanceParams(**json.loads(args.params)) if args.params else ResonanceParams()
    symbols = [s.strip().upper() for s in args.symbols.split(",")] if args.symbols else None
    evidences = load_pack(Path(args.pack), symbols)
    if not evidences:
        print("no symbols found in pack", file=sys.stderr); return 2
    positions, capital = {}, args.capital
    if args.positions:
        positions = from_file(Path(args.positions))
    else:
        try:
            positions, api_capital = from_control_api(cfg.control_url, args.account)
            capital = capital or api_capital
            print(f"[judge] control API: {len(positions)} open position(s), capital {api_capital}")
        except Exception as exc:  # noqa: BLE001
            print(f"[judge] control API unreachable ({exc}); assuming flat" + ("" if capital else ", capital unknown"))
    print(f"[judge] pack {next(iter(evidences.values())).pack_date}: {len(evidences)} symbols, model {cfg.model}/{cfg.effort}, evidence {cfg.evidence_level}, "
          f"max rounds {cfg.max_debate_rounds}, workers {cfg.max_workers}")
    outcomes = judge_many(evidences, positions, cfg, params,
                          on_done=lambda o: print(f"[judge] {o.symbol}: {o.decision.direction} conf={o.decision.confidence:.2f} reversal={o.decision.reversal} "
                                                  f"rounds={o.debate.rounds_held if o.debate else '-'} ${o.cost_usd:.2f}{' (cached)' if o.cached else ''}{' ERROR ' + o.error if o.error else ''}", flush=True))
    pack_date = next(iter(evidences.values())).pack_date
    run_dir = cfg.runs_dir / pack_date
    run_dir.mkdir(parents=True, exist_ok=True)
    meta = {s: {"name": ev.variety_name, "last_session": ev.last_session, "atr": ev.daily_atr} for s, ev in evidences.items()}
    config = {"model": cfg.model, "effort": cfg.effort, "evidence_level": cfg.evidence_level, "max_debate_rounds": cfg.max_debate_rounds}
    (run_dir / "decisions.json").write_text(json.dumps(
        {"pack_date": pack_date, "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"), "capital": capital,
         "config": config, "meta": meta,
         "positions": {k: v.model_dump() for k, v in positions.items()},
         "decisions": {s: o.decision.model_dump() for s, o in outcomes.items()},
         "verdicts": {s: o.verdicts for s, o in outcomes.items()},
         "theses": {s: {"long": o.long_thesis.model_dump(), "short": o.short_thesis.model_dump()} for s, o in outcomes.items() if o.long_thesis and o.short_thesis},
         "debates": {s: o.debate.model_dump() for s, o in outcomes.items() if o.debate},
         "cost_usd": {s: o.cost_usd for s, o in outcomes.items()}, "duration_s": {s: round(o.duration_s, 1) for s, o in outcomes.items()},
         "errors": {s: o.error for s, o in outcomes.items() if o.error}},
        ensure_ascii=False, indent=2), encoding="utf-8")
    plan = make_plan(args, run_dir, pack_date, {s: o.decision for s, o in outcomes.items()}, {s: m["atr"] for s, m in meta.items()}, positions,
                     {s: o.error for s, o in outcomes.items() if o.error})
    write_outputs(run_dir, outcomes, pack_date, capital, meta, positions, config, plan)
    print(f"[judge] wrote {run_dir / 'decisions.json'}, report.md, <symbol>/debate.md and <symbol>/flow.json; total cost ${sum(o.cost_usd for o in outcomes.values()):.2f}")
    if args.dry_run:
        return 0
    if not capital:
        print("[judge] capital unknown: pass --capital or run with the core reachable; setting file not written", file=sys.stderr); return 3
    setting, skipped = build_setting(outcomes, args.account or "primary", pack_date, float(capital), params, with_warmup=not args.no_warmup)
    for s in skipped:
        print(f"[setting] skipped {s['symbol']}: {s['reason']}")
    out = Path(args.setting_out) if args.setting_out else (REPO_ROOT / "third_party" / "quant_trading" / "rust_core" / ".vntrader" / f"resonance_setting_{args.account or 'primary'}.json")
    write_setting(setting, out)
    (run_dir / out.name).write_text(out.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"[setting] wrote {out} ({len(setting.contracts)} contracts); copy in {run_dir}")
    if args.no_reload:
        return 0
    try:
        print("[reload]", reload_core(cfg.control_url, args.account))
    except Exception as exc:  # noqa: BLE001
        print(f"[reload] failed: {exc} (the file is written; reload manually with POST /api/strategy/reload)")
        return 4
    return 0


def _load_run(run_dir: Path) -> tuple[dict, dict[str, JudgeOutcome], dict[str, Position]]:
    """
    A saved run: the decisions.json document, the outcomes rebuilt from it
    and the positions it was judged with.

    读取一次已保存的运行：decisions.json 文档、由它重建的各品种结果，以及判断时的持仓。
    """
    d = json.loads((run_dir / "decisions.json").read_text(encoding="utf-8"))
    theses, debates = d.get("theses", {}), d.get("debates", {})
    outcomes = {s: JudgeOutcome(symbol=s, decision=Decision(**dec), cost_usd=d.get("cost_usd", {}).get(s, 0.0), duration_s=d.get("duration_s", {}).get(s, 0.0),
                                verdicts=d.get("verdicts", {}).get(s, {}), error=d.get("errors", {}).get(s),
                                long_thesis=Thesis(**theses[s]["long"]) if s in theses else None,
                                short_thesis=Thesis(**theses[s]["short"]) if s in theses else None,
                                debate=Debate(**debates[s]) if s in debates else None) for s, dec in d["decisions"].items()}
    return d, outcomes, {s: Position(**p) for s, p in (d.get("positions") or {}).items()}


def cmd_report(args: argparse.Namespace) -> int:
    """
    Re-render report.md, the debate records and the flow files from
    decisions.json; an order plan already in the run directory is shown in
    the report as it is.

    从 decisions.json 重新渲染 report.md、各品种的辩论记录和 flow 文件；运行目录里已有的订单计划按
    原样显示在报告中。
    """
    run_dir = _runs_dir(args) / args.pack_date
    d, outcomes, positions = _load_run(run_dir)
    write_outputs(run_dir, outcomes, args.pack_date, d.get("capital"), d.get("meta"), positions, d.get("config"), read_order_plan(run_dir))
    print(f"wrote {run_dir / 'report.md'}, {len(d.get('debates', {}))} debate record(s) and flow file(s)")
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    """
    Recompute the order plan of a saved run without judging again, and
    re-render the report. The daily ATR comes from decisions.json; a run
    saved before it was recorded needs `--pack` once, which also stores the
    value in its decisions.json.

    不重新判断，重算一次已保存运行的订单计划，并重新渲染报告。日线 ATR 取自 decisions.json；在记录
    该值之前保存的运行需要带一次 `--pack`，同时会把该值存进它的 decisions.json。
    """
    run_dir = _runs_dir(args) / args.pack_date
    d, outcomes, positions = _load_run(run_dir)
    atr = {s: ((d.get("meta") or {}).get(s) or {}).get("atr") for s in d["decisions"]}
    if args.pack:
        for s, ev in load_pack(Path(args.pack), list(d["decisions"])).items():
            atr[s] = atr.get(s) or ev.daily_atr
            d.setdefault("meta", {}).setdefault(s, {})["atr"] = atr[s]
        (run_dir / "decisions.json").write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")  # so the next `plan` needs no --pack
    plan = make_plan(args, run_dir, args.pack_date, {s: o.decision for s, o in outcomes.items()}, atr, positions, d.get("errors") or {})
    if plan is None:
        return 5
    write_outputs(run_dir, outcomes, args.pack_date, d.get("capital"), d.get("meta"), positions, d.get("config"), plan)
    return 0


def cmd_web(args: argparse.Namespace) -> int:
    """
    Serve the built page template and the flow files until interrupted.

    提供构建好的页面模板和 flow 数据，直到被中断。
    """
    return serve(_runs_dir(args), port=args.port)


def build_parser() -> argparse.ArgumentParser:
    """
    Build the CLI.

    构建命令行。
    """
    p = argparse.ArgumentParser(description="resonance major-timeframe judge / 大周期方向判定")
    sub = p.add_subparsers(dest="cmd", required=True)
    j = sub.add_parser("judge")
    j.add_argument("--pack", required=True, help="evidence pack dir, e.g. scratchpad/2026-09-30")
    j.add_argument("--symbols", help="comma separated variety codes (default: all in the pack)")
    j.add_argument("--account", help="td account user id (control API ?account=)")
    j.add_argument("--capital", type=float, help="account capital in CNY (overrides /api/account)")
    j.add_argument("--positions", help="JSON file with current positions (offline)")
    j.add_argument("--evidence", default="compact", choices=["compact", "full"])
    j.add_argument("--model", default="opus")
    j.add_argument("--effort", default="xhigh")
    j.add_argument("--max-rounds", type=int, default=3, choices=[1, 2, 3], help="cap on debate rounds; the moderator may stop earlier")
    j.add_argument("--workers", type=int, default=3, help="symbols judged concurrently")
    j.add_argument("--params", help="JSON overrides for ResonanceParams")
    j.add_argument("--no-cache", action="store_true")
    j.add_argument("--dry-run", action="store_true", help="judge only; no setting file")
    j.add_argument("--no-warmup", action="store_true", help="skip warm-up bars (no DB access)")
    j.add_argument("--no-reload", action="store_true", help="write the setting file but do not call the core")
    j.add_argument("--setting-out", help="explicit path of resonance_setting_<account>.json")
    runs_help = "directory for run outputs and flow data (default: strategies/resonance/runs); use the same one for every command"
    plan_cfg_help = "order plan parameter file (default: strategies/resonance/order_plan.toml)"
    plan_out_help = "also copy order_plan.json to this path"
    j.add_argument("--runs-dir", help=runs_help)
    j.add_argument("--plan-config", help=plan_cfg_help)
    j.add_argument("--plan-out", help=plan_out_help)
    j.add_argument("--no-plan", action="store_true", help="do not build the order plan")
    j.set_defaults(func=cmd_judge)
    r = sub.add_parser("report")
    r.add_argument("--pack-date", required=True)
    r.add_argument("--runs-dir", help=runs_help)
    r.set_defaults(func=cmd_report)
    pl = sub.add_parser("plan")
    pl.add_argument("--pack-date", required=True)
    pl.add_argument("--pack", help="evidence pack dir, to take the daily ATR from when decisions.json has none")
    pl.add_argument("--plan-config", help=plan_cfg_help)
    pl.add_argument("--plan-out", help=plan_out_help)
    pl.add_argument("--runs-dir", help=runs_help)
    pl.set_defaults(func=cmd_plan)
    w = sub.add_parser("web")
    w.add_argument("--port", type=int, default=8770)
    w.add_argument("--runs-dir", help=runs_help)
    w.set_defaults(func=cmd_web)
    return p


def main(argv: list[str] | None = None) -> int:
    """
    CLI entry point.

    命令行入口。
    """
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
