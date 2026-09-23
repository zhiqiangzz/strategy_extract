# Strategy summary / 策略总结 — 大小周期共振

> Agents: read English only. 中文供人阅读。

<!-- section: summary -->
## 1. Strategy summary / 策略总结

用大周期判断方向，小周期入场以降低止损成本，出现有利运动后尽快但不是立刻把止损移到成本价，形成零成本持仓，之后只看大周期，按大周期信号移动止损直到打止损或大周期反转出场。

<!-- section: one_liner -->
## 2. One-line overview / 一句话概述

大周期定方向，小周期定时机，移损至成本后让利润奔跑。

<!-- section: premise -->
## 3. Premise and philosophy / 策略前提与理念

- 无法实时区分趋势与震荡，所以不判断，只用一种手法。
- 盈亏比阈值 ≥ 3 时 30% 胜率仍是正期望。
- 零成本持仓是整套理念的灵魂。

<!-- section: execution_steps -->
## 4. Execution steps / 执行步骤

1. **大周期方向判定**：输出 多/空/不确定；不确定则不交易。
2. 等待 **小周期入场信号**，逆向信号过滤掉；大小周期级别差为 1~2 个数量级。
3. 入场后设小周期止损；当 **有利运动确认** 时把止损移到成本价（尽快但不是立刻）。
4. 关闭小周期，只看大周期。

<!-- section: exit_and_risk -->
## 5. Exit and risk control / 出场与风控

- 按 **移动止损线位置** 移动止损，止损只进不退。
- 打止损出场，或 **大周期趋势反转** 时清仓。

<!-- section: scope_and_params -->
## 6. Scope and parameters / 适用范围与参数

- 多品种，主力合约。大小周期级别差：1~2 个数量级。
