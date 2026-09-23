# Bilingual style / 双语写作规范

> Agents: read the English blocks only. 中文仅供人类阅读。

## Markdown files / Markdown 文件

Every `.md` written by this skill (skill docs, stage docs, workspace summaries, reports, logs) starts with a banner line telling agents to read only the English and humans that the Chinese says the same. Then, per section: the complete English block first (one or more paragraphs, a table, a list), and directly below it the complete Chinese block. Never alternate sentence by sentence and never put the Chinese inside the English paragraph in brackets. Headings are `English / 中文`. Tables may carry both languages in one cell separated by ` / ` when a column would otherwise double.

本 skill 写出的每个 `.md`（skill 文档、阶段文档、workspace 中的总结、报告、日志）开头都有一行横幅：告诉 agent 只读英文、告诉人中文内容相同。然后每一节先写完整英文块（一段或多段、表格、列表），紧接着写完整中文块。不逐句交错，不把中文以括号塞进英文段落。标题用 `English / 中文`。表格列过多时允许一格内用 ` / ` 并列两种语言。

Exception: workspace *content* meant for the user (summary bodies, `definition_zh`, dialog questions and answers) is Chinese only; the English counterpart lives in the dedicated `*_en` fields, because the downstream agent reads those.

例外：给用户看的 workspace *内容*（总结正文、`definition_zh`、对话问答）只写中文；英文放在专门的 `*_en` 字段，因为下游 agent 读那些字段。

## Python files / Python 文件

Module docstring: first line the banner (`Agents: read the English part of every docstring only. 中文段落仅供人类阅读。`), then an English block describing purpose, inputs/outputs and CLI usage, then the Chinese block. Every function and method has a docstring with an English paragraph followed by a Chinese paragraph. Inline comments follow the same EN-then-ZH order on one line (`# EN / 中文`) when short.

模块 docstring：第一行横幅，然后英文块（用途、输入输出、命令行用法），再中文块。每个函数/方法的 docstring 先英文段再中文段。行内注释短时同一行先英后中（`# EN / 中文`）。

## JSON files / JSON 文件

Top-level `_comment_en` and `_comment_zh` keys describe the file. Enumerations and category values carry `name_en` / `name_zh` and `description_en` / `description_zh`.

顶层 `_comment_en`、`_comment_zh` 描述文件；枚举与分类值带 `name_en/name_zh`、`description_en/description_zh`。
