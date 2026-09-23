# S1 — Correct the raw text

> **Agents: follow the English part only (above the "中文版" divider). The Chinese part is a translation for human readers and adds no instructions.**
>
> **说明：agent 执行时只需参考上半部分的英文；下半部分的中文仅供人类阅读，内容相同，不含额外指令。**

## Goal

Produce a faithful, typo-free version of the strategy text without changing its meaning, an audit table of every edit, and a reorganised Markdown rendering of the full corrected text that later stages read. The input is usually a voice transcript (Chinese, produced by speech recognition) or a downloaded post, so it contains homophone errors (布林黛 → 布林带, 盘杆 → 盘感, ADDX → ADX, 海归教义法则 → 海龟交易法则), slips of the tongue (顺势、清仓、止损 where the well-known maxim is 顺势、轻仓、止损), repeated phrases and broken sentences. You fix those. You do **not** summarize, reorder, drop "unimportant" passages, or add explanations: later stages need the full text, and the user must be able to trust that S1 changed only what the table says.

## Inputs

- The input folder recorded in `state.json` → `input_dir` (e.g. `strategy_zoo/大小周期共振/`). Text files are `.md`/`.txt`; media files are ignored.
- Root-level text files are `primary` by default (the transcript, the video analysis); files under `references/` are `secondary` (external material the user collected; context only, never merged).

## Outputs

| File | Content |
|---|---|
| `S1_sources.json` | Manifest of every text file: `path`, `role` (`primary` / `secondary` / `ignored`), `kind` (`transcript` / `analysis` / `reference` / `other`), short bilingual note. Schema: `schemas/sources.schema.json`. The user may change roles at the stop. |
| `S1_strategy_raw.md` | Banner, then one `## Source: <filename>` section per primary file containing the corrected text. Keep timestamps like `[387s]` if present: later stages cite them in `source_quote`. |
| `S1_corrections.md` | Table `| # | source | original | corrected | reason | confidence |`. Confidence `high` for obvious homophones, `medium` for context-based fixes, `low` for guesses (list these explicitly in the stop message). |
| `S1_strategy_clean.md` | The complete corrected text organised for reading: a short banner, then topic sections (`## <topic>（[start]–[end]）` with the timestamp range of the raw lines it covers), paragraphs formed by merging consecutive lines, and numbered/bulleted lists where the speaker enumerates (steps, details, lessons). Every sentence of the raw text is kept verbatim (only sentence punctuation may be normalised); nothing is summarised, reordered across sections, or added. Editor notes like `(与上一句重复…)` are dropped; `[原文不清: …]` annotations are kept. This file is the input of S2. |

## Procedure

1. `SF/sf_state.py start S1`.
2. List the input folder. Build `S1_sources.json`. If a root-level file is itself an interpretation with outside ideas (e.g. `视频分析_*.md` that proposes ATR stops the transcript never mentions), keep it `primary` but set `kind: analysis`; the S2 subagents are told to treat `analysis` files as weaker evidence than `transcript` files.
3. Read every primary file completely. Correct in place: homophones, obviously wrong technical names, slips that contradict the surrounding sentence, ASR artifacts (duplicated clauses, missing punctuation). When a passage is garbled beyond confident repair, keep it and append `[原文不清]`.
4. Write `S1_strategy_raw.md` and `S1_corrections.md`. Every edit in the text must have a row; every row must correspond to an edit.
5. Sanity-check: paragraph count and timestamp count of each source equal the original's.
6. Write `S1_strategy_clean.md`: read the corrected text once as an editor, choose 8–15 topic sections in the text's own order, give each a heading with its timestamp range, merge lines into paragraphs, and turn enumerations into lists. Do not paraphrase. Generating it from the raw file with a script (section boundaries by timestamp) is the safest way to keep every sentence.
7. `SF/sf_check.py s1-coverage` must report 0 missing segments.
8. `SF/sf_state.py complete S1`, print the stop message, end the turn.

## Done criteria

- All four outputs exist; `S1_sources.json` has `path`, `role` and `kind` for every text file.
- `sf_check.py s1-coverage` passes: the clean text contains every raw sentence.
- No row in `S1_corrections.md` changes meaning beyond fixing an error; low-confidence rows are listed in the stop message.

## Stop message

Use the template in SKILL.md §5. Under "Review" ask the user to (a) confirm or flip source roles in `S1_sources.json`, (b) scan the `low` confidence rows, (c) fix anything the ASR got wrong that you could not detect, (d) check the section headings of `S1_strategy_clean.md` read naturally, since S2 works from that file.

---

# 中文版（仅供人类阅读；agent 请参考上方英文）

## 目标

产出一份意思不变、无错别字的策略文本、每处修改的对照表，以及一份供后续阶段阅读的、重新组织过的完整矫正文本（Markdown）。输入通常是语音转写（中文、ASR 生成）或下载的帖子，含同音错字（布林黛→布林带、盘杆→盘感、ADDX→ADX、海归教义法则→海龟交易法则）、口误（"顺势、清仓、止损"应为"顺势、轻仓、止损"）、重复与断句。你只修这些，**不**总结、不重排、不删"不重要"的段落、不加解释：后续阶段需要全文，用户必须能确信 S1 只改了表里列出的内容。

## 输入

- `state.json` 中记录的输入目录 `input_dir`（如 `strategy_zoo/大小周期共振/`）。文本文件为 `.md`/`.txt`，媒体文件忽略。
- 根目录下的文本文件默认为 `primary`（转写稿、视频分析）；`references/` 下的文件为 `secondary`（用户收集的外部资料，仅作背景，不合并）。

## 产出

| 文件 | 内容 |
|---|---|
| `S1_sources.json` | 每个文本文件的清单：`path`、`role`（`primary` / `secondary` / `ignored`）、`kind`（`transcript` / `analysis` / `reference` / `other`）、简短双语备注。schema 见 `schemas/sources.schema.json`。用户可在停顿时改变角色。 |
| `S1_strategy_raw.md` | 横幅之后，每个 primary 文件一个 `## Source: <文件名>` 小节，内含矫正后的文本。若有 `[387s]` 之类时间戳则保留：后续阶段的 `source_quote` 会引用。 |
| `S1_corrections.md` | 表格 `| # | 来源 | 原文 | 修改后 | 原因 | 置信度 |`。明显同音错字为 `high`，依上下文修正为 `medium`，猜测为 `low`（停止消息中要明确列出）。 |
| `S1_strategy_clean.md` | 整理成可读形式的完整矫正文本：简短横幅之后按主题分节（`## <主题>（[起]–[止]）`，标题带该节覆盖的原文时间戳范围），连续行合并成段落，讲者列举之处（步骤、细节、要点）改为编号或项目列表。原文每一句都原样保留（只允许规范句末标点）；不摘要、不跨节重排、不添加。`(与上一句重复…)` 之类编者括注去掉；`[原文不清: …]` 注记保留。此文件是 S2 的输入。 |

## 步骤

1. `SF/sf_state.py start S1`。
2. 列出输入目录，生成 `S1_sources.json`。根目录下若有本身就是解读、含外部观点的文件（如提出转写里没有的 ATR 止损的 `视频分析_*.md`），仍设 `primary` 但 `kind: analysis`；S2 子代理会把 `analysis` 视为比 `transcript` 更弱的证据。
3. 通读每个 primary 文件，原地矫正同音错字、明显错误的技术名词、与上下文矛盾的口误、ASR 伪迹（重复子句、缺标点）。无法有把握修复的段落保留并追加 `[原文不清]`。
4. 写出 `S1_strategy_raw.md` 与 `S1_corrections.md`。正文每处修改都要有一行，每一行都要对应一处修改。
5. 自检：每个来源的段落数、时间戳数与原文一致。
6. 写 `S1_strategy_clean.md`：以编辑的视角通读矫正后的文本，按原文顺序划分 8~15 个主题小节，每节标题附时间戳范围，行合并为段落，列举改为列表。不改写。用脚本按时间戳边界从原文生成是保证不丢句子的最稳妥做法。
7. `SF/sf_check.py s1-coverage` 必须报告 0 个缺失片段。
8. `SF/sf_state.py complete S1`，打印停止消息，结束本轮。

## 完成标准

- 四个产出齐全；`S1_sources.json` 中每个文本文件都有 `path`、`role`、`kind`。
- `sf_check.py s1-coverage` 通过：clean 文本包含原文每一句。
- `S1_corrections.md` 中没有任何一行在纠错之外改变了含义；低置信度行在停止消息中列出。

## 停止消息

使用 SKILL.md 第 5 节的模板。"请审阅"部分请用户 (a) 确认或调整 `S1_sources.json` 中的来源角色，(b) 检查 `low` 置信度的行，(c) 修正你未能发现的 ASR 错误，(d) 检查 `S1_strategy_clean.md` 的小节标题是否自然，因为 S2 以该文件为输入。
