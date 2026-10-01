# S8 check report

> **Agents: follow the English part only. The Chinese part at the end is a translation for human readers.**
> **说明：agent 只需参考英文；末尾中文仅供人类阅读。**

Generated: 2026-10-01T18:18:22+08:00

## Inputs
- summary: `workspace/大小周期共振/S5_summary_marked.md`
- terms: `workspace/大小周期共振/S6_terms_defined.json`
- formal: `workspace/大小周期共振/S7_formal.json`

## Script findings

Errors: 0, warnings: 0

- no errors

- no warnings

## Semantic review (agent)

Method: every numbered step of section 4, every bullet of section 5 and every bullet of section 6 of `S5_summary_marked.md` was matched against the defined terms (`S6_terms_defined.json`), the callbacks (`S7_formal.json`) and the flow rules that implement them (`S7_formal.json` → `flow`, rendered in `S7_strategy_driver.py`); the resolutions in `S6_conflict_log.md` were checked against all files.

| Summary line | Terms / callbacks covering it | Flow rule(s) | Result |
|---|---|---|---|
| §4.1 大周期方向判定; uncertain → no new entry, keep managing | CB01 T011; T005, T010, T002 | F01 (every evaluation); F02 only when direction is definite | OK — the T021 exception for high-confidence uncertain is F05 |
| §4.2 only same-direction minor signals, filter counter-trend | T022 (constraint on CB02) | F02 passes `direction` into CB02 and only runs when it is long/short | OK |
| §4.3 enter on minor signal, set minor stop, close minor timeframe | CB02 T013 (EntryDecision), CB03 T014 (StopDistance), T018, T004/T023 sizing, T012 | F03: CB03 → `enter` → IN_POSITION; sizing by `Account.size_from_risk` | OK — after F03 nothing in the IN_POSITION block touches minor-timeframe data (T018) |
| §4.4 favourable move on major tf → move stop to cost asap, not immediately | CB06 T024 → T015; T016 cost = fill price; T017, T008 | F06 (only while `not position.stop_at_cost`) → `move_stop_to_cost` | OK |
| §4.5 trail stop by major signals, only tightens; exit by stop or active close on reversal | CB04 T020, T019; CB05 T021; T025 | F07 (`move_stop`, runtime enforces only-tightens); F04 (`close:stop`); F05 (`close:reversal`) | OK |
| §5 initial stop very close, never by major tf | CB03 T014 | F03 | OK |
| §5 move to cost | CB06 T024, T015, T016 | F06 | OK |
| §5 trailing stop | CB04 T020 | F07 | OK |
| §5 exit path 1: stop hit (initial / cost / trailed) | T014, T015, T020 | F04 (built-in `stop_hit`, evaluated before everything else in position) | OK |
| §5 exit path 2: reversal → active close | CB05 T021, T025 | F05 | OK — conflict C1 resolution reflected in T011/T021 and in F05's position before F06/F07 |
| §5 no discretionary exit except reversal | T025 | no other `close` rule exists | OK |
| §5 light position = per-trade risk ≤ fixed fraction | T004, P02 T023 | `Account.per_trade_loss_ratio` in `_enter` | OK |
| §5 consecutive stops accepted; re-entry allowed | T026, T013 | F04 → FLAT, then F02/F03 again (dry-run `stopped_out_then_reenter`) | OK |
| §6 futures background, not instrument-limited | T030 | `StepContext.instrument` | OK |
| §6 timeframe gap 1–2 levels, no second-level entry | P03 T027, T010, T012 | downstream chooses `MarketData.timeframe` | OK |
| §6 30% win rate / payoff ≥ 3 | P01 T007 | not runtime | OK |
| §6 5–10% per trade is too expensive | T023 range note | — | OK |
| §6 ~70% of time no trend | T002 | — | OK |

Flow order check: the rule blocks in `S7_strategy_driver.py` appear in the order F01…F07, which is the order of §4 (direction → filtered entry → enter+stop → move to cost → trail/exit), with the two deterministic exits (F04 stop hit, F05 reversal) placed before stop management inside the in-position block. Both dry-run scenarios (`trend_then_reversal`, `stopped_out_then_reenter`) pass; the second exercises the only-tightens guard implicitly (a looser trailing stop at tick 5 of scenario 1 is ignored).

Omissions or contradictions found: none. Every judgement the summary requires maps to exactly one callback and one flow rule; every deterministic rule maps to a constraint or to driver runtime; no callback is un-invoked.

Notes for the downstream implementer (not defects): the stub defines the standard interface dataclasses (Bar, MarketData, Instrument, Position, EntryDecision, StopDistance) that the downstream agent fills from its own data layer; `ExecutionPort` must be implemented to execute the driver's actions and keep `Position` current (set `stop_at_cost` on a `cost` stop move); `minor_timeframe_entry_signal` returns `EntryDecision`; `initial_stop_level` returns `StopDistance` with an explicit unit; the driver is cadence-agnostic (call `step()` whenever a new `StepContext` is available).

Fixes applied in S8: none required.

---

# 中文版（仅供人类阅读；agent 请参考上方英文）

脚本发现：0 个错误，0 个警告（明细见上方英文部分）。语义审查由 agent 在上方 Semantic review 节填写：逐条核对执行步骤与出场风控所依赖的术语，记录遗漏与矛盾。
