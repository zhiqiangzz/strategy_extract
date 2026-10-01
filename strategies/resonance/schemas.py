"""
Agents: read the English part only. 中文仅供人类阅读。

schemas.py — pydantic models for every structured LLM output and for the
hand-off file, plus the JSON schemas passed to `claude -p --json-schema`.

`Thesis` is what the Long/Short thesis agents return, `CrossExam` what the
cross-examination returns, `Decision` what the manager returns (this is the
value of callback CB01 `major_timeframe_direction`, and when a position is
open also of CB05 `major_trend_reversal`). `ResonanceSetting` /
`ContractSetting` mirror the serde structs of the Rust strategy; changing a
field here requires the same change in rust_core's resonance.rs.

schemas.py 定义所有结构化 LLM 输出和交接文件的 pydantic 模型，以及传给 `claude -p --json-schema`
的 JSON schema。`Thesis` 是多/空论证代理的返回，`CrossExam` 是交叉质证的返回，`Decision` 是
Manager 的返回（即回调 CB01 大周期方向判定 的值；持仓时也是 CB05 趋势反转 的值）。
`ResonanceSetting` / `ContractSetting` 与 Rust 策略的 serde 结构一一对应；改这里的字段必须同步改
rust_core 的 resonance.rs。
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from .config import ResonanceParams

Direction = Literal["long", "short", "uncertain"]


class KeyPoint(BaseModel):
    """
    One argument of a thesis with the evidence ids it rests on.

    论证中的一条论据及其依据的证据 id。
    """
    claim: str
    evidence_refs: list[str] = Field(default_factory=list)
    strength: Literal["weak", "moderate", "strong"]


class Thesis(BaseModel):
    """
    Output of the Long or Short thesis agent.

    多头或空头论证代理的输出。
    """
    stance: Literal["long", "short"]
    thesis: str
    key_points: list[KeyPoint]
    falsifiers: list[str] = Field(default_factory=list, description="what would prove this thesis wrong / 什么会推翻该论证")
    confidence: float = Field(ge=0, le=1)


class Rebuttal(BaseModel):
    """
    A rebuttal of one claim.

    对一条论据的反驳。
    """
    claim: str
    rebuttal: str
    survives: bool


class CrossExam(BaseModel):
    """
    Output of the cross-examination step.

    交叉质证步骤的输出。
    """
    long_rebuttals: list[Rebuttal]
    short_rebuttals: list[Rebuttal]
    unresolved_conflicts: list[str]
    data_quality_caveats: list[str]
    net_assessment: str


class Decision(BaseModel):
    """
    Output of the manager: the major-timeframe direction (CB01) and, when a
    position exists, the reversal verdict (CB05).

    Manager 的输出：大周期方向（CB01），持仓时还有反转裁决（CB05）。
    """
    symbol: str
    direction: Direction
    confidence: float = Field(ge=0, le=1)
    uncertain_is_high_confidence: bool = Field(False, description="only meaningful when direction == uncertain / 仅当 direction 为 uncertain 时有意义")
    reversal: Optional[bool] = Field(None, description="only when a position was given / 仅在给定持仓时")
    reasoning: str
    key_drivers: list[str]
    risk_flags: list[str] = Field(default_factory=list)
    evidence_quality: Literal["good", "partial", "poor"]


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
    JSON schema for `--json-schema`, with `additionalProperties: false` on
    the root so the model cannot invent fields.

    供 `--json-schema` 使用的 JSON schema，根对象禁止额外字段。
    """
    schema = model.model_json_schema()
    schema["additionalProperties"] = False
    return schema
