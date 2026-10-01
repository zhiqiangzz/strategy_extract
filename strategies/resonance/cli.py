"""
Agents: read the English part only. 中文仅供人类阅读。

cli.py — command-line entry points.

    uv run python -m strategies.resonance.cli judge --pack scratchpad/2026-09-29 --symbols CU,LC --account 123456 [--dry-run] [--no-reload] [--capital 1000000] [--positions file.json] [--evidence compact|full] [--no-cache]
    uv run python -m strategies.resonance.cli report --pack-date 2026-09-29

`judge` loads the evidence pack, fetches positions and capital from the
control API (or from `--positions` / `--capital`), runs the debate per
symbol, writes `runs/<date>/decisions.json` and `report.md`, and, unless
`--dry-run`, builds the setting file (with DB lookups and warm-up bars),
writes it to the vntrader directory (`--setting-out`, default
`third_party/quant_trading/rust_core/.vntrader/resonance_setting_<account>.json`)
and asks the core to reload (`--no-reload` skips that). `report` re-renders
the Markdown report from a saved decisions.json.

cli.py 是命令行入口。`judge` 读取证据包、从 control API（或 `--positions` / `--capital`）取持仓与
资金、逐品种辩论、写出 `runs/<日期>/decisions.json` 与 `report.md`；除非 `--dry-run`，否则组装设置
文件（含 DB 查询与预热 K 线）、写入 vntrader 目录（`--setting-out`，默认
`third_party/quant_trading/rust_core/.vntrader/resonance_setting_<账户>.json`）并通知 core 重载
（`--no-reload` 跳过）。`report` 从保存的 decisions.json 重新渲染 Markdown 报告。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from .config import REPO_ROOT, JudgeConfig, ResonanceParams
from .debate import JudgeOutcome, judge_many
from .evidence import load_pack
from .positions import from_control_api, from_file
from .schemas import Decision
from .signal_writer import build_setting, reload_core, write_setting


def render_report(outcomes: dict[str, JudgeOutcome], pack_date: str, capital: float | None) -> str:
    """
    Markdown report: one table row per symbol with the four agents' verdicts
    and the manager decision, then each decision's reasoning.

    Markdown 报告：每品种一行（四个代理的结论与 Manager 决策），之后是每个决策的理由。
    """
    L = [f"# Resonance major-timeframe decisions — pack {pack_date}", "",
         f"Generated {datetime.now().astimezone().isoformat(timespec='seconds')}; capital {capital}; "
         f"total cost ${sum(o.cost_usd for o in outcomes.values()):.2f}; cached {sum(1 for o in outcomes.values() if o.cached)}/{len(outcomes)}", "",
         "| symbol | A1 | A2 | A3 | A4 | **decision** | conf | reversal | quality |", "|---|---|---|---|---|---|---|---|---|"]
    for sym in sorted(outcomes):
        o = outcomes[sym]; v = o.verdicts; d = o.decision
        L.append(f"| {sym} | {v.get('A1', '-')} | {v.get('A2', '-')} | {v.get('A3', '-')} | {v.get('A4', '-')} | **{d.direction}** | {d.confidence:.2f} | {d.reversal} | {d.evidence_quality}{' ERROR' if o.error else ''} |")
    L.append("")
    for sym in sorted(outcomes):
        o = outcomes[sym]; d = o.decision
        L += [f"## {sym} — {d.direction} ({d.confidence:.2f})", "", d.reasoning, "",
              f"- key drivers: {', '.join(d.key_drivers)}", f"- risk flags: {', '.join(d.risk_flags) or '-'}",
              f"- uncertain_is_high_confidence: {d.uncertain_is_high_confidence}; reversal: {d.reversal}; cost ${o.cost_usd:.2f}; {o.duration_s:.0f}s" + (f"; error: {o.error}" if o.error else ""), ""]
        if o.cross_exam:
            L += ["<details><summary>cross-examination net assessment</summary>", "", o.cross_exam.net_assessment, "",
                  f"unresolved: {o.cross_exam.unresolved_conflicts}", f"caveats: {o.cross_exam.data_quality_caveats}", "", "</details>", ""]
    return "\n".join(L)


def cmd_judge(args: argparse.Namespace) -> int:
    """
    The `judge` command; returns the exit code.

    `judge` 命令；返回退出码。
    """
    cfg = JudgeConfig(model=args.model, effort=args.effort, evidence_level=args.evidence, max_workers=args.workers, use_cache=not args.no_cache)
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
    print(f"[judge] pack {next(iter(evidences.values())).pack_date}: {len(evidences)} symbols, model {cfg.model}/{cfg.effort}, evidence {cfg.evidence_level}, workers {cfg.max_workers}")
    outcomes = judge_many(evidences, positions, cfg, params,
                          on_done=lambda o: print(f"[judge] {o.symbol}: {o.decision.direction} conf={o.decision.confidence:.2f} reversal={o.decision.reversal} ${o.cost_usd:.2f}{' (cached)' if o.cached else ''}{' ERROR ' + o.error if o.error else ''}"))
    pack_date = next(iter(evidences.values())).pack_date
    run_dir = cfg.runs_dir / pack_date
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "decisions.json").write_text(json.dumps(
        {"pack_date": pack_date, "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"), "capital": capital,
         "positions": {k: v.model_dump() for k, v in positions.items()},
         "decisions": {s: o.decision.model_dump() for s, o in outcomes.items()},
         "verdicts": {s: o.verdicts for s, o in outcomes.items()},
         "cost_usd": {s: o.cost_usd for s, o in outcomes.items()}, "errors": {s: o.error for s, o in outcomes.items() if o.error}},
        ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "report.md").write_text(render_report(outcomes, pack_date, capital), encoding="utf-8")
    print(f"[judge] wrote {run_dir / 'decisions.json'} and report.md; total cost ${sum(o.cost_usd for o in outcomes.values()):.2f}")
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


def cmd_report(args: argparse.Namespace) -> int:
    """
    Re-render report.md from decisions.json.

    从 decisions.json 重新渲染 report.md。
    """
    cfg = JudgeConfig()
    run_dir = cfg.runs_dir / args.pack_date
    d = json.loads((run_dir / "decisions.json").read_text(encoding="utf-8"))
    outcomes = {s: JudgeOutcome(symbol=s, decision=Decision(**dec), cost_usd=d.get("cost_usd", {}).get(s, 0.0), verdicts=d.get("verdicts", {}).get(s, {}),
                                error=d.get("errors", {}).get(s)) for s, dec in d["decisions"].items()}
    (run_dir / "report.md").write_text(render_report(outcomes, args.pack_date, d.get("capital")), encoding="utf-8")
    print(f"wrote {run_dir / 'report.md'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """
    Build the CLI.

    构建命令行。
    """
    p = argparse.ArgumentParser(description="resonance major-timeframe judge / 大周期方向判定")
    sub = p.add_subparsers(dest="cmd", required=True)
    j = sub.add_parser("judge")
    j.add_argument("--pack", required=True, help="A5 output dir, e.g. scratchpad/2026-09-29")
    j.add_argument("--symbols", help="comma separated variety codes (default: all in the pack)")
    j.add_argument("--account", help="td account user id (control API ?account=)")
    j.add_argument("--capital", type=float, help="account capital in CNY (overrides /api/account)")
    j.add_argument("--positions", help="JSON file with current positions (offline)")
    j.add_argument("--evidence", default="compact", choices=["compact", "full"])
    j.add_argument("--model", default="opus")
    j.add_argument("--effort", default="xhigh")
    j.add_argument("--workers", type=int, default=3)
    j.add_argument("--params", help="JSON overrides for ResonanceParams")
    j.add_argument("--no-cache", action="store_true")
    j.add_argument("--dry-run", action="store_true", help="judge only; no setting file")
    j.add_argument("--no-warmup", action="store_true", help="skip warm-up bars (no DB access)")
    j.add_argument("--no-reload", action="store_true", help="write the setting file but do not call the core")
    j.add_argument("--setting-out", help="explicit path of resonance_setting_<account>.json")
    j.set_defaults(func=cmd_judge)
    r = sub.add_parser("report")
    r.add_argument("--pack-date", required=True)
    r.set_defaults(func=cmd_report)
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
