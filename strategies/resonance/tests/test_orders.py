"""
Agents: read the English part only. 中文仅供人类阅读。

Order-plan tests with a fake market (no database): the plan built from the
2026-09-30 decisions, the long mirror, the invariants of a sized order over a
grid of inputs, the plain formula with the stop floor off, every reason for
not placing an order, budget overrides, orders for an open position, the
parameter file, the plan files, the pack's daily ATR and the CLI.

订单计划测试，使用假行情（不连数据库）：由 2026-09-30 的决策生成的计划、多头镜像、在一组输入上检验
已定手数订单的不变量、关闭止损下限后的纯公式、每一种不出单的原因、预算覆盖、有持仓时的订单、参数
文件、计划文件、证据包的日线 ATR，以及命令行。
"""
from __future__ import annotations

import itertools
import json
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from strategies.resonance.evidence import load_pack
from strategies.resonance.orders import (AUDIT_FILE, PLAN_FILE, SHANGHAI, OrderPlanConfig, Quote, build_order_plan, load_plan_config,
                                         read_order_plan, size_open, write_order_plan)
from strategies.resonance.schemas import Decision, Position
from strategies.resonance.tests.conftest import FakeRunner

# what the database held for the 2026-09-30 open (checked with read-only queries when the feature was built)
# 数据库中 2026-09-30 开盘前的数据（实现该功能时用只读查询核对过）
QUOTES = {"LC": Quote("LC2701", 119500.0, "2026-09-30 08:59:00", 1, 0.17), "P": Quote("P2701", 9575.0, "2026-09-30 08:59:00", 10, 0.11),
          "AG": Quote("AG2612", 15000.0, "2026-09-30 08:59:00", 15, 0.22), "CU": Quote("CU2611", 109710.0, "2026-09-30 08:59:00", 5, 0.11),
          "TA": Quote("TA2701", 6306.0, "2026-09-30 08:55:00", 5, 0.10)}
ATR = {"LC": 6114.29, "P": 166.0, "AG": 494.5, "CU": 1329.29, "TA": 198.43}
LATER = datetime(2026, 10, 5, 12, 0, tzinfo=SHANGHAI)
SAMPLE_ORDER_KEYS = ["order_id", "contract", "action", "side", "lots", "limit_price", "stop_price", "target_price", "position_id", "strategy_id",
                     "source", "reason", "hold_overnight", "valid_until", "depends_on", "hedge_for"]


class FakeMarket:
    """
    Quotes from a dict; an unknown variety raises like the database reader.

    由字典提供行情；未知品种像数据库读取器一样抛错。
    """

    def __init__(self, quotes: dict[str, Quote] | None = None):
        """Keep the quotes and record every lookup.

        保存行情并记录每次查询。
        """
        self.quotes = QUOTES if quotes is None else quotes
        self.asked: list[tuple[str, datetime]] = []

    def quote(self, variety: str, as_of: datetime) -> Quote:
        """Return the quote or raise LookupError.

        返回行情或抛出 LookupError。
        """
        self.asked.append((variety, as_of))
        if variety not in self.quotes:
            raise LookupError("数据库中没有该日的主力合约")
        return self.quotes[variety]


def decision(symbol: str, direction: str, confidence: float, reversal: bool | None = None, summary: str = "空方的价格结构论据成立。") -> Decision:
    """A manager decision with the fields the plan reads.

    只含订单计划会读取的字段的 Manager 决策。
    """
    return Decision(symbol=symbol, direction=direction, confidence=confidence, reversal=reversal, debate_summary=summary, reasoning="理由",
                    key_drivers=[], evidence_quality="partial")


def plan(decisions: list[Decision], positions: dict[str, Position] | None = None, cfg: OrderPlanConfig | None = None, market: FakeMarket | None = None,
         now: datetime = LATER, **kw):
    """Build a plan for pack date 2026-09-30.

    为包日期 2026-09-30 生成计划。
    """
    return build_order_plan("2026-09-30", {d.symbol: d for d in decisions}, ATR, positions or {}, cfg or OrderPlanConfig(),
                            market or FakeMarket(), now=now, **kw)


def test_plan_of_the_2026_09_30_decisions():
    """
    The three short decisions become three opening orders with the range,
    lots and stop worked out by hand; the two uncertain symbols get none.
    The plan is dated at the decision time even when it is built days later,
    and the reference price is asked for as of that time.

    三个做空决策变成三张开仓单，区间、手数和止损与手算一致；两个不确定的品种不出单。即使在几天后才
    生成，计划的时间仍是决策时点，参考价也按该时点查询。
    """
    market = FakeMarket()
    r = plan([decision("LC", "short", 0.68), decision("P", "short", 0.66), decision("AG", "short", 0.57), decision("CU", "uncertain", 0.70),
              decision("TA", "uncertain", 0.55)], market=market)
    p = r.plan
    assert (p.plan_id, p.version, p.snapshot_id, p.created_at) == ("manager-2026-09-30", 1, "pack-2026-09-30", "2026-09-30T09:00:00+08:00")
    assert [(o.order_id, o.contract, o.action, o.side, o.lots, o.limit_price, o.stop_price, o.target_price) for o in p.orders] == [
        ("M001", "AG2612", "open", "sell", 1, [14877.0, 15123.0], 15447.0, 13167.0),
        ("M002", "LC2701", "open", "sell", 1, [117980.0, 121020.0], 128180.0, 87380.0),
        ("M003", "P2701", "open", "sell", 5, [9534.0, 9616.0], 9732.0, 8940.0)]
    assert all((o.strategy_id, o.source, o.hold_overnight, o.valid_until, o.position_id, o.depends_on, o.hedge_for) ==
               ("major_minor_timeframe_resonance", "manager", True, "2026-09-30T15:00:00+08:00", None, [], []) for o in p.orders)
    assert p.orders[1].reason == "做空，置信度 0.68。空方的价格结构论据成立。"
    assert r.skipped == [{"symbol": "CU", "reason": "方向不确定，不开新仓"}, {"symbol": "TA", "reason": "方向不确定，不开新仓"}]
    sizing = {s["symbol"]: s for s in r.sizing}
    # budget and loss limit both shrink with the confidence: LC 0.68 -> 68 000 and 10 200
    assert (sizing["LC"]["budget_cny"], sizing["LC"]["loss_limit_cny"], sizing["LC"]["max_loss"]) == (68000.0, 10200.0, 10200.0)
    assert (sizing["LC"]["limited_by"], sizing["LC"]["lots_by_margin"], sizing["LC"]["lots_by_risk"], sizing["LC"]["stop_atr"]) == ("止损下限", 3, 1, 1.67)
    assert (sizing["P"]["limited_by"], sizing["P"]["margin_used"], sizing["P"]["loss_limit_cny"], sizing["P"]["max_loss"]) == ("止损下限", 52888.0, 9900.0, 9900.0)
    assert (sizing["AG"]["budget_cny"], sizing["AG"]["loss_limit_cny"], sizing["AG"]["limited_by"]) == (57000.0, 8550.0, "保证金")
    assert sizing["AG"]["reference_time"] == "2026-09-30 08:59:00"
    # only symbols that open are looked up, as of the decision time
    assert {v for v, _ in market.asked} == {"AG", "LC", "P"} and {t.isoformat() for _, t in market.asked} == {"2026-09-30T09:00:00+08:00"}
    # the file format: same keys, same order, as the sample plan; limit_price is [low, high]
    dumped = p.model_dump()
    assert list(dumped) == ["plan_id", "version", "snapshot_id", "created_at", "orders"] and list(dumped["orders"][0]) == SAMPLE_ORDER_KEYS
    # built before the decision time: dated now
    early = plan([decision("LC", "short", 0.68)], now=datetime(2026, 9, 30, 8, 45, tzinfo=SHANGHAI))
    assert early.plan.created_at == "2026-09-30T08:45:00+08:00"


def test_long_is_the_mirror():
    """
    A long order buys: the worst fill is the top of the range, the stop is
    below the range and the target above.

    多头订单为买入：最差成交在区间上沿，止损在区间下方，目标在上方。
    """
    o = plan([decision("CU", "long", 0.70)]).plan.orders[0]
    assert (o.side, o.lots, o.limit_price, o.stop_price, o.target_price) == ("buy", 1, [109380.0, 110040.0], 107940.0, 116340.0)
    assert o.reason.startswith("做多，置信度 0.70。")


def test_sized_orders_keep_their_invariants():
    """
    Over a grid of prices, volatilities, contract specs, budgets and
    parameters: a sized order never loses more than the limit when filled at
    its worst price, never needs more margin than the budget, has its stop
    outside the range on the losing side, and all its prices on the tick grid.

    在一组价格、波动率、合约规格、预算和参数上：已定手数的订单按最差价成交也不会亏过上限，占用的保证金
    不超过预算，止损在区间之外且位于亏损一侧，所有价格都落在最小变动价位上。
    """
    sized = skipped = 0
    for side, (price, tick), atr_pct, mult, ratio, (budget, limit), floor, width in itertools.product(
            ("buy", "sell"), ((109710.0, 10.0), (9575.0, 2.0), (811.5, 0.5), (15000.0, 1.0)), (0.004, 0.02, 0.06), (1.0, 10.0, 100.0),
            (0.08, 0.22), ((20_000.0, 3_000.0), (80_000.0, 12_000.0), (300_000.0, 15_000.0)), (0.0, 0.5, 1.0, 2.5), (0.0, 0.25, 1.0)):
        cfg = OrderPlanConfig(risk={"min_stop_atr": floor}, entry={"range_atr": width})
        s = size_open(side, price, price * atr_pct, mult, ratio, tick, budget, limit, cfg)
        if "skip" in s:
            skipped += 1
            continue
        sized += 1
        low, high, stop, worst = s["low"], s["high"], s["stop"], s["worst"]
        assert s["lots"] >= 1 and low <= high and worst == (high if side == "buy" else low)
        assert s["max_loss"] <= limit + 1e-6 and s["margin_used"] <= budget + 1e-6
        assert (stop < low) if side == "buy" else (stop > high)
        for value in (low, high, stop, s["target"]):
            assert value is None or abs(value / tick - round(value / tick)) < 1e-6
        if floor and s["limited_by"] == "止损下限":
            assert s["stop_distance"] >= floor * price * atr_pct - tick
    assert sized > 400 and skipped > 100


def test_plain_formula_and_parameters():
    """
    With the stop floor off the lots come from the margin budget alone (LC:
    three lots; the stop is 3400 points away with the loss limit scaled by
    confidence, 5000 with the full limit). The other parameters do what the
    file says: full budget, per-symbol budget, margin surcharge, no target,
    a wider range, another clock, other fixed fields.

    关闭止损下限后手数只由保证金预算决定（LC：三手；亏损上限乘置信度时止损距离 3400 点，用全额时
    5000 点）。其他参数按文件所说生效：全额预算、按品种的预算、保证金加收、不设目标、更宽的区间、别的
    时间、别的固定字段。
    """
    lc = [decision("LC", "short", 0.68)]
    o = plan(lc, cfg=OrderPlanConfig(risk={"min_stop_atr": 0})).plan.orders[0]
    assert (o.lots, o.limit_price, o.stop_price) == (3, [117980.0, 121020.0], 121380.0)
    full = plan(lc, cfg=OrderPlanConfig(risk={"min_stop_atr": 0, "scale_by_confidence": False})).plan.orders[0]
    assert (full.lots, full.stop_price) == (3, 122980.0)
    # the full loss limit with the stop floor on: two lots, 7500 points
    assert [(x.lots, x.stop_price) for x in plan(lc, cfg=OrderPlanConfig(risk={"scale_by_confidence": False})).plan.orders] == [(2, 125480.0)]
    assert plan(lc, cfg=OrderPlanConfig(risk={"min_stop_atr": 0}, budget={"scale_by_confidence": False})).plan.orders[0].lots == 4
    assert plan(lc, cfg=OrderPlanConfig(risk={"min_stop_atr": 0}, budget={"symbols": {"LC": 200_000}})).plan.orders[0].lots == 6
    assert plan(lc, cfg=OrderPlanConfig(risk={"min_stop_atr": 0}, margin={"addon": 0.08})).plan.orders[0].lots == 2
    custom = OrderPlanConfig(entry={"range_atr": 0.5, "decision_clock": "08:55:00"},
                             order={"target_r": 0, "hold_overnight": False, "valid_until_clock": "23:00:00", "plan_id_prefix": "resonance", "strategy_id": "x"})
    r = plan(lc, cfg=custom)
    o = r.plan.orders[0]
    assert (r.plan.plan_id, r.plan.created_at, o.strategy_id) == ("resonance-2026-09-30", "2026-09-30T08:55:00+08:00", "x")
    assert (o.limit_price, o.target_price, o.hold_overnight, o.valid_until) == ([116460.0, 122540.0], None, False, "2026-09-30T23:00:00+08:00")


def test_every_reason_for_no_order():
    """
    No order, with the reason recorded: a budget below one lot's margin, one
    lot already losing more than the limit at the stop floor, confidence
    under the minimum, no quote, no daily ATR, no price tick, a failed
    judgement.

    不出单并记录原因：预算不足一手保证金、一手按止损下限就已超过亏损上限、置信度低于下限、没有行情、
    没有日线 ATR、没有最小变动价位、判断失败。
    """
    def why(decisions, **kw) -> str:
        """The single skip reason of a plan with no orders.

        一份没有订单的计划里唯一的未出单原因。
        """
        r = plan(decisions, **kw)
        assert r.plan.orders == [] and len(r.skipped) == 1
        return r.skipped[0]["reason"]

    assert why([decision("CU", "long", 0.50)]) == "预算 50000 元不足一手保证金 60522 元"
    assert why([decision("LC", "short", 0.68)], cfg=OrderPlanConfig(risk={"min_stop_atr": 3.0})) == "一手按 3 倍日线 ATR 止损的亏损 18343 元超过上限 10200 元"
    assert why([decision("LC", "short", 0.68)], cfg=OrderPlanConfig(budget={"min_confidence": 0.7})) == "置信度 0.68 低于下限 0.7"
    assert why([decision("LC", "short", 0.68)], market=FakeMarket({})) == "行情或合约数据不可用：数据库中没有该日的主力合约"
    assert why([decision("RB", "long", 0.8)], market=FakeMarket({"RB": Quote("RB2701", 3000.0, "t", 10, 0.1)})) == "证据包中没有日线 ATR"
    assert why([decision("ZZ", "long", 0.8)]) == "没有最小变动价位"
    assert why([decision("LC", "uncertain", 0.0)], errors={"LC": "claude timed out"}) == "判断失败：claude timed out"


def test_orders_for_an_open_position():
    """
    A reversal closes the position; when the new direction is the opposite
    one, an opening order follows and depends on the close. The same
    direction, or an uncertain call that is not a reversal, places nothing.

    反转时平掉持仓；新方向相反时，随后有一张依赖平仓单的开仓单。方向一致，或不构成反转的不确定判断，
    都不出单。
    """
    held = {"LC": Position(vt_symbol="lc2701.GFEX", variety_code="LC", direction="long", volume=3, entry_price=125000.0)}
    r = plan([decision("LC", "short", 0.68, reversal=True)], positions=held)
    close, reopen = r.plan.orders
    assert (close.order_id, close.contract, close.action, close.side, close.lots, close.position_id) == ("M001", "LC2701", "close", "sell", 3, "lc2701.GFEX")
    assert (close.limit_price, close.stop_price, close.target_price, close.depends_on) == (None, None, None, [])
    assert close.reason.startswith("趋势反转，平掉 long 3 手。")
    assert (reopen.order_id, reopen.action, reopen.side, reopen.lots, reopen.depends_on) == ("M002", "open", "sell", 1, ["M001"])
    assert [s["order_id"] for s in r.sizing] == ["M002"] and r.skipped == []

    only_close = plan([decision("LC", "uncertain", 0.8, reversal=True)], positions=held)
    assert [(o.action, o.side) for o in only_close.plan.orders] == [("close", "sell")] and only_close.skipped == []
    short_held = {"LC": Position(vt_symbol="lc2701.GFEX", variety_code="LC", direction="short", volume=2)}
    assert plan([decision("LC", "uncertain", 0.8, reversal=True)], positions=short_held).plan.orders[0].side == "buy"

    same = plan([decision("LC", "short", 0.68, reversal=False)], positions=short_held)
    assert same.plan.orders == [] and same.skipped == [{"symbol": "LC", "reason": "已持有同向仓位 short 2 手"}]
    unsure = plan([decision("LC", "uncertain", 0.4, reversal=False)], positions=held)
    assert unsure.plan.orders == [] and unsure.skipped == [{"symbol": "LC", "reason": "方向不确定，不开新仓；持仓按原规则管理"}]


def test_parameter_file(tmp_path: Path):
    """
    The shipped order_plan.toml equals the built-in defaults; another file
    overrides them; an unknown key is an error.

    随包提供的 order_plan.toml 与内置默认值一致；别的文件可以覆盖；出现未知的键即报错。
    """
    assert load_plan_config() == OrderPlanConfig()
    assert (load_plan_config().budget.default_cny, load_plan_config().risk.max_loss_cny, load_plan_config().order.strategy_id) == (
        100_000, 15_000, "major_minor_timeframe_resonance")
    custom = tmp_path / "plan.toml"
    custom.write_text('[budget]\ndefault_cny = 50000\n[budget.symbols]\nCU = 150000\n[risk]\nmax_loss_cny = 8000\n', encoding="utf-8")
    cfg = load_plan_config(custom)
    assert (cfg.budget.default_cny, cfg.budget.symbols, cfg.risk.max_loss_cny, cfg.risk.min_stop_atr) == (50_000, {"CU": 150_000}, 8_000, 1.0)
    custom.write_text("[risk]\nmax_loss = 8000\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        load_plan_config(custom)


def test_plan_files_round_trip(tmp_path: Path):
    """
    order_plan.json holds the plan and nothing else; the audit file holds
    the parameters, sizing and skipped symbols; both load back; the copy is
    identical.

    order_plan.json 只含计划本身；审计文件含参数、计算明细和未出单品种；二者都能读回；副本内容相同。
    """
    r = plan([decision("LC", "short", 0.68), decision("CU", "uncertain", 0.7)])
    path = write_order_plan(r, tmp_path / "run", OrderPlanConfig(), tmp_path / "elsewhere" / "plan.json")
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert path.name == PLAN_FILE and saved == r.plan.model_dump() and saved["orders"][0]["limit_price"] == [117980.0, 121020.0]
    assert (tmp_path / "elsewhere" / "plan.json").read_text(encoding="utf-8") == path.read_text(encoding="utf-8")
    audit = json.loads((tmp_path / "run" / AUDIT_FILE).read_text(encoding="utf-8"))
    assert audit["as_of"] == "2026-09-30T09:00:00+08:00" and audit["config"]["risk"]["max_loss_cny"] == 15000 and audit["skipped"][0]["symbol"] == "CU"
    back = read_order_plan(tmp_path / "run")
    assert back.plan == r.plan and back.sizing == r.sizing and back.skipped == r.skipped
    assert read_order_plan(tmp_path / "nothing") is None


def test_daily_atr_of_the_pack(pack: Path):
    """
    The pack's daily ATR is the atr_14 indicator when present, else the mean
    true range of its daily bars.

    证据包的日线 ATR 优先取 atr_14 指标，没有则取包内日线的平均真实波幅。
    """
    ev = load_pack(pack)["CU"]
    assert ev.daily_atr == 2.0
    ev.technical["single_indicator_results"]["atr_14"] = {"current_values": {"atr": 1329.29}}
    assert ev.daily_atr == 1329.29
    ev.technical, ev.daily_bars = None, []
    assert ev.daily_atr is None


def test_cli_writes_and_recomputes_the_plan(pack: Path, tmp_path: Path, monkeypatch):
    """
    `judge` writes order_plan.json next to decisions.json, records the ATR
    and shows the plan in the report; `plan` recomputes the same file from
    decisions.json and applies another parameter file; `report` keeps the
    plan section; a bad parameter file stops `judge` before any model call.

    `judge` 在 decisions.json 旁写出 order_plan.json，记录 ATR，并在报告中展示计划；`plan` 从
    decisions.json 重算出相同的文件，也能应用别的参数文件；`report` 保留计划部分；参数文件有误时
    `judge` 在调用模型之前就停下。
    """
    from strategies.resonance import cli
    runner, real_many = FakeRunner(), cli.judge_many
    market = FakeMarket({"CU": Quote("CU2611", 109710.0, "2026-09-29 08:59:00", 5, 0.11)})
    monkeypatch.setattr(cli, "judge_many", lambda *a, **kw: real_many(*a, runner=runner, **kw))
    monkeypatch.setattr(cli, "from_control_api", lambda url, account: ({}, None))
    monkeypatch.setattr(cli, "DbMarketData", lambda: market)
    runs = ["--runs-dir", str(tmp_path / "runs")]
    out = tmp_path / "inbox" / "plan.json"
    assert cli.main(["judge", "--pack", str(pack), "--symbols", "CU", "--dry-run", "--plan-out", str(out), *runs]) == 0
    run_dir = tmp_path / "runs" / "2026-09-29"
    first = (run_dir / PLAN_FILE).read_text(encoding="utf-8")
    order = json.loads(first)["orders"][0]
    # the fixture's ATR is 2 points, so the range collapses to the reference price on a 10-point tick
    assert (order["contract"], order["side"], order["lots"], order["limit_price"], order["stop_price"]) == ("CU2611", "buy", 1, [109710.0, 109710.0], 107610.0)
    assert json.loads(first)["created_at"] == "2026-09-29T09:00:00+08:00" and out.read_text(encoding="utf-8") == first
    assert json.loads((run_dir / "decisions.json").read_text(encoding="utf-8"))["meta"]["CU"]["atr"] == 2.0
    report = (run_dir / "report.md").read_text(encoding="utf-8")
    assert "## 订单计划" in report and "| M001 | CU2611 | open buy | 1 | 109710 – 109710 | 107610 | 116010 |" in report and "| 60,340 / 70,000 | 10,500 / 10,500 | 保证金 |" in report

    (run_dir / PLAN_FILE).unlink()
    assert cli.main(["plan", "--pack-date", "2026-09-29", *runs]) == 0 and (run_dir / PLAN_FILE).read_text(encoding="utf-8") == first
    assert cli.main(["report", "--pack-date", "2026-09-29", *runs]) == 0 and "## 订单计划" in (run_dir / "report.md").read_text(encoding="utf-8")
    tight = tmp_path / "tight.toml"
    tight.write_text("[budget]\ndefault_cny = 50000\n", encoding="utf-8")
    assert cli.main(["plan", "--pack-date", "2026-09-29", "--plan-config", str(tight), *runs]) == 0
    assert json.loads((run_dir / PLAN_FILE).read_text(encoding="utf-8"))["orders"] == []
    assert "未出单：\n- CU：预算 35000 元不足一手保证金 60340 元" in (run_dir / "report.md").read_text(encoding="utf-8")

    calls = len(runner.calls)
    tight.write_text("[budget]\ndefault = 1\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        cli.main(["judge", "--pack", str(pack), "--symbols", "CU", "--dry-run", "--no-cache", "--plan-config", str(tight), *runs])
    assert len(runner.calls) == calls
    assert cli.main(["judge", "--pack", str(pack), "--symbols", "CU", "--dry-run", "--no-plan", "--runs-dir", str(tmp_path / "other")]) == 0
    assert not (tmp_path / "other" / "2026-09-29" / PLAN_FILE).exists()
