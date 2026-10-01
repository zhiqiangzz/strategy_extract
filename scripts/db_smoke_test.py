#!/usr/bin/env python3
"""
Agents: read the English part of every docstring only. 中文段落仅供人类阅读。

db_smoke_test.py — connectivity and API smoke test for the database package of
third_party/quant_trading (``futures_quant_database_v2``).

Run from the repo root with ``uv run python scripts/db_smoke_test.py``. The
package reads its connection settings from the git-ignored ``.env`` in the
current working directory (or ``DATABASE_V2_ENV_FILE``). The test performs
read-only queries only: a raw ``SELECT 1`` and server version, the list of
varieties, the trading calendar range, the current main contract per variety,
a daily market-data pull for one variety over the last 30 calendar days, and
an intraday pull. Each step prints PASS/FAIL with a one-line summary; the exit
code is non-zero if any step failed. The optional ``--variety`` flag selects
the variety used for the market-data steps (default: the first variety).

db_smoke_test.py 是 third_party/quant_trading 数据库包（``futures_quant_database_v2``）
的连通性与接口冒烟测试。在仓库根目录运行 ``uv run python scripts/db_smoke_test.py``。
连接参数由当前目录下被 git 忽略的 ``.env``（或 ``DATABASE_V2_ENV_FILE``）提供。测试只做
只读查询：``SELECT 1`` 与服务器版本、品种列表、交易日历范围、各品种当前主力合约、某品种
最近 30 天日行情、以及一次日内行情读取。每步打印 PASS/FAIL 与一行摘要，任一步失败则退出码
非零。``--variety`` 可指定行情步骤使用的品种（默认第一个品种）。
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import date, timedelta


def step(name: str, fn):
    """
    Run one check, print PASS/FAIL with timing and a short summary, and
    return (ok, result).

    执行一项检查，打印 PASS/FAIL、耗时和一行摘要，返回 (是否通过, 结果)。
    """
    t0 = time.perf_counter()
    try:
        result, summary = fn()
        print(f"PASS  {name:<28} {time.perf_counter() - t0:6.2f}s  {summary}")
        return True, result
    except Exception as exc:  # noqa: BLE001 - a smoke test reports everything
        print(f"FAIL  {name:<28} {time.perf_counter() - t0:6.2f}s  {type(exc).__name__}: {str(exc)[:160]}")
        return False, None


def main(argv: list[str] | None = None) -> int:
    """
    CLI entry point; returns the process exit code.

    命令行入口；返回进程退出码。
    """
    ap = argparse.ArgumentParser(description="quant_trading DB smoke test / 数据库冒烟测试")
    ap.add_argument("--variety", help="variety code or Chinese name for the market-data steps")
    args = ap.parse_args(argv)

    from sqlalchemy import text

    from futures_quant_database_v2 import api, crud
    from futures_quant_database_v2.core.config import settings
    from futures_quant_database_v2.core.db import session_scope

    host = f"{settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB_V2 or settings.POSTGRES_DB}"
    print(f"target: {host} as {settings.POSTGRES_USER}")
    results: list[bool] = []

    def raw_connect():
        with session_scope() as s:
            one = s.execute(text("SELECT 1")).scalar()
            ver = s.execute(text("SHOW server_version")).scalar()
            n_tables = s.execute(text("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")).scalar()
        assert one == 1
        return ver, f"PostgreSQL {ver}, {n_tables} public tables"

    ok, _ = step("connect + SELECT 1", raw_connect); results.append(ok)
    if not ok:
        print("connection failed; skipping API checks")
        return 1

    def varieties():
        rows = crud.get_futures_contexts()
        names = ", ".join(f"{r['variety_code']}({r['variety_name']})" for r in rows[:6])
        return rows, f"{len(rows)} varieties: {names}{' …' if len(rows) > 6 else ''}"

    ok, vrows = step("futures list", varieties); results.append(ok)

    def calendar():
        df = api.get_cn_trading_calendar_df()
        col = df.columns[0]
        return df, f"{len(df)} trading days, {df[col].min()} → {df[col].max()}"

    ok, _ = step("trading calendar", calendar); results.append(ok)

    def mains():
        rows = crud.get_main_contracts()
        sample = ", ".join(f"{r['variety_code']}→{r['contract_code']}" for r in rows[:5])
        return rows, f"{len(rows)} current mains: {sample}{' …' if len(rows) > 5 else ''}"

    ok, mrows = step("current main contracts", mains); results.append(ok)

    variety = args.variety or (vrows[0]["variety_code"] if vrows else None)
    end = date.today(); begin = end - timedelta(days=30)

    def daily():
        df = api.get_daily_market_data_df(begin_date=begin, end_date=end, varieties=[variety])
        last = df.iloc[-1] if len(df) else None
        tail = f"last {last['交易日期'].date()} {last['合约代码']} close={last['收盘价']}" if last is not None else "no rows"
        return df, f"{variety}: {len(df)} daily rows {begin}→{end}; {tail}"

    ok, _ = step("daily market data (api)", daily); results.append(ok)

    def intraday():
        df = api.get_intraday_market_data_df(begin_date=end - timedelta(days=7), end_date=end, varieties=[variety])
        return df, f"{variety}: {len(df)} intraday rows in last 7 days, columns={list(df.columns)[:6]}"

    ok, _ = step("intraday market data (api)", intraday); results.append(ok)

    def metrics():
        df = api.get_trading_metrics_df(begin_date=begin, end_date=end, varieties=[variety])
        return df, f"{variety}: {len(df)} trading-metric rows (multiplier/margin)"

    ok, _ = step("trading metrics (api)", metrics); results.append(ok)

    failed = results.count(False)
    print(f"\n{len(results) - failed}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
