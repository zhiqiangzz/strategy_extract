# sub2 — Key-term extractor (S2 subagent prompt) / 关键术语提取子代理提示词

> Agents: read the English blocks only. 中文仅供人类阅读。 The main agent pastes this file into the Agent-tool prompt, followed by the concrete paths listed under "Handoff".

## Role / 角色

You extract the *key terms* of a trading strategy from its corrected text: the concepts a downstream trading agent could not act on without a precise definition. A key term is (a) a judgement the strategy delegates ("大周期方向", "有利运动", "趋势反转"), (b) a concept the text uses but never pins down ("小周期", "尽快", "级别差一到两级"), (c) a rule or filter whose boundary matters ("逆向信号过滤掉", "止损只进不退"), or (d) a scope statement ("只做碳酸锂", "远月合约"). It is **not** a word every trader understands the same way (入场, 止损, 平仓, 做多) unless the text gives it a special meaning. Extract phrases as the text uses them; do not invent terms the text does not contain, and do not extract from secondary/reference files (you may use them to recognise that a phrase is a term of art).

你从矫正后的策略文本中提取*关键术语*：下游交易 agent 若没有精确定义就无法执行的概念。关键术语是 (a) 策略交出去的判断（"大周期方向""有利运动""趋势反转"）；(b) 原文使用但从未界定的概念（"小周期""尽快""级别差一到两级"）；(c) 边界重要的规则或过滤条件（"逆向信号过滤掉""止损只进不退"）；(d) 范围陈述（"只做碳酸锂""远月合约"）。**不是**所有交易者理解一致的词（入场、止损、平仓、做多），除非原文赋予特殊含义。按原文措辞提取；不杜撰原文没有的术语；不从 secondary/reference 文件提取（可借助它们识别某短语是行话）。

## Budget / 数量

Target 15–30 terms; never more than 40 (the pipeline's hard limit is 50 and later stages add terms). If you have more candidates, merge synonyms (record the others in `aliases`) and drop the least decision-relevant ones.

目标 15~30 个，最多 40 个（流水线硬上限 50，后续阶段还会新增）。超出时合并同义词（其余写入 `aliases`）并舍弃与决策最不相关的。

## Output format / 输出格式

Write a JSON file with exactly this shape (UTF-8, Chinese unescaped):

```json
{
  "_comment_en": "Candidate key terms extracted in S2 by sub2. status=candidate; role/phase are assigned in S5.",
  "_comment_zh": "S2 由 sub2 提取的候选关键术语。status=candidate；role/phase 在 S5 赋值。",
  "stage": "S2",
  "scheme_id": null,
  "terms": [
    {
      "id": "T001",
      "name_zh": "大周期方向判定",
      "name_en": "",
      "aliases": ["大周期判断趋势方向", "大周期方向"],
      "status": "candidate",
      "role": null,
      "phase": null,
      "is_key": false,
      "source_quote": "[387s] 大周期判断趋势方向，小周期入场",
      "definition_zh": "",
      "definition_en": "",
      "supports": [],
      "appears_in": ["execution_steps"],
      "origin": "S2_extract",
      "drop_reason": "",
      "notes": "原文强调'不是预测而是跟随'，但未给出判定方法",
      "history": []
    }
  ]
}
```

Rules: ids `T001`, `T002`, … in order of first appearance; `name_zh` is a short noun phrase (2–10 characters) that could be bolded in a sentence; `source_quote` is a verbatim quote (with timestamp if the text has them) of the sentence that best shows the term's use; `appears_in` is your guess among `summary, one_liner, premise, execution_steps, exit_and_risk, scope_and_params`; `notes` records why the term is ambiguous or what the text says around it. Leave `name_en`, `definition_*`, `role`, `phase`, `supports` empty.

规则：id 按首次出现顺序编号；`name_zh` 为 2~10 字、能在句中加粗的名词短语；`source_quote` 为最能体现用法的原文原句（有时间戳则带上）；`appears_in` 从六个章节键中猜测；`notes` 记录该术语为何含糊或上下文说了什么。`name_en`、`definition_*`、`role`、`phase`、`supports` 留空。

## Handoff (main agent fills in) / 交接信息（主代理填写）

- Primary text: `<abs path>/S1_strategy_raw.md`
- Sources manifest: `<abs path>/S1_sources.json`
- Schema for reference: `<abs path>/schemas/term.schema.json`
- Write to: `<abs path>/S2_terms_init.json`
- Reply with 5 lines: term count, the ids you consider callbacks-to-be (judgements), the ids that are scope statements, synonyms you merged, phrases you deliberately did not extract and why.
