# Bilingual style

> **Agents: follow the English part only (above the "中文版" divider). The Chinese part is a translation for human readers and adds no instructions.**
>
> **说明：agent 执行时只需参考上半部分的英文；下半部分的中文仅供人类阅读，内容相同，不含额外指令。**

## Markdown files

Every `.md` written by this skill (skill docs, stage docs, prompts, references, workspace reports and logs) has three parts in this order: (1) the title and a banner telling agents to follow the English part only and telling humans that the Chinese part is a translation; (2) the **complete English text**; (3) a horizontal rule, a heading `# 中文版（仅供人类阅读；agent 请参考上方英文）`, and the **complete Chinese text**, section for section. The English part contains no Chinese paragraphs and the Chinese part no English paragraphs. Languages are never alternated sentence by sentence or section by section. Chinese words may appear inside an English sentence only when they are data (a term name, a quote from the strategy, a file name). Code blocks and tables that are identical in both languages may be given once in the English part and referenced from the Chinese part ("图见英文部分").

Exception: workspace *content* meant for the user (summary bodies, `definition_zh`, dialog questions and answers) is Chinese only; the English counterpart lives in the dedicated `*_en` fields, because the downstream agent reads those.

## Python files

The module docstring starts with the banner line `Agents: read the English part of every docstring only. 中文段落仅供人类阅读。`, followed by the complete English description (purpose, inputs/outputs, CLI usage) and then the complete Chinese description. Every function and method docstring is one English block followed by one Chinese block. Short inline comments may pair both on one line (`# EN / 中文`).

## JSON files

Top-level `_comment_en` and `_comment_zh` keys describe the file. Enumerations and category values carry `name_en` / `name_zh` and `description_en` / `description_zh`.

## Checking

Before committing, run the docstring-coverage check from the README (every `def` has a docstring containing Chinese) and confirm every `.md` under the skill has exactly one `# 中文版` heading.

---

# 中文版（仅供人类阅读；agent 请参考上方英文）

## Markdown 文件

本 skill 写出的每个 `.md`（skill 文档、阶段文档、提示词、参考资料、workspace 中的报告与日志）依次由三部分组成：(1) 标题和一段横幅，告诉 agent 只参考英文、告诉人中文是翻译；(2) **完整的英文正文**；(3) 一条分隔线、标题 `# 中文版（仅供人类阅读；agent 请参考上方英文）`、以及逐节对应的**完整中文正文**。英文部分不含中文段落，中文部分不含英文段落。绝不逐句或逐节交错两种语言。英文句子中只有作为数据的中文（术语名、策略原文引用、文件名）才允许出现。两种语言完全相同的代码块和表格可以只在英文部分给出一次，中文部分引用（"图见英文部分"）。

例外：给用户看的 workspace *内容*（总结正文、`definition_zh`、对话问答）只写中文；对应英文放在专门的 `*_en` 字段，因为下游 agent 读那些字段。

## Python 文件

模块 docstring 第一行是横幅 `Agents: read the English part of every docstring only. 中文段落仅供人类阅读。`，随后是完整的英文说明（用途、输入输出、命令行用法），再是完整的中文说明。每个函数和方法的 docstring 都是一个英文块接一个中文块。简短的行内注释可在同一行并列（`# EN / 中文`）。

## JSON 文件

顶层 `_comment_en`、`_comment_zh` 描述文件；枚举与分类值带 `name_en/name_zh`、`description_en/description_zh`。

## 检查

提交前运行 README 中的 docstring 覆盖检查（每个 `def` 都有含中文的 docstring），并确认 skill 下每个 `.md` 恰好有一个 `# 中文版` 标题。
