# strategies/resonance — downstream implementation of 大小周期共振

> **Agents: follow the English part only (above the "中文版" divider). The Chinese part is a translation for human readers and adds no instructions.**
>
> **说明：agent 执行时只需参考上半部分的英文；下半部分的中文仅供人类阅读，内容相同，不含额外指令。**

## What this is

The first consumer of the strategy-formalizer output in `workspace/大小周期共振/final/`. The six callbacks of `callbacks_stub.py` are implemented in two places:

| S7 callback | Implementation | Where |
|---|---|---|
| CB01 `major_timeframe_direction` (T011) | LLM debate over the A1–A4 evidence pack: Long Thesis → Short Thesis → Cross-Examination → Manager | Python, `debate.py`, run by the user whenever they want |
| CB05 `major_trend_reversal` (T021) | Same run, when a position is open: `reversal = direction opposite to the position OR high-confidence uncertain` (recomputed in code, `apply_reversal_rule`) | Python |
| CB02 `minor_timeframe_entry_signal` (T013) | 30-minute bar close beyond the highest high (long) / lowest low (short) of the previous `entry_lookback` bars, only in the major direction (T022) | Rust `resonance.rs::on_minor_close` |
| CB03 `initial_stop_level` (T014) | Swing low/high of the last `stop_lookback` 30m bars ± 1 tick, capped at `stop_atr_cap_mult × ATR(30m)`, floored to one tick; lots = floor(`risk_budget_cny` / (distance × multiplier)) (T004/T023) | Rust, at the entry decision; stop armed at the fill |
| CB06 `favorable_move` (T024) | open profit ≥ `cost_r_multiple × R` on a 30m close, or daily close beyond entry by `cost_daily_atr_mult × ATR(1d)` → stop to entry price (T015/T016) | Rust `on_minor_close` / `on_daily_close` |
| CB04 `major_timeframe_trailing_stop` (T020) | lowest low / highest high of the last `trail_lookback_days` daily bars; only tightens, never beyond cost (T025) | Rust `on_daily_close` |
| exit path 1 (stop hit) | touch `StopLoss` trigger in the strategy's own `OrderEngine` | Rust, every tick |
| exit path 2 (reversal) | `reversal: true` in the setting file → close on the next in-session tick | Rust `reload` + `on_tick` |

Data flow:

```
Multi-Agent-Trading-Platform A5 run (A1 技术指标 / A2 基本面 / A3 新闻 / A4 研报)
        │  scratchpad/<date>/
        ▼
uv run python -m strategies.resonance.cli judge --pack <dir> --account <user>
        │  4 × `claude -p --model opus --effort xhigh --json-schema` per variety
        │  runs/<date>/<symbol>/{long_thesis,short_thesis,cross_exam,manager}.{prompt.md,response.json}
        │  runs/<date>/decisions.json + report.md
        ▼
rust_core/.vntrader/resonance_setting_<user>.json   (direction, reversal, risk budget, params, warm-up bars)
        │  POST /api/strategy/reload?account=<user>
        ▼
trading-core → ResonanceStrategy (crates/strategy/src/resonance.rs) → CTP
        │  resonance_state_<user>.json (phase, bars), resonance_triggers_<user>.json (stops)
```

## Files

| File | Purpose |
|---|---|
| `config.py` | `ResonanceParams` (rule parameters shared with Rust) and `JudgeConfig` (model, effort, evidence level, workers, cache). |
| `evidence.py` | Loads an A5 pack and renders one symbol's evidence with stable ids (`A1.macd`, `A2.curve`, `A3.<event_id>`, `A4.ev1`, `D`). |
| `claude_cli.py` | One structured call through the logged-in Claude Code CLI (`claude -p … --json-schema`), nested-session safe, transcripts recorded. |
| `prompts/*.md` | The four role prompts; `_definitions.md` quotes T011/T005/T021/T010/T007 verbatim and is embedded in every prompt. |
| `schemas.py` | pydantic models for Thesis / CrossExam / Decision, the hand-off `ResonanceSetting`, and the JSON schemas sent to the CLI. |
| `debate.py` | `judge_symbol` (four calls, validation, reversal rule, cache) and `judge_many` (thread pool). |
| `positions.py` | Open positions and capital from the control API (`/api/positions`, `/api/account`) or a file. |
| `signal_writer.py` | Decisions → setting file: main contract from the v2 DB, `VARIETY_META` multipliers/ticks, risk budget, warm-up bars (30m from `tick_ctp`, daily from `market_data`), atomic write, reload call. |
| `export_ticks.py` | Exports `tick_ctp` ticks of a contract for the Rust replay example. |
| `cli.py` | `judge` and `report` commands. |
| `tests/` | Fake-runner tests: evidence, debate, reversal rule, cache, setting round-trip, positions parsing. |
| `runs/` | Per-pack transcripts, decisions and reports (git-ignored except reports). |

Rust side (branch `resonance-strategy` of `third_party/quant_trading`): `crates/strategy/src/bars.rs` (tick → 30m/daily bars, ATR, Donchian), `crates/strategy/src/resonance.rs` (the strategy, serde structs mirroring `schemas.py`, 7 tests), `crates/strategy/examples/resonance_replay.rs` (dry-run replay on exported ticks), `trading-core/src/main.rs` + `accounts.rs` (registration, per-strategy trigger file, subscriptions), `strategy/src/lib.rs` (`symbols_of`).

## Hand-off file

`resonance_setting_<user>.json` (written by Python, read by Rust `RawResonanceSetting`):

```json
{"version": 1, "generated_at": "...", "pack_date": "2026-09-29", "account": "<user>", "source": "strategies/resonance judge",
 "contracts": {"cu2611.SHFE": {"variety_code": "CU", "variety_name": "沪铜", "decision_id": "2026-09-29/CU",
   "direction": "long|short|uncertain", "confidence": 0.62, "reversal": false,
   "risk_budget_cny": 10000.0, "multiplier": 5, "price_tick": 10.0,
   "params": {"entry_lookback": 20, "stop_lookback": 10, "stop_atr_cap_mult": 2.0, "atr_period": 14, "cost_r_multiple": 1.0,
              "cost_daily_atr_mult": 1.0, "trail_lookback_days": 10, "slippage_ticks": 2, "cooldown_bars": 0},
   "warmup": {"bars_30m": [[epoch, o, h, l, c, v], ...], "bars_1d": [["YYYY-MM-DD", o, h, l, c, v], ...]}}}}
```

Semantics in Rust: `long`/`short` and flat → hunt entries on 30m closes; `uncertain` → no new entries, open positions keep being managed; `reversal: true` with an open position → close on the next in-session tick. Contracts missing from a new file: dropped when flat, kept with direction `uncertain` when in position (a position is never abandoned).

## Run book

```sh
# 1. judge (dry run: decisions + report only; ~4 opus/xhigh calls per variety, ≈ $1.5–2 per variety)
uv run python -m strategies.resonance.cli judge --pack scratchpad/2026-09-29 --symbols CU,LC --dry-run --capital 1000000
# 2. full: writes rust_core/.vntrader/resonance_setting_<user>.json (DB lookups + warm-up) and reloads the core
uv run python -m strategies.resonance.cli judge --pack scratchpad/2026-09-29 --account <user>
#    add --no-reload to only write the file; --positions file.json / --capital N when the core is not running
# 3. Rust (inside third_party/quant_trading/rust_core, toolchain from this repo's pixi env)
PATH=../../../.pixi/envs/default/bin:$PATH cargo test -p strategy
cargo run -p strategy --example resonance_replay -- ticks.json resonance_setting.json
uv run python -m strategies.resonance.export_ticks --variety CU --begin 2026-09-15 --end 2026-09-26 --out ticks.json
```

Positions come from `GET /api/positions?account=`; capital from `GET /api/account?account=` (`balance`). A cached decision (same pack date, symbol, prompt version, model, effort, evidence level and position state) is reused for free; `--no-cache` forces a rerun.

## Limitations

- No backtest: trading-core has no replay harness; `resonance_replay` dry-runs the Rust rules on exported ticks with next-tick fills and no slippage model.
- `trading-core` itself must be built on the deployment machine (CTP SDK + bindgen); only the `strategy` crate is built and tested here.
- The evidence pack is as fresh as its sources (A2 factor dates lag ~5 days; A3 may be unusable for some symbols; A4 is often PARTIAL). The manager is told to lower `evidence_quality` accordingly.
- Risk sizing uses the capital given at judge time; the Rust strategy sizes at entry from `risk_budget_cny` and the planned stop distance (floored to one tick).
- Live reload (`POST /api/strategy/reload`) is only exercised when a `trading-core` is running on the machine; the judge logs a warning and leaves the setting file in place otherwise. The Rust side lives on branch `resonance-strategy` of the `quant_trading` submodule and must be merged/deployed there.

---

# 中文版（仅供人类阅读；agent 请参考上方英文）

## 这是什么

strategy-formalizer 在 `workspace/大小周期共振/final/` 产出的第一个下游实现。`callbacks_stub.py` 的六个回调分两处实现：

| S7 回调 | 实现 | 位置 |
|---|---|---|
| CB01 大周期方向判定（T011） | 对 A1–A4 证据包做 LLM 辩论：多头论证 → 空头论证 → 交叉质证 → Manager | Python `debate.py`，用户随时运行 |
| CB05 趋势反转（T021） | 同一次运行，持仓时：`reversal = 方向与持仓相反 或 高置信度不确定`（代码重算，`apply_reversal_rule`） | Python |
| CB02 小周期入场信号（T013） | 30 分钟 K 线收盘价突破此前 `entry_lookback` 根的最高高点（多）/最低低点（空），且与大周期同向（T022） | Rust `resonance.rs::on_minor_close` |
| CB03 小周期止损（T014） | 最近 `stop_lookback` 根 30m K 线的摆动低/高点 ± 1 跳，上限 `stop_atr_cap_mult × ATR(30m)`，下限 1 跳；手数 = floor(`risk_budget_cny` / (距离 × 乘数))（T004/T023） | Rust，入场决策时算，成交后武装止损 |
| CB06 有利运动（T024） | 30m 收盘浮盈 ≥ `cost_r_multiple × R`，或日线收盘超过入场价 `cost_daily_atr_mult × ATR(1d)` → 止损移到入场价（T015/T016） | Rust `on_minor_close` / `on_daily_close` |
| CB04 大周期移动止损（T020） | 最近 `trail_lookback_days` 根日线的最低低点/最高高点；只进不退，不低于成本（T025） | Rust `on_daily_close` |
| 出场路径一（打止损） | 策略自带 `OrderEngine` 的 touch 止损触发 | Rust，每个 tick |
| 出场路径二（趋势反转） | 设置文件 `reversal: true` → 下一个交易时段内的 tick 平仓 | Rust `reload` + `on_tick` |

数据流见英文部分的图：A5 证据包 → `cli judge`（每品种 4 次 `claude -p`，留痕到 `runs/<日期>/<品种>/`）→ `resonance_setting_<user>.json` → `POST /api/strategy/reload` → trading-core 中的 `ResonanceStrategy` → CTP。

## 文件

见英文部分的表格。Rust 侧在 `third_party/quant_trading` 的 `resonance-strategy` 分支：`bars.rs`（tick → 30m/日线、ATR、Donchian）、`resonance.rs`（策略本体与 serde 结构，7 个测试）、`examples/resonance_replay.rs`（导出 tick 的干跑回放）、`main.rs`/`accounts.rs`（注册、每策略独立触发文件、订阅）、`lib.rs`（`symbols_of`）。

## 交接文件

格式见英文部分。Rust 侧语义：`long`/`short` 且空仓 → 在 30m 收盘找入场；`uncertain` → 不开新仓、已有持仓继续管理；`reversal: true` 且持仓 → 下一个交易时段内 tick 平仓。新文件里消失的合约：空仓则移除，持仓则保留管理且方向置 `uncertain`（绝不丢下持仓）。

## 运行手册

命令见英文部分：`cli judge --dry-run` 只出决策与报告（每品种约 4 次 opus/xhigh 调用，约 1.5–2 美元）；去掉 `--dry-run` 则写设置文件（含 DB 查询与预热 K 线）并通知 core 重载（`--no-reload` 只写文件）；Rust 侧在 `rust_core` 内用本仓库 pixi 环境的工具链 `cargo test -p strategy`，`resonance_replay` 用 `export_ticks` 导出的 tick 回放。持仓来自 `/api/positions`，资金来自 `/api/account` 的 `balance`。同一（包日期、品种、提示词版本、模型、effort、证据粒度、持仓状态）的决策会被缓存复用，`--no-cache` 强制重跑。

## 局限

- 没有回测：trading-core 无回放框架；`resonance_replay` 用下一 tick 按委托价成交、无滑点模型。
- `trading-core` 需在部署机编译（CTP SDK + bindgen）；这里只编译和测试 `strategy` crate。
- 证据包新鲜度受上游限制（A2 因子滞后约 5 天；A3 部分品种不可用；A4 常为 PARTIAL），Manager 被要求据此下调 `evidence_quality`。
- 仓位按判断时的资金算预算；Rust 在入场时按 `risk_budget_cny` 与计划止损距离（下限 1 跳）算手数。
- 热加载（`POST /api/strategy/reload`）只有本机运行着 `trading-core` 时才会生效；否则 judge 记录警告并保留设置文件。Rust 侧代码在 `quant_trading` 子模块的 `resonance-strategy` 分支，需在部署机合并/部署。
