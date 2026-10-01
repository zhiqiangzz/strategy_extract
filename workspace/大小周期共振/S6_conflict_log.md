# S6 conflict log — 大小周期共振

> Agents: one entry per contradiction found while defining terms (both quotes, the dialog id where the user decided, the edit made). 中文条目供人阅读。

## Entries / 条目

(none yet)

### C1 — D002 与 D026 关于“不确定”的后果 / consequence of an 'uncertain' direction
- 冲突：D002 答“T011 输出不确定时不开新仓，已有持仓按原规则继续管理”；D026 答“趋势反转包括 T011 判定为置信度较高的不确定”，即高置信度的不确定要清仓。
- 裁决：D027 选 (c)。低置信度的不确定 → 继续管理持仓；高置信度的不确定 → 由 T021 判定为反转并清仓；“置信度较高”不量化，由下游 agent 在 T021 内判断。
- 修改：T011 定义补充“除非该不确定被 T021 判定为置信度较高的反转”；T021 定义写明两种反转情形；总结第 4/5 节的“趋势反转”按 T021 定义理解，措辞不变。

### S1 — 总结同步 / summary kept in sync with definitions（非冲突，记录改动）
- 第 4 节第 1 步补“判定为不确定时不开新仓，已有持仓按原规则继续管理”（D002/D027）。
- 第 5 节“仓位”补“每笔交易的风险不超过本金的一个固定比例”（D015）。

## Closing / 收尾

Consistency checklist (references/consistency_rules.md §1–8) walked over all 25 live terms and the summary on 2026-09-23: exit paths (stop / T021 reversal, T025), stop direction and trigger (T015, T020, T024), direction filter and the 'uncertain' consequence (T011, T022, T021), scope (T030, T010, T012, T027), parameters stated once (T007, T023, T027), wording, coverage of every step and bullet, no dialog-added terms. No further conflicts found on 2026-09-23.

2026-09-23 已对全部 25 个存活术语和总结走完一致性清单，未再发现矛盾。

### S2 — 回调调度补充（2026-10-01，skill 新增 schedule 后重开 S6）
- D030–D035 为 6 个回调补充了调度：T011、T013、T014、T024、T020 为 on_demand/sync（由下游调用方决定频率；T014 在入场时调用一次），T021 为 on_demand/async（允许异步慢判断）。
- 一致性：入场前（T011、T013）与持仓期（T024、T020、T021）的判断都由调用方定频率，止损触发由 driver 在 tick 上内置；与总结第 4、5 节无矛盾。未再发现矛盾。
