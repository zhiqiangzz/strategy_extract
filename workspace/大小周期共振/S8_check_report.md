# S8 check report

> **Agents: follow the English part only. The Chinese part at the end is a translation for human readers.**
> **说明：agent 只需参考英文；末尾中文仅供人类阅读。**

Generated: 2026-09-23T23:43:44+08:00

## Inputs
- summary: `workspace/大小周期共振/S5_summary_marked.md`
- terms: `workspace/大小周期共振/S6_terms_defined.json`
- formal: `workspace/大小周期共振/S7_formal.json`

## Script findings

Errors: 0, warnings: 0

- no errors

- no warnings

## Semantic review (agent)

Method: every numbered step of section 4, every bullet of section 5 and every bullet of section 6 of `S5_summary_marked.md` was matched against the defined terms (`S6_terms_defined.json`) and the callbacks (`S7_formal.json`); the resolutions in `S6_conflict_log.md` were checked against both files.

| Summary line | Terms / callbacks covering it | Result |
|---|---|---|
| §4.1 大周期方向判定; uncertain → no new entry, keep managing | CB01 T011; T005 (no regime judgement), T010, T002 | OK — T011 definition states outputs and the 'uncertain' consequence incl. the T021 exception |
| §4.2 only same-direction minor signals, filter counter-trend | T022 (constraint on CB02); CB01→CB02 constrains relation | OK |
| §4.3 enter on minor signal, set minor stop, close minor timeframe | CB02 T013 (limit price), CB03 T014 (distance), T018, T004/T023 sizing, T012 | OK — sizing derived from CB03 output and P02 |
| §4.4 favourable move on major tf → move stop to cost asap, not immediately | CB06 T024 → triggers T015; T016 cost = fill price; T017, T008 | OK |
| §4.5 trail stop by major signals, only tightens; exit by stop or active close on reversal | CB04 T020 (price-led, only tightens), T019; CB05 T021; T025 | OK |
| §5 initial stop very close, never by major tf | CB03 T014 | OK |
| §5 move to cost | CB06 T024, T015, T016 | OK |
| §5 trailing stop | CB04 T020 | OK |
| §5 exit path 1: stop hit (initial / cost / trailed) | T014, T015, T020 | OK — no callback needed; deterministic |
| §5 exit path 2: reversal → active close | CB05 T021, T025 | OK — conflict C1 resolution reflected in T011 and T021 |
| §5 no discretionary exit except reversal | T025 | OK |
| §5 light position = per-trade risk ≤ fixed fraction | T004, P02 T023 | OK |
| §5 consecutive stops accepted; re-entry allowed | T026, T013 (re-entry clause) | OK |
| §6 futures background, not instrument-limited | T030 | OK |
| §6 timeframe gap 1–2 levels, no second-level entry | P03 T027, T010, T012 | OK — default 1 level ≈ 4–6x, overridable |
| §6 30% win rate / payoff ≥ 3 | P01 T007 | OK — acceptance criterion, not runtime |
| §6 5–10% per trade is too expensive | T023 range note | OK |
| §6 ~70% of time no trend | T002 | OK — premise only |

Omissions or contradictions found: none. Every judgement the summary requires maps to exactly one callback; every deterministic rule maps to a constraint; no callback is un-invoked (CB01–CB06 all appear in §4/§5 and in the `sequence` chain).

Notes for the downstream implementer (not defects): input types `MarketData`, `Position`, `Instrument` in the stub are placeholders to be defined downstream; `minor_timeframe_entry_signal` returns an object `{decision, entry_price}`; `initial_stop_level` must declare whether its distance is points or percent.

Fixes applied in S8: none required.

---

# 中文版（仅供人类阅读；agent 请参考上方英文）

脚本发现：0 个错误，0 个警告（明细见上方英文部分）。语义审查由 agent 在上方 Semantic review 节填写：逐条核对执行步骤与出场风控所依赖的术语，记录遗漏与矛盾。
