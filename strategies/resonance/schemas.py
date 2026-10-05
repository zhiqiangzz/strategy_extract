"""
Agents: read the English part only. 中文仅供人类阅读。

schemas.py — pydantic models for every structured LLM output, for the
assembled debate record and for the hand-off file, plus the JSON schemas
passed to `claude -p --json-schema`.

LLM outputs: `Thesis` (opening statement of the long or short side),
`RebuttalTurn` / `DefenceTurn` (one side's rebuttals of the other side's
points, or its replies to the rebuttals of its own points, in one round),
`ModeratorRuling` (continue or stop after a round, with the reason) and
`Decision` (the manager's ruling on every point and the direction; this is
the value of callback CB01 `major_timeframe_direction`, and when a position
is open also of CB05 `major_trend_reversal`). `Debate` is the record the
code assembles from them: one `DebateThread` per point with its `Exchange`s,
and one `RoundRuling` per round. `OrderPlan` / `Order` are the order plan
handed to the trading system (built by `orders.py`); their field names and
order are that system's file format. `ResonanceSetting` / `ContractSetting`
mirror the serde structs of the Rust strategy; changing a field here
requires the same change in rust_core's resonance.rs.

schemas.py 定义所有结构化 LLM 输出、组装后的辩论记录和交接文件的 pydantic 模型，以及传给
`claude -p --json-schema` 的 JSON schema。LLM 输出：`Thesis`（多方或空方的立论）、`RebuttalTurn` /
`DefenceTurn`（一轮中一方对对方论据的反驳，或对己方论据所受反驳的再反驳）、`ModeratorRuling`
（一轮结束后继续或终止及理由）、`Decision`（Manager 对每条论据的裁定和方向；即回调 CB01 大周期方向
判定 的值，持仓时也是 CB05 趋势反转 的值）。`Debate` 是代码据此组装的记录：每条论据一个
`DebateThread`（含若干 `Exchange`），每轮一个 `RoundRuling`。`OrderPlan` / `Order` 是交给交易系统的订单计划
（由 `orders.py` 生成），字段名和顺序就是该系统的文件格式。`ResonanceSetting` / `ContractSetting`
与 Rust 策略的 serde 结构一一对应；改这里的字段必须同步改 rust_core 的 resonance.rs。
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from .config import ResonanceParams

Direction = Literal["long", "short", "uncertain"]
Side = Literal["long", "short"]
Strength = Literal["weak", "moderate", "strong"]
AttackType = Literal["counterexample", "limitation", "insufficient_support", "causality", "data_issue", "other"]
DefenceStance = Literal["maintain", "narrow", "concede"]


class KeyPoint(BaseModel):
    """
    One argument of an opening statement: the claim, why the evidence
    implies it, and the evidence ids it rests on.

    立论中的一条论据：结论、证据为何能推出它，以及依据的证据编号。
    """
    claim: str
    reasoning: str
    evidence_refs: list[str] = Field(default_factory=list)
    strength: Strength


class Thesis(BaseModel):
    """
    Opening statement of the long or short side.

    多方或空方的立论。
    """
    stance: Side
    thesis: str
    key_points: list[KeyPoint]
    falsifiers: list[str] = Field(default_factory=list, description="what would prove this thesis wrong / 什么会推翻该立论")
    confidence: float = Field(ge=0, le=1)


class Rebuttal(BaseModel):
    """
    One side's attack on one point of the other side.

    一方对对方一条论据的反驳。
    """
    point_id: str
    attack_type: AttackType
    argument: str
    evidence_refs: list[str] = Field(default_factory=list)
    withdrawn: bool = Field(False, description="true = the objection is dropped / 撤回异议")


class RebuttalTurn(BaseModel):
    """
    All rebuttals one side makes in one round.

    一方在一轮中的全部反驳。
    """
    rebuttals: list[Rebuttal]


class Defence(BaseModel):
    """
    The owner's reply to the latest rebuttal of one of its points.

    论据所有方对最新一条反驳的再反驳。
    """
    point_id: str
    stance: DefenceStance
    argument: str
    evidence_refs: list[str] = Field(default_factory=list)
    revised_claim: Optional[str] = Field(None, description="the narrower claim when stance == narrow / 收窄后的论据")


class DefenceTurn(BaseModel):
    """
    All replies one side makes in one round.

    一方在一轮中的全部再反驳。
    """
    defences: list[Defence]


class ModeratorRuling(BaseModel):
    """
    The moderator's call after a round: hold another one or stop, and why.

    主持人在一轮结束后的判断：继续还是终止，以及理由。
    """
    continue_debate: bool
    reason: str
    focus_point_ids: list[str] = Field(default_factory=list)


class Exchange(BaseModel):
    """
    One speech in a thread: a rebuttal by the opponent or a reply by the
    owner. `unanswered` marks a placeholder the code inserts when a side
    said nothing about a thread it was asked to address.

    线程中的一次发言：对方的反驳或所有方的再反驳。`unanswered` 表示该方被要求回应却没有回应时由
    代码插入的占位。
    """
    round: int
    speaker: Side
    kind: Literal["rebuttal", "defence"]
    argument: str
    evidence_refs: list[str] = Field(default_factory=list)
    attack_type: Optional[AttackType] = None
    stance: Optional[DefenceStance] = None
    revised_claim: Optional[str] = None
    withdrawn: bool = False
    unanswered: bool = False


class DebateThread(BaseModel):
    """
    One point of one side and everything said about it.

    一方的一条论据及围绕它的全部交锋。
    """
    point_id: str
    owner: Side
    claim: str
    reasoning: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    strength: Strength
    exchanges: list[Exchange] = Field(default_factory=list)
    status: Literal["contested", "conceded", "objection_withdrawn"] = "contested"


class RoundRuling(BaseModel):
    """
    Why the debate went on or stopped after a round; `decided_by` is
    "moderator" for the LLM's call and "rule" for the code's (no contested
    point left, or the round limit).

    一轮之后辩论为何继续或终止；`decided_by` 为 "moderator" 表示 LLM 主持人的判断，"rule" 表示
    代码规则（已无争议论据，或达到轮数上限）。
    """
    round: int
    continue_debate: bool
    reason: str
    decided_by: Literal["moderator", "rule"]
    focus_point_ids: list[str] = Field(default_factory=list)


class Debate(BaseModel):
    """
    The whole debate of one symbol.

    一个品种的完整辩论记录。
    """
    threads: list[DebateThread]
    rulings: list[RoundRuling] = Field(default_factory=list)
    rounds_held: int = 0


class PointVerdict(BaseModel):
    """
    The manager's ruling on one point.

    Manager 对一条论据的裁定。
    """
    point_id: str
    verdict: Literal["stands", "weakened", "refuted"]
    reason: str


class Decision(BaseModel):
    """
    Output of the manager: the ruling on every point, the major-timeframe
    direction (CB01) and, when a position exists, the reversal verdict
    (CB05).

    Manager 的输出：对每条论据的裁定、大周期方向（CB01），持仓时还有反转裁决（CB05）。
    """
    symbol: str
    direction: Direction
    confidence: float = Field(ge=0, le=1)
    uncertain_is_high_confidence: bool = Field(False, description="only meaningful when direction == uncertain / 仅当 direction 为 uncertain 时有意义")
    reversal: Optional[bool] = Field(None, description="only when a position was given / 仅在给定持仓时")
    point_verdicts: list[PointVerdict] = Field(default_factory=list)
    debate_summary: str = ""
    reasoning: str
    key_drivers: list[str]
    risk_flags: list[str] = Field(default_factory=list)
    evidence_quality: Literal["good", "partial", "poor"]


class Order(BaseModel):
    """
    One order of a plan. `limit_price` is the entry range `[low, high]` of an
    opening order: the trading system may enter anywhere inside it, and
    `stop_price` is placed so that the worst fill in the range (the top for
    a buy, the bottom for a sell) loses the allowed maximum. A closing order
    has no prices and names its position in `position_id`.

    计划中的一张订单。开仓单的 `limit_price` 是入场区间 `[下沿, 上沿]`：交易系统可在区间内任意位置
    入场，`stop_price` 的位置使区间内最差成交（买单为上沿，卖单为下沿）恰好亏到允许的上限。平仓单
    不带价格，用 `position_id` 指明持仓。
    """
    order_id: str
    contract: str
    action: Literal["open", "close"]
    side: Literal["buy", "sell"]
    lots: int = Field(ge=1)
    limit_price: Optional[list[float]] = None
    stop_price: Optional[float] = None
    target_price: Optional[float] = None
    position_id: Optional[str] = None
    strategy_id: str
    source: str
    reason: str
    hold_overnight: bool
    valid_until: str
    depends_on: list[str] = Field(default_factory=list)
    hedge_for: list[str] = Field(default_factory=list)

    @field_validator("limit_price")
    @classmethod
    def _range(cls, v: Optional[list[float]]) -> Optional[list[float]]:
        """A range is two prices, low first.

        区间是两个价格，下沿在前。
        """
        if v is not None and (len(v) != 2 or v[0] > v[1]):
            raise ValueError("limit_price must be [low, high]")
        return v


class OrderPlan(BaseModel):
    """
    The order plan of one pack date, as the trading system reads it.

    一个包日期的订单计划，即交易系统读取的文件内容。
    """
    plan_id: str
    version: int = 1
    snapshot_id: str
    created_at: str
    orders: list[Order] = Field(default_factory=list)


class Position(BaseModel):
    """
    An open position as reported by the control API (net view).

    control API 报告的净持仓。
    """
    vt_symbol: str
    variety_code: str
    direction: Literal["long", "short"]
    volume: int
    entry_price: Optional[float] = None


class Warmup(BaseModel):
    """
    Bars seeded into the Rust strategy so it can signal immediately after a
    reload. 30m bars are [start_epoch, o, h, l, c, v]; daily bars are
    [trading_day, o, h, l, c, v].

    为 Rust 策略预热的 K 线，使其 reload 后立即可以产生信号。30m 为 [start_epoch, o, h, l, c, v]，
    日线为 [trading_day, o, h, l, c, v]。
    """
    bars_30m: list[list] = Field(default_factory=list)
    bars_1d: list[list] = Field(default_factory=list)


class ContractSetting(BaseModel):
    """
    One contract's entry in the hand-off file (mirrors Rust `RawContract`).

    交接文件中一个合约的条目（对应 Rust 的 `RawContract`）。
    """
    variety_code: str
    variety_name: str
    decision_id: str
    direction: Direction
    confidence: float
    reversal: bool = False
    risk_budget_cny: float
    multiplier: float
    price_tick: float
    params: ResonanceParams
    warmup: Warmup = Field(default_factory=Warmup)
    note: str = ""


class ResonanceSetting(BaseModel):
    """
    The whole hand-off file (mirrors Rust `RawResonanceSetting`).

    整个交接文件（对应 Rust 的 `RawResonanceSetting`）。
    """
    version: int = 1
    generated_at: str
    pack_date: str
    source: str = "strategies/resonance judge"
    account: str
    contracts: dict[str, ContractSetting]


def json_schema_for(model: type[BaseModel]) -> dict:
    """
    JSON schema for `--json-schema`. Every object in it (the root and the
    nested models) lists all its properties as required and forbids extra
    ones, so the model can neither skip a field that has a default here nor
    invent one.

    供 `--json-schema` 使用的 JSON schema。其中每个对象（根和嵌套模型）都把全部属性列为必填并禁止
    额外字段，模型既不能跳过此处带默认值的字段，也不能自造字段。
    """
    schema = model.model_json_schema()
    for node in [schema, *schema.get("$defs", {}).values()]:
        if "properties" in node:
            node["required"] = list(node["properties"])
            node["additionalProperties"] = False
    return schema
