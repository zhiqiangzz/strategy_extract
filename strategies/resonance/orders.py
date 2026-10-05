"""
Agents: read the English part only. 中文仅供人类阅读。

orders.py — turn the manager's decisions into an order plan for the trading
system.

The manager decides direction and confidence. This module computes every
number of an order from the parameter file `order_plan.toml`
(`OrderPlanConfig`), the database (`DbMarketData`: main contract, margin
ratio, lot size, last trade before the decision time) and the evidence pack
(daily ATR), so the same inputs always give the same plan.

`build_order_plan` applies these rules to each symbol:

- Flat and long/short: one `open` order. The entry range is the reference
  price ± `range_atr` daily ATRs, written as `limit_price = [low, high]`;
  the trading system may enter anywhere inside it on the minor timeframe.
  Lots are the smaller of what the margin budget (`budget × confidence`)
  buys at the top of the range and what keeps the stop at least
  `min_stop_atr` daily ATRs away. The stop is placed so that a fill at the
  worst price of the range (the top for a buy, the bottom for a sell) loses
  at most the loss limit (`max_loss_cny × confidence`); any other fill
  inside the range loses less.
- Uncertain: no order.
- Open position and reversal: one `close` order for the position, and when
  the new direction is the opposite one, an `open` order that depends on it.
- Open position in the same direction: no order.

It returns the plan (`schemas.OrderPlan`, the exact file format), how each
order was sized (`sizing`) and why a symbol got no order (`skipped`).
`write_order_plan` writes `order_plan.json` and `order_plan.audit.json`.

orders.py 把 Manager 的决策变成交给交易系统的订单计划。Manager 决定方向和置信度；本模块根据参数文件
`order_plan.toml`（`OrderPlanConfig`）、数据库（`DbMarketData`：主力合约、保证金比率、每手数量、决策
时点之前的最后一笔成交）和证据包（日线 ATR）算出订单里的每个数字，相同输入必得相同计划。
`build_order_plan` 对每个品种应用以下规则：空仓且方向为多/空时出一张 `open` 单，入场区间为参考价 ±
`range_atr` 倍日线 ATR，写成 `limit_price = [下沿, 上沿]`，交易系统可在小周期上于区间内任意位置入场；
手数取"保证金预算（预算 × 置信度）在区间上沿能买的手数"与"使止损距离不小于 `min_stop_atr` 倍日线
ATR 的手数"中较小者；止损的位置保证按区间内最差价（买单为上沿，卖单为下沿）成交时亏损不超过亏损上限
（`max_loss_cny × 置信度`），区间内其他位置成交亏损更小。方向不确定时不出单。有持仓且判定反转时出一张 `close`
单，新方向相反时再出一张依赖它的 `open` 单。有持仓且方向一致时不出单。返回订单计划
（`schemas.OrderPlan`，即文件格式本身）、每张单的计算明细（`sizing`）和未出单原因（`skipped`）。
`write_order_plan` 写出 `order_plan.json` 和 `order_plan.audit.json`。
"""
from __future__ import annotations

import json
import math
import tomllib
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Optional, Protocol
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

from .config import PACKAGE_DIR
from .schemas import Decision, Order, OrderPlan, Position
from .signal_writer import VARIETY_META, resolve_contract

SHANGHAI = ZoneInfo("Asia/Shanghai")
DEFAULT_PLAN_CONFIG = PACKAGE_DIR / "order_plan.toml"
PLAN_FILE, AUDIT_FILE = "order_plan.json", "order_plan.audit.json"
SIDE_OF = {"long": "buy", "short": "sell"}
DIRECTION_ZH = {"long": "做多", "short": "做空"}


class _Section(BaseModel):
    """
    Base of the config sections: an unknown key is an error.

    各配置段的基类：出现未知的键即报错。
    """
    model_config = ConfigDict(extra="forbid")


class BudgetConfig(_Section):
    """
    `[budget]`: margin budget per symbol.

    `[budget]`：每个品种的保证金预算。
    """
    default_cny: float = Field(100_000, gt=0)
    scale_by_confidence: bool = True
    min_confidence: float = Field(0.0, ge=0, le=1)
    symbols: dict[str, float] = Field(default_factory=dict)


class RiskConfig(_Section):
    """
    `[risk]`: largest loss of one order and the floor of the stop distance.

    `[risk]`：单笔订单的最大亏损和止损距离的下限。
    """
    max_loss_cny: float = Field(15_000, gt=0)
    scale_by_confidence: bool = True
    min_stop_atr: float = Field(1.0, ge=0)


class EntryConfig(_Section):
    """
    `[entry]`: width of the entry range and the decision time.

    `[entry]`：入场区间的宽度和决策时点。
    """
    range_atr: float = Field(0.25, ge=0)
    decision_clock: str = "09:00:00"


class MarginConfig(_Section):
    """
    `[margin]`: surcharge on the database's margin ratio.

    `[margin]`：在数据库保证金比率之上的加收。
    """
    addon: float = Field(0.0, ge=0, lt=1)


class OrderFieldsConfig(_Section):
    """
    `[order]`: fixed fields of every order and of the plan.

    `[order]`：每张订单及计划本身的固定字段。
    """
    strategy_id: str = "major_minor_timeframe_resonance"
    source: str = "manager"
    plan_id_prefix: str = "manager"
    plan_version: int = 1
    target_r: float = Field(3.0, ge=0)
    hold_overnight: bool = True
    valid_until_clock: str = "15:00:00"


class OrderPlanConfig(_Section):
    """
    The whole parameter file `order_plan.toml`.

    整个参数文件 `order_plan.toml`。
    """
    budget: BudgetConfig = Field(default_factory=BudgetConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    entry: EntryConfig = Field(default_factory=EntryConfig)
    margin: MarginConfig = Field(default_factory=MarginConfig)
    order: OrderFieldsConfig = Field(default_factory=OrderFieldsConfig)


def load_plan_config(path: Optional[Path] = None) -> OrderPlanConfig:
    """
    Read the parameter file (default: `order_plan.toml` next to this module).

    读取参数文件（默认是本模块旁边的 `order_plan.toml`）。
    """
    with open(path or DEFAULT_PLAN_CONFIG, "rb") as fh:
        return OrderPlanConfig(**tomllib.load(fh))


@dataclass
class Quote:
    """
    What the plan needs to know about one variety at the decision time.

    订单计划在决策时点需要知道的一个品种的信息。
    """
    contract: str
    price: float
    price_time: str
    multiplier: float
    margin_ratio: float


class MarketData(Protocol):
    """
    Source of quotes; `quote` raises LookupError with the reason when a
    piece is missing.

    行情来源；缺少某项数据时 `quote` 抛出带原因的 LookupError。
    """

    def quote(self, variety: str, as_of: datetime) -> Quote:
        """Quote of a variety's main contract as of a moment.

        某品种主力合约在某一时刻的行情。
        """
        ...


class DbMarketData:
    """
    Quotes from the v2 database: main contract of the day
    (`signal_writer.resolve_contract`), lot size and margin ratio
    (`crud.get_trading_metric_as_of`) and the close of the last one-minute
    bar that ends before `as_of` (`klines.get_tick_ctp_klines`).

    来自 v2 数据库的行情：当日主力合约（`signal_writer.resolve_contract`）、每手数量与保证金比率
    （`crud.get_trading_metric_as_of`），以及 `as_of` 之前最后一根一分钟 K 线的收盘价
    （`klines.get_tick_ctp_klines`）。
    """

    def quote(self, variety: str, as_of: datetime) -> Quote:
        """Look the variety up; LookupError names what is missing.

        查询该品种；缺什么由 LookupError 指明。
        """
        from futures_quant_database_v2 import crud
        from futures_quant_database_v2.api import klines
        local = as_of.astimezone(SHANGHAI).replace(tzinfo=None)
        contract = resolve_contract(variety, local.date())
        if not contract or not contract.get("contract_id"):
            raise LookupError("数据库中没有该日的主力合约")
        metric = crud.get_trading_metric_as_of(variety, local.date()) or {}
        if not metric.get("margin_ratio") or not metric.get("num_per_hand"):
            raise LookupError("数据库中没有保证金比率或每手数量")
        bars = klines.get_tick_ctp_klines(contract["contract_id"], tf="1m", end=local - timedelta(seconds=1), limit=1)
        if not bars:
            raise LookupError(f"{contract['contract_code']} 在 {local:%Y-%m-%d %H:%M} 之前没有成交")
        return Quote(contract=str(contract["contract_code"]).upper(), price=float(bars[-1]["close"]), price_time=str(bars[-1]["dt"]),
                     multiplier=float(metric["num_per_hand"]), margin_ratio=float(metric["margin_ratio"]))


@dataclass
class PlanResult:
    """
    The plan, how each open order was sized, and the symbols without an order.

    订单计划、每张开仓单的计算明细，以及未出单的品种。
    """
    plan: OrderPlan
    sizing: list[dict] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)
    as_of: str = ""


def _floor(x: float, tick: float) -> float:
    """
    Largest multiple of `tick` not above `x`.

    不超过 `x` 的最大 tick 整数倍。
    """
    return round(float(math.floor(x / tick + 1e-9) * tick), 6)


def _ceil(x: float, tick: float) -> float:
    """
    Smallest multiple of `tick` not below `x`.

    不小于 `x` 的最小 tick 整数倍。
    """
    return round(float(math.ceil(x / tick - 1e-9) * tick), 6)


def size_open(side: str, price: float, atr: float, multiplier: float, margin_ratio: float, tick: float, budget_cny: float,
              loss_limit_cny: float, cfg: OrderPlanConfig) -> dict:
    """
    Size one opening order for a margin budget and a loss limit (both
    already scaled by confidence where the parameters say so). Returns the
    entry range, lots, stop, target and the figures behind them, or
    `{"skip": reason}` when not even one lot fits. Invariants of a sized
    order: the loss of a fill at the worst price of the range that is then
    stopped out is at most `loss_limit_cny`; the margin at the top of the
    range is at most `budget_cny`; the stop lies outside the range on the
    losing side; every price is on the tick grid.

    按给定的保证金预算和亏损上限（两者已按参数乘过置信度）计算一张开仓单。返回入场区间、手数、止损、
    目标及其依据的数字；连一手都放不下时返回 `{"skip": 原因}`。已定手数的订单满足：按区间内最差价成交
    后被止损的亏损不超过 `loss_limit_cny`；按区间上沿计算的保证金不超过 `budget_cny`；止损在区间之外
    且位于亏损一侧；所有价格都落在最小变动价位上。
    """
    buy = side == "buy"
    ratio = margin_ratio + cfg.margin.addon
    max_loss, min_stop = loss_limit_cny, cfg.risk.min_stop_atr * atr
    half = cfg.entry.range_atr * atr
    low, high = _ceil(price - half, tick), _floor(price + half, tick)
    if low > high:
        low = high = _floor(price + tick / 2, tick)
    lots_margin = math.floor(budget_cny / (high * multiplier * ratio) + 1e-9)
    lots_risk = math.floor(max_loss / (min_stop * multiplier) + 1e-9) if min_stop > 0 else None
    lots = lots_margin if lots_risk is None else min(lots_margin, lots_risk)
    if lots < 1:
        if lots_margin < 1:
            return {"skip": f"预算 {budget_cny:.0f} 元不足一手保证金 {high * multiplier * ratio:.0f} 元"}
        return {"skip": f"一手按 {cfg.risk.min_stop_atr:g} 倍日线 ATR 止损的亏损 {min_stop * multiplier:.0f} 元超过上限 {max_loss:.0f} 元"}
    dist = max_loss / (lots * multiplier)
    for _ in range(2):
        worst = high if buy else low
        stop = _ceil(worst - dist, tick) if buy else _floor(worst + dist, tick)
        if (stop < low) if buy else (stop > high):
            break
        # the stop fell inside the range: narrow the range until it lies one tick beyond the far edge
        # 止损落进了区间：收窄区间，直到止损在远端之外一个最小变动价位
        half = max(0.0, (dist - tick) / 2)
        low, high = _ceil(price - half, tick), _floor(price + half, tick)
        if low > high:
            low = high = _floor(price + tick / 2, tick)
    else:
        return {"skip": f"止损距离 {dist:g} 不足一个最小变动价位 {tick:g}"}
    if buy and stop <= 0:
        stop = tick
    target = None
    if cfg.order.target_r > 0:
        raw = worst + (1 if buy else -1) * cfg.order.target_r * dist
        target = _floor(raw + tick / 2, tick) if raw > 0 else None
    return {"low": low, "high": high, "worst": worst, "lots": lots, "lots_by_margin": lots_margin, "lots_by_risk": lots_risk,
            "limited_by": "止损下限" if lots_risk is not None and lots_risk < lots_margin else "保证金",
            "stop": stop, "target": target, "stop_distance": round(abs(worst - stop), 6), "stop_atr": round(abs(worst - stop) / atr, 2) if atr else None,
            "margin_used": round(high * multiplier * ratio * lots, 2), "max_loss": round(abs(worst - stop) * lots * multiplier, 2)}


def _reason(decision: Decision, limit: int = 200) -> str:
    """
    The `reason` of an order: direction, confidence and the manager's account
    of the debate, at most `limit` characters and ending on a whole sentence
    when one fits.

    订单的 `reason`：方向、置信度，以及 Manager 对辩论的概述；不超过 `limit` 个字符，并尽量在完整的
    句子处结束。
    """
    text = " ".join((decision.debate_summary or decision.reasoning or "").replace("**", "").split())
    head = f"{DIRECTION_ZH.get(decision.direction, decision.direction)}，置信度 {decision.confidence:.2f}。"
    full = head + text
    if len(full) <= limit:
        return full
    cut = full[:limit]
    stop = cut.rfind("。")
    return cut[:stop + 1] if stop >= len(head) else cut.rstrip()


def build_order_plan(pack_date: str, decisions: dict[str, Decision], atr: dict[str, Optional[float]], positions: dict[str, Position],
                     cfg: OrderPlanConfig, market: MarketData, errors: Optional[dict[str, str]] = None,
                     now: Optional[datetime] = None) -> PlanResult:
    """
    Build the plan of one pack date (rules in the module docstring). `atr`
    maps symbol to the daily ATR of the pack; `errors` names symbols whose
    judgement failed; `now` is the wall clock (tests pin it). The plan is
    dated at the decision time: the pack date at `decision_clock`, or `now`
    when that is earlier.

    生成一个包日期的订单计划（规则见模块说明）。`atr` 为品种 -> 证据包中的日线 ATR；`errors` 指出判断
    失败的品种；`now` 是当前时间（测试会固定它）。计划的时间取决策时点：包日期的 `decision_clock`，
    若 `now` 更早则取 `now`。
    """
    day = date.fromisoformat(pack_date)
    decision_time = datetime.combine(day, time.fromisoformat(cfg.entry.decision_clock), SHANGHAI)
    as_of = min(now or datetime.now(SHANGHAI), decision_time)
    valid_until = datetime.combine(day, time.fromisoformat(cfg.order.valid_until_clock), SHANGHAI).isoformat(timespec="seconds")
    created_at = as_of.isoformat(timespec="seconds")
    orders: list[Order] = []
    sizing: list[dict] = []
    skipped: list[dict] = []

    def add(**fields) -> Order:
        """Append an order with the next id and the fixed fields.

        追加一张订单，带下一个编号和固定字段。
        """
        order = Order(order_id=f"M{len(orders) + 1:03d}", strategy_id=cfg.order.strategy_id, source=cfg.order.source,
                      hold_overnight=cfg.order.hold_overnight, valid_until=valid_until, **fields)
        orders.append(order)
        return order

    def skip(symbol: str, reason: str) -> None:
        """Record why a symbol got no (further) order.

        记录某品种没有（更多）订单的原因。
        """
        skipped.append({"symbol": symbol, "reason": reason})

    for symbol in sorted(decisions):
        d, pos = decisions[symbol], positions.get(symbol)
        if (errors or {}).get(symbol):
            skip(symbol, f"判断失败：{errors[symbol]}"[:200])
            continue
        closing: Optional[Order] = None
        if pos and d.reversal:
            closing = add(contract=pos.vt_symbol.split(".")[0].upper(), action="close", side="sell" if pos.direction == "long" else "buy",
                          lots=pos.volume, position_id=pos.vt_symbol, reason=f"趋势反转，平掉 {pos.direction} {pos.volume} 手。" + _reason(d, 160))
        if d.direction not in SIDE_OF:
            if not closing:
                skip(symbol, "方向不确定，不开新仓" + ("；持仓按原规则管理" if pos else ""))
            continue
        if pos and not closing:
            skip(symbol, f"已持有同向仓位 {pos.direction} {pos.volume} 手")
            continue
        if d.confidence < cfg.budget.min_confidence:
            skip(symbol, f"置信度 {d.confidence:.2f} 低于下限 {cfg.budget.min_confidence:g}")
            continue
        meta, daily_atr = VARIETY_META.get(symbol), atr.get(symbol)
        if meta is None or not daily_atr or daily_atr <= 0:
            skip(symbol, "没有最小变动价位" if meta is None else "证据包中没有日线 ATR")
            continue
        try:
            q = market.quote(symbol, as_of)
        except Exception as exc:  # noqa: BLE001 - reported per symbol, like a failed judgement
            skip(symbol, f"行情或合约数据不可用：{exc}"[:200])
            continue
        budget = cfg.budget.symbols.get(symbol, cfg.budget.default_cny) * (d.confidence if cfg.budget.scale_by_confidence else 1.0)
        loss_limit = cfg.risk.max_loss_cny * (d.confidence if cfg.risk.scale_by_confidence else 1.0)
        s = size_open(SIDE_OF[d.direction], q.price, daily_atr, q.multiplier, q.margin_ratio, meta[1], budget, loss_limit, cfg)
        if "skip" in s:
            skip(symbol, s["skip"])
            continue
        order = add(contract=q.contract, action="open", side=SIDE_OF[d.direction], lots=s["lots"], limit_price=[s["low"], s["high"]],
                    stop_price=s["stop"], target_price=s["target"], reason=_reason(d), depends_on=[closing.order_id] if closing else [])
        sizing.append({"symbol": symbol, "order_id": order.order_id, "contract": q.contract, "side": order.side, "confidence": d.confidence,
                       "budget_cny": round(budget, 2), "loss_limit_cny": round(loss_limit, 2), "reference_price": q.price, "reference_time": q.price_time, "atr": round(daily_atr, 4),
                       "multiplier": q.multiplier, "margin_ratio": round(q.margin_ratio + cfg.margin.addon, 6), "price_tick": meta[1],
                       **{k: s[k] for k in ("lots", "lots_by_margin", "lots_by_risk", "limited_by", "worst", "stop_distance", "stop_atr", "margin_used", "max_loss")}})
    plan = OrderPlan(plan_id=f"{cfg.order.plan_id_prefix}-{pack_date}", version=cfg.order.plan_version, snapshot_id=f"pack-{pack_date}",
                     created_at=created_at, orders=orders)
    return PlanResult(plan=plan, sizing=sizing, skipped=skipped, as_of=created_at)


def write_order_plan(result: PlanResult, run_dir: Path, cfg: OrderPlanConfig, extra_out: Optional[Path] = None) -> Path:
    """
    Write `order_plan.json` (the plan, nothing else) and
    `order_plan.audit.json` (parameters, decision time, sizing, skipped
    symbols) into `run_dir`; copy the plan to `extra_out` when given.

    把 `order_plan.json`（只含计划本身）和 `order_plan.audit.json`（参数、决策时点、计算明细、未出单
    品种）写到 `run_dir`；给了 `extra_out` 时再把计划拷贝一份过去。
    """
    run_dir.mkdir(parents=True, exist_ok=True)
    text = json.dumps(result.plan.model_dump(), ensure_ascii=False, indent=2) + "\n"
    (run_dir / PLAN_FILE).write_text(text, encoding="utf-8")
    (run_dir / AUDIT_FILE).write_text(json.dumps({"as_of": result.as_of, "config": cfg.model_dump(), "sizing": result.sizing, "skipped": result.skipped},
                                                 ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if extra_out:
        Path(extra_out).parent.mkdir(parents=True, exist_ok=True)
        Path(extra_out).write_text(text, encoding="utf-8")
    return run_dir / PLAN_FILE


def read_order_plan(run_dir: Path) -> Optional[PlanResult]:
    """
    Load a plan written by `write_order_plan`, or None when there is none.

    读取 `write_order_plan` 写出的计划；没有则返回 None。
    """
    plan_path, audit_path = run_dir / PLAN_FILE, run_dir / AUDIT_FILE
    if not plan_path.exists():
        return None
    audit = json.loads(audit_path.read_text(encoding="utf-8")) if audit_path.exists() else {}
    return PlanResult(plan=OrderPlan(**json.loads(plan_path.read_text(encoding="utf-8"))), sizing=audit.get("sizing", []),
                      skipped=audit.get("skipped", []), as_of=audit.get("as_of", ""))
