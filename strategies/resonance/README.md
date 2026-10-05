# strategies/resonance — downstream implementation of 大小周期共振

> **Agents: follow the English part only (above the "中文版" divider). The Chinese part is a translation for human readers and adds no instructions.**
>
> **说明：agent 执行时只需参考上半部分的英文；下半部分的中文仅供人类阅读，内容相同，不含额外指令。**

## What this is

The first consumer of the strategy-formalizer output in `workspace/大小周期共振/final/`. The six callbacks of `callbacks_stub.py` are implemented in two places:

| S7 callback | Implementation | Where |
|---|---|---|
| CB01 `major_timeframe_direction` (T011) | LLM debate over the four-source evidence pack (技术指标 / 基本面 / 新闻 / 研报): opening statements of the long and the short side → up to three rounds of point-by-point rebuttal and reply, ended by a moderator → Manager | Python, `debate.py`, run by the user whenever they want |
| CB05 `major_trend_reversal` (T021) | Same run, when a position is open: `reversal = direction opposite to the position OR high-confidence uncertain` (recomputed in code, `apply_reversal_rule`) | Python |
| CB02 `minor_timeframe_entry_signal` (T013) | 30-minute bar close beyond the highest high (long) / lowest low (short) of the previous `entry_lookback` bars, only in the major direction (T022) | Rust `resonance.rs::on_minor_close` |
| CB03 `initial_stop_level` (T014) | Swing low/high of the last `stop_lookback` 30m bars ± 1 tick, capped at `stop_atr_cap_mult × ATR(30m)`, floored to one tick; lots = floor(`risk_budget_cny` / (distance × multiplier)) (T004/T023) | Rust, at the entry decision; stop armed at the fill |
| CB06 `favorable_move` (T024) | open profit ≥ `cost_r_multiple × R` on a 30m close, or daily close beyond entry by `cost_daily_atr_mult × ATR(1d)` → stop to entry price (T015/T016) | Rust `on_minor_close` / `on_daily_close` |
| CB04 `major_timeframe_trailing_stop` (T020) | lowest low / highest high of the last `trail_lookback_days` daily bars; only tightens, never beyond cost (T025) | Rust `on_daily_close` |
| exit path 1 (stop hit) | touch `StopLoss` trigger in the strategy's own `OrderEngine` | Rust, every tick |
| exit path 2 (reversal) | `reversal: true` in the setting file → close on the next in-session tick | Rust `reload` + `on_tick` |

Data flow:

```
Multi-Agent-Trading-Platform 汇总 run (技术指标 / 基本面 / 新闻 / 研报)
        │  scratchpad/<date>/   = everything known before trading day <date>
        ▼
uv run python -m strategies.resonance.cli judge --pack <dir> --account <user>
        │  8–17 × `claude -p --model opus --effort xhigh --json-schema` per variety
        │  runs/<date>/<symbol>/{long_thesis,short_thesis,debate_r<N>_{rebuttal,defence}_{long,short},debate_r<N>_moderator,manager}.{prompt.md,response.json}
        │  runs/<date>/<symbol>/debate.md   (the debate record)
        │  runs/<date>/<symbol>/flow.json   (data for the web page template in web/) + runs/index.json
        │  runs/<date>/decisions.json + report.md
        │  runs/<date>/order_plan.json   (orders for the trading system: entry range, lots, stop; see "Order plan")
        ▼
rust_core/.vntrader/resonance_setting_<user>.json   (direction, reversal, risk budget, params, warm-up bars)
        │  POST /api/strategy/reload?account=<user>
        ▼
trading-core → ResonanceStrategy (crates/strategy/src/resonance.rs) → CTP
        │  resonance_state_<user>.json (phase, bars), resonance_triggers_<user>.json (stops)
```

## The debate

Every call stands at the same decision time: before the open of the pack date D. The pack is what was known before D and the judgement is about the move from D onward, no matter when the judge is run. `prompts/_time_anchor.md` states this in every prompt, and the evidence block opens with a 数据覆盖 table computed in code (`Evidence.coverage()`): up to which date each source has data and which past dates it lacks relative to the last completed session before D. Only those past gaps (for example a 基本面 factor whose data ends five days earlier, or 新闻 unusable for the symbol) count as missing data; anything dated D or later is the future being judged.

1. **Opening (立论).** The long side (多方) and the short side (空方) each write a thesis with 3–6 arguments (论据): claim, reasoning chain, evidence ids. The code numbers them 多1… and 空1…; each becomes a thread.
2. **Rounds.** In a round the other side rebuts every thread in play (反驳), naming the attack: counterexample (举反例), limitation (局限性), insufficient support (论证不充分), missing or unclear causality (无因果或因果不明), data issue (数据问题). Then the owner answers each rebuttal (再反驳): maintain (坚持), narrow (收窄, with the narrower claim) or concede (认输). From round 2 on a rebuttal must answer the latest reply and may withdraw the objection. A conceded point or a withdrawn objection closes its thread; a side that says nothing about a thread is recorded as not having answered.
3. **Moderator (主持人).** After each round the moderator decides whether another round is worth holding and gives the reason; when it continues it names the threads to focus on. The code ends the debate without asking when no thread is contested or after `max_debate_rounds` (default and maximum 3). Every ruling is kept with its reason.
4. **Manager.** Rules on every thread (stands / weakened / refuted, with the reason) and decides the direction from the surviving arguments. The evidence pack is given to the manager only to check what the debaters cite; it may not add arguments of its own.

## Order plan

After the manager's decision the judge writes `runs/<date>/order_plan.json`, the orders for the trading system in its own file format (`plan_id`, `version`, `snapshot_id`, `created_at`, `orders[]`). The manager decides direction and confidence only; every number in an order is computed by `orders.py` from the parameter file `order_plan.toml`, the database and the evidence pack, so the same inputs always give the same plan.

For a symbol that is flat with direction long or short, one `open` order:

1. Reference price `P`: the last trade before the decision time (the pack date at `decision_clock`, 09:00 by default; when the plan is made earlier, the last trade before now). A plan rebuilt days later therefore still uses the price of that morning.
2. Entry range: `P ± range_atr × ATR(1d)`, rounded inward to the price tick, written as `limit_price = [low, high]`. The trading system may enter anywhere inside it on the minor timeframe.
3. Budget: `default_cny × confidence` (100 000 × 0.68 = 68 000), or a per-symbol budget from `[budget.symbols]`.
4. Loss limit: `max_loss_cny × confidence` (15 000 × 0.68 = 10 200). Like the budget, it shrinks with the confidence; `scale_by_confidence = false` under `[risk]` or `[budget]` uses the full amount.
5. Lots: the smaller of `floor(budget / (high × lot size × margin ratio))` and `floor(loss limit / (min_stop_atr × ATR × lot size))`. The second keeps the stop at least `min_stop_atr` daily ATRs away; without it a large position would get a stop inside ordinary daily noise.
6. Stop: `loss limit / (lots × lot size)` away from the worst fill of the range (the top for a buy, the bottom for a sell), rounded toward the entry. A fill at the worst price that is stopped out loses at most the loss limit; any other fill in the range loses less. The stop always lies outside the range.
7. Target: `target_r ×` the stop distance beyond the worst fill (3 by default; 0 writes null).

Direction uncertain gives no order. An open position that the judgement reverses gives a `close` order (no prices, `position_id` = the position's vt_symbol), followed by an `open` order that `depends_on` it when the new direction is the opposite one. A position in the same direction gives no order. A symbol also gets no order when one lot does not fit the budget or the loss limit, or when the database has no main contract, margin ratio or trade for it; the reason is listed in `report.md` and in `order_plan.audit.json`, which also records how every order was sized.

Fixed fields: `strategy_id` `major_minor_timeframe_resonance`, `source` `manager`, `plan_id` `manager-<date>`, `snapshot_id` `pack-<date>`, `created_at` the decision time, `valid_until` 15:00 of the pack date, `hold_overnight` true. All of them and every number above are parameters in `order_plan.toml`; an unknown key in that file is an error. The margin ratio in the database is the exchange standard; `[margin] addon` adds a broker's surcharge.

The Rust `ResonanceStrategy` does not read this plan. It still takes `resonance_setting_<user>.json` and applies its own entry and stop rules; the two outputs exist side by side.

## Files

| File | Purpose |
|---|---|
| `config.py` | `ResonanceParams` (rule parameters shared with Rust) and `JudgeConfig` (model, effort, evidence level, round limit, moderator effort, workers, cache). |
| `evidence.py` | Loads a pack, works out the last completed session before the pack date, and renders one symbol's evidence: decision time, 数据覆盖 table, then the four sources with stable ids (`技术指标.macd`, `基本面.curve`, `新闻.20260929_001`, `研报.ev1`, `日线`). The upstream directory names of a pack appear only in its `SOURCES` table. |
| `claude_cli.py` | One structured call through the logged-in Claude Code CLI (`claude -p … --json-schema`), nested-session safe, transcripts recorded. |
| `prompts/*.md` | Role prompts: `long_thesis`, `short_thesis`, `debate_rebuttal`, `debate_defence` (one template each, filled per side), `debate_moderator`, `manager`. `_definitions.md` (T011/T005/T021/T010/T007 verbatim) and `_time_anchor.md` (decision time) are embedded in every prompt. |
| `schemas.py` | pydantic models for the LLM outputs (Thesis, RebuttalTurn, DefenceTurn, ModeratorRuling, Decision), the assembled `Debate` record, the order plan (`OrderPlan`, `Order`), the hand-off `ResonanceSetting`, and the JSON schemas sent to the CLI (every field required, no extras). |
| `debate.py` | `judge_symbol` (opening statements, `run_debate`, manager, reversal rule, cache), the Markdown rendering of threads and rulings, and `judge_many` (thread pool over symbols; the two sides of a step run concurrently). |
| `positions.py` | Open positions and capital from the control API (`/api/positions`, `/api/account`) or a file. |
| `signal_writer.py` | Decisions → setting file: main contract from the v2 DB, `VARIETY_META` multipliers/ticks, risk budget, warm-up bars (30m from `tick_ctp`, daily from `market_data`), atomic write, reload call. |
| `export_ticks.py` | Exports `tick_ctp` ticks of a contract for the Rust replay example. |
| `flow.py` | Builds `<symbol>/flow.json` after every run: the calls in order with their timing, cost, prompt composition and results, what the code did in between, and the threads. Also rebuilds `runs/index.json`. This is the data contract of the web page (`FLOW_SCHEMA`). |
| `orders.py`, `order_plan.toml` | The order plan: parameters (`OrderPlanConfig`), market data from the v2 DB (`DbMarketData`: main contract, margin ratio, lot size, last trade before the decision time), sizing (`size_open`), `build_order_plan`, and the plan and audit files. |
| `serve.py` | Localhost server for the built page template and its data; under `/runs/` it serves only `index.json` and `flow.json`. |
| `web/` | The page template: a Vite + Vue 3 + UnoCSS project with the toolchain and theme of `third_party/quant_trading/web/frontend`. It holds no data and reads the flow files. See `web/README.md`. |
| `cli.py` | `judge`, `report`, `plan` and `web` commands; renders `report.md` and `<symbol>/debate.md`, writes the flow files and the order plan. |
| `tests/` | Fake-runner tests: evidence and coverage table, decision-time block, debate rounds (moderator, round limit, focus, concessions, withdrawn objections, unanswered threads), reversal rule, cache, report, flow data and index, the server's allow-list, the order plan (fake market: sizing, invariants, skip reasons, positions, parameter file, CLI), setting round-trip, positions parsing. `make_web_fixture.py` regenerates the sample flow the page template is tested with. |
| `runs/` | Per-pack decisions, reports and debate records; the per-call prompts/responses and decision caches are git-ignored. `runs/2026-09-29/` is the output of the earlier single-pass version. |

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
# 1. judge (dry run: decisions, report and debate records only; 8–17 opus/xhigh calls per variety depending on the rounds held;
#    a one-round debate measured ≈ $3.4 and ≈ 10 min per variety on the 2026-09-30 pack)
uv run python -m strategies.resonance.cli judge --pack scratchpad/2026-09-30 --symbols CU,LC,AG,TA,P --workers 5 --dry-run --capital 1000000
#    --max-rounds 1|2|3 caps the debate (default 3; the moderator may stop earlier); --workers N symbols at a time
# 2. full: writes rust_core/.vntrader/resonance_setting_<user>.json (DB lookups + warm-up) and reloads the core
uv run python -m strategies.resonance.cli judge --pack scratchpad/2026-09-30 --account <user>
#    add --no-reload to only write the file; --positions file.json / --capital N when the core is not running
#    the order plan is written to runs/<date>/order_plan.json (needs the v2 DB); --plan-out FILE copies it, --no-plan skips it
#    re-render report.md, the debate records and the flow files from decisions.json: cli report --pack-date 2026-09-30
#    recompute the order plan after editing order_plan.toml, without judging again:  cli plan --pack-date 2026-09-30 [--plan-config FILE]
# 3. web page of a run (template in web/, data written by the judge; node comes from pixi)
pixi run web-install && pixi run web-build           # once, and again after changing the template
uv run python -m strategies.resonance.cli web        # http://127.0.0.1:8770/#2026-09-30/LC
#    judge, report and web all work under strategies/resonance/runs; --runs-dir DIR moves them elsewhere (give all three the same DIR)
# 4. Rust (inside third_party/quant_trading/rust_core, toolchain from this repo's pixi env)
PATH=../../../.pixi/envs/default/bin:$PATH cargo test -p strategy
cargo run -p strategy --example resonance_replay -- ticks.json resonance_setting.json
uv run python -m strategies.resonance.export_ticks --variety CU --begin 2026-09-15 --end 2026-09-26 --out ticks.json
```

Positions come from `GET /api/positions?account=`; capital from `GET /api/account?account=` (`balance`). A cached decision (same pack date, symbol, prompt version, model, effort, evidence level, round limit and position state) is reused for free; `--no-cache` forces a rerun. With `--workers N` up to 2 × N `claude` processes run at once, because the two sides of a step run concurrently.

## Limitations

- No backtest: trading-core has no replay harness; `resonance_replay` dry-runs the Rust rules on exported ticks with next-tick fills and no slippage model.
- `trading-core` itself must be built on the deployment machine (CTP SDK + bindgen); only the `strategy` crate is built and tested here.
- The evidence pack is only as complete as its sources: some 基本面 factors end days before the last session, 新闻 may be unusable for a symbol, 研报 is often PARTIAL. These past gaps are listed in the 数据覆盖 table and are the only basis for lowering `evidence_quality`.
- The `claude` CLI tells the model the run date and this cannot be switched off (a custom system prompt does not remove it); the decision-time block in every prompt is what keeps the judgement anchored to the pack date.
- The moderator and the round limit bound the cost, not the quality: a debate can stop with threads still contested, and the manager then rules on them as they stand.
- Risk sizing uses the capital given at judge time; the Rust strategy sizes at entry from `risk_budget_cny` and the planned stop distance (floored to one tick).
- Live reload (`POST /api/strategy/reload`) is only exercised when a `trading-core` is running on the machine; the judge logs a warning and leaves the setting file in place otherwise. The Rust side lives on branch `resonance-strategy` of the `quant_trading` submodule and must be merged/deployed there.

---

# 中文版（仅供人类阅读；agent 请参考上方英文）

## 这是什么

strategy-formalizer 在 `workspace/大小周期共振/final/` 产出的第一个下游实现。`callbacks_stub.py` 的六个回调分两处实现：

| S7 回调 | 实现 | 位置 |
|---|---|---|
| CB01 大周期方向判定（T011） | 对四个来源（技术指标 / 基本面 / 新闻 / 研报）的证据包做 LLM 辩论：多方、空方立论 → 最多三轮逐条反驳与再反驳，由主持人决定何时终止 → Manager | Python `debate.py`，用户随时运行 |
| CB05 趋势反转（T021） | 同一次运行，持仓时：`reversal = 方向与持仓相反 或 高置信度不确定`（代码重算，`apply_reversal_rule`） | Python |
| CB02 小周期入场信号（T013） | 30 分钟 K 线收盘价突破此前 `entry_lookback` 根的最高高点（多）/最低低点（空），且与大周期同向（T022） | Rust `resonance.rs::on_minor_close` |
| CB03 小周期止损（T014） | 最近 `stop_lookback` 根 30m K 线的摆动低/高点 ± 1 跳，上限 `stop_atr_cap_mult × ATR(30m)`，下限 1 跳；手数 = floor(`risk_budget_cny` / (距离 × 乘数))（T004/T023） | Rust，入场决策时算，成交后武装止损 |
| CB06 有利运动（T024） | 30m 收盘浮盈 ≥ `cost_r_multiple × R`，或日线收盘超过入场价 `cost_daily_atr_mult × ATR(1d)` → 止损移到入场价（T015/T016） | Rust `on_minor_close` / `on_daily_close` |
| CB04 大周期移动止损（T020） | 最近 `trail_lookback_days` 根日线的最低低点/最高高点；只进不退，不低于成本（T025） | Rust `on_daily_close` |
| 出场路径一（打止损） | 策略自带 `OrderEngine` 的 touch 止损触发 | Rust，每个 tick |
| 出场路径二（趋势反转） | 设置文件 `reversal: true` → 下一个交易时段内的 tick 平仓 | Rust `reload` + `on_tick` |

数据流见英文部分的图：汇总运行产出的证据包（`scratchpad/<日期>/`，即该交易日之前已知的全部信息）→ `cli judge`（每品种 8–17 次 `claude -p`，留痕到 `runs/<日期>/<品种>/`，辩论记录为 `debate.md`，网页模板的数据为 `flow.json`，另有 `runs/index.json`）→ `resonance_setting_<user>.json` → `POST /api/strategy/reload` → trading-core 中的 `ResonanceStrategy` → CTP。

## 辩论

所有调用都站在同一个决策时点：包日期 D 开盘前。证据包是 D 之前已知的信息，判断的是从 D 起的走势，与判断程序何时运行无关。`prompts/_time_anchor.md` 把这一点写进每个提示词；证据块开头是代码算出的数据覆盖表（`Evidence.coverage()`）：每个来源的数据截至哪天、相对 D 之前最后一个完整交易日缺哪些过去的日期。只有这些过去的缺口（例如某个基本面因子的数据早五天就断了，或该品种的新闻不可用）才算数据缺失；D 当天及之后的一切都是被判断的未来。

1. **立论。** 多方和空方各写一份立论，含 3–6 条论据：结论、推理链、证据编号。代码把它们编号为 多1… 和 空1…，每条成为一个线程。
2. **多轮辩论。** 每一轮先由对方逐条反驳仍在辩的线程，并指明攻击类型：举反例、局限性、论证不充分、无因果或因果不明、数据问题；再由论据所有方逐条再反驳：坚持、收窄（给出收窄后的论据）或认输。第二轮起，反驳必须针对对方上一轮的再反驳，也可以撤回异议。认输或撤回异议即关闭线程；对某个线程不发言的一方被记为未回应。
3. **主持人。** 每轮结束后由主持人判断是否值得再打一轮并给出理由；继续时点名下一轮聚焦的线程。已无争议线程、或达到 `max_debate_rounds`（默认值和上限都是 3）时由代码直接终止。每次判断及其理由都会保留。
4. **Manager。** 对每个线程给出裁定（成立 / 被削弱 / 被驳倒及理由），并根据存活的论据决定方向。证据包只供 Manager 核对双方的引用，不得自行引入新论点。

## 订单计划

Manager 给出决策后，判断层写出 `runs/<日期>/order_plan.json`，即按交易系统自己的文件格式（`plan_id`、`version`、`snapshot_id`、`created_at`、`orders[]`）给出的订单。Manager 只决定方向和置信度；订单里的每个数字都由 `orders.py` 根据参数文件 `order_plan.toml`、数据库和证据包算出，相同输入必得相同计划。

空仓且方向为多或空的品种出一张 `open` 单：

1. 参考价 `P`：决策时点之前的最后一笔成交（决策时点为包日期的 `decision_clock`，默认 09:00；若生成计划时还没到，则取当前时间之前的最后一笔）。因此几天后重新生成的计划仍然使用当天早上的价格。
2. 入场区间：`P ± range_atr × 日线 ATR`，向区间内侧取整到最小变动价位，写成 `limit_price = [下沿, 上沿]`。交易系统可在小周期上于区间内任意位置入场。
3. 预算：`default_cny × 置信度`（100 000 × 0.68 = 68 000），或 `[budget.symbols]` 里按品种设置的预算。
4. 亏损上限：`max_loss_cny × 置信度`（15 000 × 0.68 = 10 200）。和预算一样随置信度缩小；把 `[risk]` 或 `[budget]` 下的 `scale_by_confidence` 设为 false 则使用全额。
5. 手数：取 `floor(预算 / (上沿 × 每手数量 × 保证金比率))` 与 `floor(亏损上限 / (min_stop_atr × ATR × 每手数量))` 中较小者。后者保证止损距离不小于 `min_stop_atr` 倍日线 ATR；没有它，仓位大的品种止损会落在正常的日内波动之内。
6. 止损：距离区间内最差成交价（买单为上沿，卖单为下沿）`亏损上限 / (手数 × 每手数量)`，向入场方向取整。按最差价成交后被止损，亏损不超过亏损上限；区间内其他位置成交亏损更小。止损一定在区间之外。
7. 目标：在最差成交价之外 `target_r ×` 止损距离处（默认 3；配成 0 则填 null）。

方向不确定时不出单。持仓被判定反转时出一张 `close` 单（不带价格，`position_id` 为持仓的 vt_symbol）；新方向相反时，随后有一张 `depends_on` 它的 `open` 单。持有同向仓位时不出单。一手放不进预算或亏损上限，或数据库里没有该品种的主力合约、保证金比率或成交时，同样不出单；原因列在 `report.md` 和 `order_plan.audit.json` 里，后者还记录每张单是怎么算出来的。

固定字段：`strategy_id` 为 `major_minor_timeframe_resonance`，`source` 为 `manager`，`plan_id` 为 `manager-<日期>`，`snapshot_id` 为 `pack-<日期>`，`created_at` 为决策时点，`valid_until` 为包日期 15:00，`hold_overnight` 为 true。这些字段和上面所有数字都是 `order_plan.toml` 里的参数；该文件出现未知的键会报错。数据库里的保证金比率是交易所标准，`[margin] addon` 用于加上期货公司的加收。

Rust 的 `ResonanceStrategy` 不读这份计划，它仍然读取 `resonance_setting_<user>.json` 并按自己的规则入场和止损；两个出口并存。

## 文件

见英文部分的表格。`orders.py` 与 `order_plan.toml` 负责订单计划：参数、来自 v2 库的行情（主力合约、保证金比率、每手数量、决策时点前的最后一笔成交）、手数与止损的计算，以及计划文件和审计文件。`flow.py` 在每次运行后生成 `<品种>/flow.json`（按顺序的调用及其时间、费用、提示词构成和返回结果，调用之间代码做的事，以及各线程）并重建 `runs/index.json`，这是网页的数据约定；`serve.py` 是页面模板及其数据的本机服务，`/runs/` 下只放行 `index.json` 和 `flow.json`；`web/` 是页面模板（Vite + Vue 3 + UnoCSS 工程，工具链和主题与 `third_party/quant_trading/web/frontend` 一致），本身不含数据，详见 `web/README.md`。上游证据包的目录名只出现在 `evidence.py` 的 `SOURCES` 表里；`runs/2026-09-29/` 是早先单次质证版本的产出。Rust 侧在 `third_party/quant_trading` 的 `resonance-strategy` 分支：`bars.rs`（tick → 30m/日线、ATR、Donchian）、`resonance.rs`（策略本体与 serde 结构，7 个测试）、`examples/resonance_replay.rs`（导出 tick 的干跑回放）、`main.rs`/`accounts.rs`（注册、每策略独立触发文件、订阅）、`lib.rs`（`symbols_of`）。

## 交接文件

格式见英文部分。Rust 侧语义：`long`/`short` 且空仓 → 在 30m 收盘找入场；`uncertain` → 不开新仓、已有持仓继续管理；`reversal: true` 且持仓 → 下一个交易时段内 tick 平仓。新文件里消失的合约：空仓则移除，持仓则保留管理且方向置 `uncertain`（绝不丢下持仓）。

## 运行手册

命令见英文部分：`cli judge --dry-run` 只出决策、报告和辩论记录（每品种 8–17 次 opus/xhigh 调用，取决于辩论打了几轮；在 2026-09-30 证据包上实测，一轮辩论每品种约 3.4 美元、约 10 分钟）；`--max-rounds` 设置轮数上限（默认 3，主持人可提前终止），`--workers N` 设置同时判断的品种数；订单计划写到 `runs/<日期>/order_plan.json`（需要能连上 v2 库；`--plan-out 文件` 另存一份，`--no-plan` 跳过）；`cli report` 从 decisions.json 重新渲染报告、辩论记录和 flow 文件；`cli plan --pack-date 日期` 在修改 `order_plan.toml` 之后不重新判断、直接重算订单计划；`pixi run web-install && pixi run web-build` 构建网页模板（一次性，改了模板后重做；node 来自 pixi），`cli web` 在 http://127.0.0.1:8770/ 提供页面和数据；`judge`、`report`、`web` 默认都在 `strategies/resonance/runs` 下读写，`--runs-dir 目录` 可换到别处（三个命令要传同一个目录）；去掉 `--dry-run` 则写设置文件（含 DB 查询与预热 K 线）并通知 core 重载（`--no-reload` 只写文件）；Rust 侧在 `rust_core` 内用本仓库 pixi 环境的工具链 `cargo test -p strategy`，`resonance_replay` 用 `export_ticks` 导出的 tick 回放。持仓来自 `/api/positions`，资金来自 `/api/account` 的 `balance`。同一（包日期、品种、提示词版本、模型、effort、证据粒度、轮数上限、持仓状态）的决策会被缓存复用，`--no-cache` 强制重跑。同一步的多空两侧并行调用，所以 `--workers N` 时最多同时有 2 × N 个 `claude` 进程。

## 局限

- 没有回测：trading-core 无回放框架；`resonance_replay` 用下一 tick 按委托价成交、无滑点模型。
- `trading-core` 需在部署机编译（CTP SDK + bindgen）；这里只编译和测试 `strategy` crate。
- 证据包的完整程度受上游限制：部分基本面因子的数据在最后交易日之前若干天就断了，新闻对个别品种不可用，研报常为 PARTIAL。这些过去的缺口列在数据覆盖表里，也是下调 `evidence_quality` 的唯一依据。
- `claude` CLI 会把运行日期告诉模型，且无法关闭（自定义系统提示也去不掉）；让判断锚定在包日期上的是每个提示词里的决策时点段落。
- 主持人和轮数上限约束的是成本而不是质量：辩论可能在仍有争议线程时终止，此时由 Manager 按现状裁定。
- 仓位按判断时的资金算预算；Rust 在入场时按 `risk_budget_cny` 与计划止损距离（下限 1 跳）算手数。
- 热加载（`POST /api/strategy/reload`）只有本机运行着 `trading-core` 时才会生效；否则 judge 记录警告并保留设置文件。Rust 侧代码在 `quant_trading` 子模块的 `resonance-strategy` 分支，需在部署机合并/部署。
