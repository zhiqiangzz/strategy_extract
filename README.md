# strategy_generate_skill

> Agents: read the English paragraphs only. 中文段落仅供人类阅读，内容相同。

## What is here / 这是什么

A self-contained repository holding one Claude Code skill, **strategy-formalizer**, which turns a trading strategy written as prose (voice transcript, forum post) into a structured summary, a classified term set, callback wrappers for a downstream trading agent, and a term-relationship graph. The pipeline has eight stages (S1..S8), stops after every stage for human review, logs every question and answer, and can be resumed after a session ends. Read `.agents/skills/strategy-formalizer/SKILL.md` for the full flow.

这是一个自包含仓库，包含一个 Claude Code skill：**strategy-formalizer**。它把以文字形式存在的交易策略（语音转写、论坛帖）转换为结构化总结、分类后的术语集、下游交易 agent 使用的回调包装，以及术语关系图。流水线共八个阶段，每个阶段后停止等待人工审阅，记录所有问答，会话中断后可恢复。完整流程见 `.agents/skills/strategy-formalizer/SKILL.md`。

## Layout / 目录

```
.agents/skills/strategy-formalizer/   the skill (SKILL.md, stages/, agents/, templates/, schemas/, references/, scripts/, tests/)
.claude/skills/strategy-formalizer    symlink -> ../../.agents/skills/strategy-formalizer (how Claude Code finds it)
strategy_zoo/<name>/                  input folders (git-ignored: private transcripts and media)
workspace/<name>/                     one folder per pipeline run; committed; see SKILL.md §7 for every file
workspace/ACTIVE                      name of the workspace that `continue` resumes
pyproject.toml, uv.lock, .venv/       python deps managed by uv (openpyxl, pydantic, networkx, pytest)
pixi.toml, .pixi/                     non-python deps managed by pixi (graphviz for the S7 graph png)
```

## Setup / 环境

Everything installs into this directory; nothing is installed globally.

所有依赖都装在本目录内，不做全局安装。

```sh
uv venv .venv --python 3.12      # once
uv sync                          # python deps into .venv/
pixi install                     # graphviz into .pixi/
pixi run graphviz-register       # once per machine: registers graphviz plugins (sf_graph.py also does this)
uv run pytest                    # 13 tests
```

## Run / 运行

```
/strategy-formalizer init strategy_zoo/大小周期共振   # creates workspace/大小周期共振/, starts S1
/strategy-formalizer continue                        # resume from wherever the last session stopped
/strategy-formalizer status                          # show stage table and files edited since the last stop
/strategy-formalizer reopen S3                       # rewind (asks for confirmation)
```

Between stages the pipeline stops; edit the files it names (json is the source of truth, `.xlsx`/`.md` twins are merged back on resume), then say `继续`.

阶段之间流水线会停下；编辑它点名的文件（json 为准，`.xlsx`/`.md` 副本在恢复时合并回来），然后说"继续"。

## Not in this repository / 不包含

Market data, instrument lists and backtesting belong to the downstream trading agent (the separate `quant_trading` project) and are intentionally not wired in here.
