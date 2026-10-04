"""
Agents: read the English part only. 中文仅供人类阅读。

config.py — every tunable of the resonance implementation in one place.

`ResonanceParams` holds the deterministic rule parameters the Rust strategy
executes (timeframes, lookbacks, ATR caps, risk fraction) and the thresholds
the Python judge uses. `JudgeConfig` holds how the LLM debate is run (model,
effort, evidence level, round limit, concurrency, cache). Both are pydantic models so a
JSON/CLI override is validated. The defaults are the rule set the user chose
when the stubs were implemented; the S6 definitions they realise are quoted
in README.md.

config.py 集中管理 resonance 实现的全部可调项。`ResonanceParams` 是 Rust 策略执行的确定性规则
参数（周期、回看长度、ATR 上限、风险比例）和 Python 判断用的阈值；`JudgeConfig` 是 LLM 辩论的
运行方式（模型、effort、证据粒度、轮数上限、并发、缓存）。两者都是 pydantic 模型，JSON/命令行覆盖会被
校验。默认值是实现桩时用户选定的规则集；它们实现的 S6 定义在 README.md 中引用。
"""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parents[1]
PROMPTS_DIR = PACKAGE_DIR / "prompts"
PROMPT_VERSION = "v2"


class ResonanceParams(BaseModel):
    """
    Deterministic rule parameters shared with the Rust strategy (serialised
    into the setting file's `params`).

    与 Rust 策略共享的确定性规则参数（序列化到设置文件的 `params`）。
    """
    major_tf: str = "1d"
    minor_tf: str = "30m"
    entry_lookback: int = Field(20, ge=2, description="minor bars for the breakout channel / 入场突破通道的小周期 K 线数")
    stop_lookback: int = Field(10, ge=2, description="minor bars for the initial swing stop / 初始止损参考的小周期 K 线数")
    stop_atr_cap_mult: float = Field(2.0, gt=0, description="cap of the initial stop distance in minor ATRs / 初始止损距离上限（小周期 ATR 倍数）")
    atr_period: int = Field(14, ge=2)
    cost_r_multiple: float = Field(1.0, gt=0, description="open profit in R that triggers move-to-cost / 触发移损至成本的浮盈 R 倍数")
    cost_daily_atr_mult: float = Field(1.0, gt=0, description="daily close beyond entry by this many daily ATRs also triggers move-to-cost / 日线收盘超过入场价该倍数日 ATR 亦触发")
    trail_lookback_days: int = Field(10, ge=2, description="daily bars for the Donchian trailing stop / 移动止损参考的日线数")
    per_trade_loss_ratio: float = Field(0.01, gt=0, lt=0.05, description="T023: risk per trade as a fraction of capital / 单笔风险占本金比例")
    slippage_ticks: int = Field(2, ge=0)
    cooldown_bars: int = Field(0, ge=0, description="minor bars to wait after a stop-out before re-entry / 止损后再入场前等待的小周期 K 线数")
    reversal_uncertain_conf_threshold: float = Field(0.7, ge=0, le=1, description="an 'uncertain' with confidence at or above this counts as a high-confidence uncertain (reversal) / 不确定的置信度达到此值视为高置信度不确定（反转）")


class JudgeConfig(BaseModel):
    """
    How the LLM debate is executed.

    LLM 辩论的执行方式。
    """
    model: str = "opus"
    effort: str = "xhigh"
    evidence_level: str = Field("compact", pattern="^(compact|full)$")
    max_debate_rounds: int = Field(3, ge=1, le=3, description="hard cap on debate rounds; the moderator may stop earlier / 辩论轮数硬上限；主持人可提前终止")
    moderator_effort: str = Field("medium", description="effort of the continue-or-stop call / 主持人判断继续或终止所用的 effort")
    parallel_sides: bool = Field(True, description="run the long and short side of a step concurrently / 同一步的多空两侧并行调用")
    max_workers: int = Field(3, ge=1, le=8, description="symbols judged concurrently / 并行判断的品种数")
    timeout_s: int = Field(600, ge=30)
    retries: int = Field(1, ge=0)
    runs_dir: Path = REPO_ROOT / "strategies" / "resonance" / "runs"
    use_cache: bool = True
    control_url: str = "http://127.0.0.1:8081"
    daily_bars_for_context: int = Field(30, ge=0, description="recent daily bars appended to the evidence (0 = none) / 附加到证据中的最近日线数")
