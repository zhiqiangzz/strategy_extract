"""
Agents: read the English part only. 中文仅供人类阅读。

export_ticks.py — export ticks of one contract from `tick_ctp` into the JSON
shape consumed by the Rust replay example (`resonance_replay`).

    uv run python -m strategies.resonance.export_ticks --variety CU --begin 2026-09-22 --end 2026-09-26 --out /tmp/ticks_cu.json [--contract cu2611.SHFE]

Resolves the main contract as of `--end` (or takes `--contract`), reads the
raw ticks through `crud.get_tick_ctp_binned` is not enough (no volume), so
it queries the `tick_ctp` table directly with a session, and writes
`{"vt_symbol", "ticks": [{epoch, trading_day, last, volume, bid1, ask1}]}`.
`epoch` is real UTC seconds derived from the naive Shanghai `event_time`.

export_ticks.py 把 `tick_ctp` 中某合约的 tick 导出为 Rust 回放示例（`resonance_replay`）使用的 JSON。
按 `--end` 解析主力合约（或用 `--contract`），直接查 `tick_ctp` 表，写出
`{"vt_symbol", "ticks": [{epoch, trading_day, last, volume, bid1, ask1}]}`；`epoch` 为由上海时间
`event_time` 换算的真实 UTC 秒。
"""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .signal_writer import resolve_contract

CN = timezone(timedelta(hours=8))


def export(variety: str, begin: date, end: date, out: Path, contract: str | None = None) -> int:
    """
    Query ticks and write the JSON file; returns the tick count.

    查询 tick 并写出 JSON；返回 tick 数。
    """
    from sqlalchemy import text

    from futures_quant_database_v2 import crud
    from futures_quant_database_v2.core.db import session_scope
    if contract:
        code = contract.split(".")[0].upper()
        ids = crud.get_all_contract_code_ids()
        cid = ids.get(code) or ids.get(code.lower())
        vt = contract
    else:
        c = resolve_contract(variety.upper(), end)
        if c is None:
            raise SystemExit(f"no main contract for {variety} as of {end}")
        cid, vt = c["contract_id"], c["vt_symbol"]
    if cid is None:
        raise SystemExit("contract id not found")
    sql = text("""SELECT trading_day, event_time, last_price, volume, bid1_price, ask1_price FROM tick_ctp
                  WHERE contract_id = :cid AND trading_day BETWEEN :lo AND :hi ORDER BY event_time""")
    ticks = []
    with session_scope() as s:
        for row in s.execute(sql, {"cid": cid, "lo": begin, "hi": end}).mappings():
            et: datetime = row["event_time"]
            epoch = int(et.replace(tzinfo=CN).timestamp()) if et.tzinfo is None else int(et.timestamp())
            ticks.append({"epoch": epoch, "trading_day": str(row["trading_day"]), "last": float(row["last_price"] or 0),
                          "volume": int(row["volume"] or 0), "bid1": float(row["bid1_price"] or 0), "ask1": float(row["ask1_price"] or 0)})
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"vt_symbol": vt, "ticks": ticks}, ensure_ascii=False), encoding="utf-8")
    return len(ticks)


def main(argv: list[str] | None = None) -> int:
    """
    CLI entry point.

    命令行入口。
    """
    ap = argparse.ArgumentParser(description="export tick_ctp ticks for the Rust replay / 导出 tick 供回放")
    ap.add_argument("--variety", required=True)
    ap.add_argument("--begin", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--contract")
    a = ap.parse_args(argv)
    n = export(a.variety, date.fromisoformat(a.begin), date.fromisoformat(a.end), Path(a.out), a.contract)
    print(f"wrote {n} ticks to {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
