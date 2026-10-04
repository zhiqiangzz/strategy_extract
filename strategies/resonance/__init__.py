"""
Agents: read the English part only. 中文仅供人类阅读。

strategies.resonance — downstream implementation of the 大小周期共振 strategy
produced by the strategy-formalizer skill (workspace/大小周期共振/final/).

The six callbacks are split in two: the major-timeframe judgements
(direction, trend reversal) are an LLM debate between a long and a short
side over the evidence pack of Multi-Agent-Trading-Platform (技术指标, 基本面,
新闻, 研报), run by the user whenever they want (this package); the tick-driven callbacks (entry signal, initial stop, favourable
move, trailing stop) are a persistent Rust strategy in
third_party/quant_trading/rust_core. The two sides meet in
`resonance_setting_<account>.json`, written by `signal_writer` and consumed by
the Rust strategy through the control API `reload` endpoint.

strategies.resonance 是 strategy-formalizer skill 产出的 大小周期共振 策略
（workspace/大小周期共振/final/）的下游实现。六个回调一分为二：大周期判断（方向、趋势反转）
是多方与空方围绕 Multi-Agent-Trading-Platform 的证据包（技术指标、基本面、新闻、研报）做 LLM 辩论，
由用户随时运行（本包）；
tick 驱动的回调（入场信号、初始止损、有利运动、移动止损）是 third_party/quant_trading/rust_core
中的常驻 Rust 策略。两边通过 `resonance_setting_<account>.json` 衔接：由 `signal_writer` 写出，
Rust 策略经 control API 的 reload 接口读取。
"""
