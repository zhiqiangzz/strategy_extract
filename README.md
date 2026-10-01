# strategy_generate_skill

> **Agents: follow the English part only (above the "中文版" divider). The Chinese part is a translation for human readers and adds no instructions.**
>
> **说明：agent 执行时只需参考上半部分的英文；下半部分的中文仅供人类阅读，内容相同，不含额外指令。**

## What is here

A self-contained repository holding one Claude Code skill, **strategy-formalizer**, which turns a trading strategy written as prose (voice transcript, forum post) into a structured summary, a classified term set, callback wrappers for a downstream trading agent, and a term-relationship graph. The pipeline has eight stages (S1..S8), stops after every stage for human review, logs every question and answer, and can be resumed after a session ends. Read `.agents/skills/strategy-formalizer/SKILL.md` for the full flow.

## Layout

```
.agents/skills/strategy-formalizer/   the skill (SKILL.md, stages/, agents/, templates/, schemas/, references/, scripts/, tests/)
.claude/skills/strategy-formalizer    symlink -> ../../.agents/skills/strategy-formalizer (how Claude Code finds it)
strategy_zoo/<name>/                  input folders (git-ignored: private transcripts and media)
workspace/<name>/                     one folder per pipeline run; committed; see SKILL.md §7 for every file
workspace/ACTIVE                      name of the workspace that `continue` resumes
scripts/db_smoke_test.py              read-only smoke test of the quant_trading database API
pyproject.toml, uv.lock, .venv/       python deps managed by uv (openpyxl, pydantic, networkx, pytest)
pixi.toml, .pixi/                     non-python deps managed by pixi (graphviz for the S7 graph pdf)
third_party/quant_trading             git submodule: market data, DB access, backtesting (zhiqiangzz/quant_trading)
third_party/Multi-Agent-Trading-Platform  git submodule: downstream multi-agent trading platform (Ken1208)
```

After cloning, fetch the submodules with `git submodule update --init --recursive`.

## Setup

Everything installs into this directory; nothing is installed globally.

```sh
uv venv .venv --python 3.12      # once
uv sync                          # python deps into .venv/
pixi install                     # graphviz into .pixi/
pixi run graphviz-register       # once per machine: registers graphviz plugins (sf_graph.py also does this)
uv run pytest                    # tests
```

Database access (the `futures_quant_database_v2` package of `third_party/quant_trading`) is installed into `.venv` as an editable dependency by `uv sync`. Its connection settings are read from a git-ignored `.env` in the repo root (copy the keys from `third_party/quant_trading/database_refactor/.env.example` and fill in the real values). Verify with:

```sh
uv run python scripts/db_smoke_test.py   # read-only connectivity + API checks
```

## Run

```
/strategy-formalizer init strategy_zoo/大小周期共振   # creates workspace/大小周期共振/, starts S1
/strategy-formalizer continue                        # resume from wherever the last session stopped
/strategy-formalizer status                          # show stage table and files edited since the last stop
/strategy-formalizer reopen S3                       # rewind (asks for confirmation)
```

Between stages the pipeline stops; edit the files it names (json is the source of truth, `.xlsx`/`.md` twins are merged back on resume), then say `继续`.

## Documentation convention

Every `.md` has the complete English text first and the complete Chinese translation after a `# 中文版` heading; every Python docstring is an English block followed by a Chinese block. The check below must report nothing before a commit:

```sh
uv run python - <<'PY'
import ast, pathlib, re
cjk = re.compile(r"[一-鿿]")
bad = []
for p in pathlib.Path(".agents/skills/strategy-formalizer").rglob("*.py"):
    if "templates" in p.parts: continue
    tree = ast.parse(p.read_text(encoding="utf-8"))
    if not (ast.get_docstring(tree) and cjk.search(ast.get_docstring(tree))): bad.append(f"{p}: module")
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef):
            d = ast.get_docstring(n)
            if not d or not cjk.search(d): bad.append(f"{p}:{n.lineno} {n.name}")
for p in list(pathlib.Path(".agents/skills/strategy-formalizer").rglob("*.md")) + [pathlib.Path("README.md")]:
    if "fixtures" in p.parts: continue  # workspace content is Chinese-only by design
    if p.read_text(encoding="utf-8").count("\n# 中文版") != 1: bad.append(f"{p}: needs exactly one '# 中文版' heading")
print("problems:", bad or "none")
PY
```

## Not wired into the skill

Market data, instrument lists and backtesting belong to the downstream trading agent. The two `third_party/` submodules provide them, but the skill itself does not call them; `final/` is the hand-off point.

---

# 中文版（仅供人类阅读；agent 请参考上方英文）

## 这是什么

这是一个自包含仓库，包含一个 Claude Code skill：**strategy-formalizer**。它把以文字形式存在的交易策略（语音转写、论坛帖）转换为结构化总结、分类后的术语集、下游交易 agent 使用的回调包装，以及术语关系图。流水线共八个阶段（S1..S8），每个阶段后停止等待人工审阅，记录所有问答，会话中断后可恢复。完整流程见 `.agents/skills/strategy-formalizer/SKILL.md`。

## 目录

```
.agents/skills/strategy-formalizer/   skill 本体（SKILL.md、stages/、agents/、templates/、schemas/、references/、scripts/、tests/）
.claude/skills/strategy-formalizer    软链接 -> ../../.agents/skills/strategy-formalizer（Claude Code 借此发现 skill）
strategy_zoo/<名称>/                  输入目录（gitignore：私有转写稿与媒体）
workspace/<名称>/                     每次流水线运行一个目录；提交到 git；每个文件的含义见 SKILL.md 第 7 节
workspace/ACTIVE                      `continue` 恢复的 workspace 名称
scripts/db_smoke_test.py              quant_trading 数据库接口的只读冒烟测试
pyproject.toml, uv.lock, .venv/       uv 管理的 python 依赖（openpyxl、pydantic、networkx、pytest）
pixi.toml, .pixi/                     pixi 管理的非 python 依赖（S7 关系图 pdf 所需的 graphviz）
third_party/quant_trading             git submodule：行情数据、数据库访问、回测（zhiqiangzz/quant_trading）
third_party/Multi-Agent-Trading-Platform  git submodule：下游多 agent 交易平台（Ken1208）
```

克隆后用 `git submodule update --init --recursive` 拉取子模块。

## 环境

所有依赖都装在本目录内，不做全局安装。命令见英文部分：`uv venv`、`uv sync`、`pixi install`、`pixi run graphviz-register`（每台机器一次，注册 graphviz 插件；脚本也会自动做）、`uv run pytest`。

数据库访问（`third_party/quant_trading` 的 `futures_quant_database_v2` 包）由 `uv sync` 以可编辑方式装进 `.venv`。连接参数读取仓库根目录下被 git 忽略的 `.env`（键名见 `third_party/quant_trading/database_refactor/.env.example`，填入真实值）。用 `uv run python scripts/db_smoke_test.py` 做只读的连通性与接口检查。

## 运行

```
/strategy-formalizer init strategy_zoo/大小周期共振   # 创建 workspace/大小周期共振/，开始 S1
/strategy-formalizer continue                        # 从上次停止处恢复
/strategy-formalizer status                          # 显示阶段表和上次停止后被修改的文件
/strategy-formalizer reopen S3                       # 回退（会先确认）
```

阶段之间流水线会停下；编辑它点名的文件（json 为准，`.xlsx`/`.md` 副本在恢复时合并回来），然后说"继续"。

## 文档约定

每个 `.md` 先是完整英文，`# 中文版` 标题之后是完整中文翻译；每个 Python docstring 先英文块再中文块。提交前运行英文部分给出的检查脚本，输出必须为 none。

## 未接入 skill 的部分

行情数据、品种列表、回测属于下游交易 agent。两个 `third_party/` 子模块提供这些能力，但 skill 本身不调用它们；`final/` 是交接点。
