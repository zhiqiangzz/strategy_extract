"""
Agents: read the English part only. 中文仅供人类阅读。

signal_writer.py — turn decisions into `resonance_setting_<account>.json`
and hand it to the Rust strategy.

For every judged variety it resolves today's main contract and exchange from
the v2 database (`crud.get_main_contract_as_of`), the contract multiplier and
price tick from `VARIETY_META` (the same values as rust_core's
`core_model::contract`), the risk budget (`capital × per_trade_loss_ratio`,
T004/T023), and the warm-up bars the Rust strategy needs before it can
signal: the last `entry_lookback + atr_period + 5` 30-minute bars from
`tick_ctp` (`api.klines.get_tick_ctp_klines`) and the last
`trail_lookback_days + atr_period + 5` daily bars from `market_data`
(`crud.get_daily_market_data_rows`). The file is validated through
`ResonanceSetting`, written atomically, and unless `--no-reload` the core is
told to reload via `POST /api/strategy/reload?account=`.

signal_writer.py 把决策写成 `resonance_setting_<account>.json` 并交给 Rust 策略。对每个已判断的
品种：从 v2 库取当日主力合约与交易所（`crud.get_main_contract_as_of`），从 `VARIETY_META` 取合约乘数
与最小变动价位（与 rust_core 的 `core_model::contract` 一致），算风险预算（本金 × 单笔风险比例，
T004/T023），并准备 Rust 策略出信号前所需的预热 K 线：`tick_ctp` 最近 `entry_lookback + atr_period
+ 5` 根 30 分钟 K 线（`api.klines.get_tick_ctp_klines`）和 `market_data` 最近 `trail_lookback_days +
atr_period + 5` 根日线（`crud.get_daily_market_data_rows`）。文件经 `ResonanceSetting` 校验后原子
写出，除非 `--no-reload`，否则通过 `POST /api/strategy/reload?account=` 通知 core 重载。
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from .config import ResonanceParams
from .debate import JudgeOutcome
from .schemas import ContractSetting, ResonanceSetting, Warmup

# variety code -> (exchange, price_tick, multiplier); values from rust_core core_model::contract / exchange
# 品种代码 -> (交易所, 最小变动价位, 合约乘数)；取值与 rust_core 的 core_model::contract / exchange 一致
VARIETY_META: dict[str, tuple[str, float, float]] = {
    "LC": ("GFEX", 20.0, 1.0), "SI": ("GFEX", 5.0, 5.0),
    "AG": ("SHFE", 1.0, 15.0), "CU": ("SHFE", 10.0, 5.0), "SN": ("SHFE", 10.0, 1.0), "NI": ("SHFE", 10.0, 1.0),
    "RU": ("SHFE", 5.0, 10.0), "AO": ("SHFE", 1.0, 20.0), "RB": ("SHFE", 1.0, 10.0),
    "SA": ("CZCE", 1.0, 20.0), "SH": ("CZCE", 1.0, 30.0), "MA": ("CZCE", 1.0, 10.0), "FG": ("CZCE", 1.0, 20.0), "TA": ("CZCE", 2.0, 5.0),
    "JM": ("DCE", 0.5, 60.0), "M": ("DCE", 1.0, 10.0), "P": ("DCE", 2.0, 10.0), "I": ("DCE", 0.5, 100.0),
}


def vt_symbol_for(code: str, exchange: str, contract_code: str) -> str:
    """
    DB contract code (e.g. "CU2611", "MA2610") -> vt_symbol ("cu2611.SHFE",
    "MA610.CZCE"), following the converter rule in quant_trading
    (CZCE: upper code + 3-digit month; others: lower code + 4 digits).

    DB 合约代码 -> vt_symbol，规则同 quant_trading 的转换脚本（CZCE 大写码 + 3 位月份；其他小写码 +
    4 位）。
    """
    digits = "".join(ch for ch in contract_code if ch.isdigit())
    if exchange == "CZCE":
        return f"{code.upper()}{digits[-3:]}.{exchange}"
    return f"{code.lower()}{digits[-4:]}.{exchange}"


def resolve_contract(variety_code: str, as_of: date) -> Optional[dict]:
    """
    Today's main contract for a variety from the v2 DB:
    {contract_code, exchange_code, contract_id, vt_symbol}. None when the
    DB has no registration.

    从 v2 库取某品种当日主力合约：{contract_code, exchange_code, contract_id, vt_symbol}；未登记
    返回 None。
    """
    from futures_quant_database_v2 import crud
    main = crud.get_main_contract_as_of(variety_code, as_of)
    if not main:
        return None
    code = main["contract_code"]
    exchange = main.get("exchange_code") or VARIETY_META.get(variety_code, ("", 0, 0))[0]
    ids = crud.get_all_contract_code_ids()
    return {"contract_code": code, "exchange_code": exchange, "contract_id": ids.get(code),
            "vt_symbol": vt_symbol_for(variety_code, exchange, code)}


def warmup_bars(variety_code: str, contract: dict, params: ResonanceParams, as_of: date) -> Warmup:
    """
    30m bars from tick_ctp for the main contract and daily bars from
    market_data, oldest first, in the compact list shapes the Rust strategy
    parses. Missing data yields empty lists (the strategy then warms up
    from live ticks).

    从 tick_ctp 取主力合约 30 分钟 K 线、从 market_data 取日线，按时间升序，使用 Rust 策略解析的
    紧凑列表形状。缺数据时为空列表（策略改用实时 tick 预热）。
    """
    from futures_quant_database_v2 import crud
    from futures_quant_database_v2.api import klines
    w = Warmup()
    n30 = params.entry_lookback + params.atr_period + 5
    if contract.get("contract_id"):
        try:
            # bars strictly up to the end of `as_of` (no look-ahead when building replay settings) / 只取 as_of 当日及之前
            end_dt = datetime.combine(as_of, datetime.max.time())
            rows = klines.get_tick_ctp_klines(contract["contract_id"], tf="30m", end=end_dt, limit=n30)
            w.bars_30m = [[int(r["epoch"]), float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]), int(r.get("volume") or 0)] for r in rows][-n30:]
        except Exception:  # noqa: BLE001 - warm-up is best effort
            w.bars_30m = []
    nd = params.trail_lookback_days + params.atr_period + 5
    try:
        rows = crud.get_daily_market_data_rows([variety_code], begin=as_of - timedelta(days=nd * 3), end=as_of, is_index=False, contract_codes=None)
        rows = sorted(rows, key=lambda r: r["trading_date"])[-nd:]
        w.bars_1d = [[str(r["trading_date"]), float(r["open_price"]), float(r["high_price"]), float(r["low_price"]), float(r["close_price"]), int(r.get("volume") or 0)] for r in rows]
    except Exception:  # noqa: BLE001
        w.bars_1d = []
    return w


def build_setting(outcomes: dict[str, JudgeOutcome], account: str, pack_date: str, capital: float, params: ResonanceParams,
                  as_of: Optional[date] = None, with_warmup: bool = True, log=print) -> tuple[ResonanceSetting, list[dict]]:
    """
    Assemble the setting file for all judged varieties. Returns the setting
    and a list of skipped varieties with reasons.

    为全部已判断品种组装设置文件；返回设置与被跳过的品种及原因。
    """
    as_of = as_of or date.today()
    contracts: dict[str, ContractSetting] = {}
    skipped: list[dict] = []
    for sym, oc in outcomes.items():
        meta = VARIETY_META.get(sym)
        if meta is None:
            skipped.append({"symbol": sym, "reason": "no VARIETY_META (multiplier/price_tick)"}); continue
        contract = resolve_contract(sym, as_of)
        if contract is None:
            skipped.append({"symbol": sym, "reason": "no main contract registered in v2 DB"}); continue
        warm = warmup_bars(sym, contract, params, as_of) if with_warmup else Warmup()
        contracts[contract["vt_symbol"]] = ContractSetting(
            variety_code=sym, variety_name=oc.verdicts.get("name", "") or sym, decision_id=f"{pack_date}/{sym}",
            direction=oc.decision.direction, confidence=oc.decision.confidence, reversal=bool(oc.decision.reversal),
            risk_budget_cny=round(capital * params.per_trade_loss_ratio, 2), multiplier=meta[2], price_tick=meta[1],
            params=params, warmup=warm, note=(oc.decision.reasoning or "")[:300])
        log(f"[setting] {sym} -> {contract['vt_symbol']} dir={oc.decision.direction} conf={oc.decision.confidence:.2f} reversal={oc.decision.reversal} warmup 30m={len(warm.bars_30m)} 1d={len(warm.bars_1d)}")
    setting = ResonanceSetting(generated_at=datetime.now().astimezone().isoformat(timespec="seconds"), pack_date=pack_date,
                               account=account, contracts=contracts)
    return setting, skipped


def write_setting(setting: ResonanceSetting, path: Path) -> Path:
    """
    Atomic JSON write (tmp file + rename).

    原子写 JSON（临时文件 + 重命名）。
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(setting.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def reload_core(base_url: str, account: Optional[str], timeout: int = 15) -> dict:
    """
    POST /api/strategy/reload?account= and return the core's JSON reply.

    调用 POST /api/strategy/reload?account= 并返回 core 的 JSON 响应。
    """
    q = f"?account={account}" if account else ""
    req = urllib.request.Request(f"{base_url}/api/strategy/reload{q}", method="POST", data=b"{}", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))
