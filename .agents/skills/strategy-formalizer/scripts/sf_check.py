#!/usr/bin/env python3
"""
Agents: read the English part of every docstring only. 中文段落仅供人类阅读。

sf_check.py — S8 cross-check of summary markdown vs term file vs formal
interface, and the `freeze` step that copies the deliverables into final/.

`run` performs the mechanical checks and writes the "Script findings" part
of S8_check_report.md (the agent appends its own semantic review below it):
  1. the summary contains every required section marker
     `<!-- section: key -->` (see sf_common.SUMMARY_SECTIONS);
  2. every `**bold**` phrase in the summary is the name (or alias) of a live
     role=callback term — nothing else may be bold;
  3. every live callback term appears in bold at least once;
  4. every live term's Chinese name appears somewhere in the summary
     (warning otherwise: a term nobody mentions is probably stale);
  5. no dropped term is mentioned in bold;
  6. the term file passes sf_terms.validate with --require-classified and
     --require-defined; the formal file passes sf_formal.validate;
  7. the S3 and S6 dialog logs have no open questions.
Exit code is 1 when any error was found. `freeze` refuses to run while
errors remain and otherwise copies summary/terms/formal/stub into final/.

    sf_check.py run    [--summary S5_summary_marked.md] [--terms S6_terms_defined.json] [--formal S7_formal.json] [--lenient]
    sf_check.py freeze [same options] [--stub S7_callbacks_stub.py]

sf_check.py 负责 S8 的交叉核对（总结 markdown、术语文件、形式化接口三者对照）以及把交付物
复制到 final/ 的 `freeze` 步骤。`run` 执行机械检查并写出 S8_check_report.md 的"脚本发现"
部分（agent 在其后追加语义审查）：1) 总结含有全部必需章节标记；2) 总结中每个 `**加粗**`
短语都是存活的 role=callback 术语的名称或别名，其他内容不得加粗；3) 每个存活回调术语至少
加粗出现一次；4) 每个存活术语的中文名在总结中出现过（否则告警，没人提到的术语多半过期）；
5) 已丢弃术语不得加粗出现；6) 术语文件通过 --require-classified --require-defined 校验，
形式化文件通过校验；7) S3、S6 对话没有未回答的问题。发现错误时退出码为 1。`freeze` 在有
错误时拒绝执行，否则把总结/术语/形式化/桩代码复制到 final/。
"""
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

from sf_common import (DIALOG_STAGES, SUMMARY_SECTIONS, load_json, now_iso, read_text, relpath, resolve_workspace,
                       say, write_text)
from sf_formal import validate as validate_formal
from sf_terms import load_terms, validate as validate_terms

BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
SECTION_RE = re.compile(r"<!--\s*section:\s*([a-z_]+)\s*-->")


def check(ws: Path, summary: Path, terms_path: Path, formal_path: Path | None,
          cat_path: Path | None, lenient: bool = False) -> tuple[list[str], list[str]]:
    """
    Run all checks described in the module docstring and return
    (errors, warnings) as human-readable strings. With lenient=True (used in
    S5 and mid-S6) only the section and bold checks and the classified-term
    validation run; definitions, the formal file and open dialogs are not
    required yet.

    执行模块说明中的全部检查，以可读字符串返回 (错误, 警告)。lenient=True（S5 与 S6 中途
    使用）时只做章节与加粗检查及已分类术语校验，不要求定义、形式化文件和对话已关闭。
    """
    errors: list[str] = []
    warnings: list[str] = []
    text = read_text(summary)
    terms = load_terms(terms_path)
    live = [t for t in terms["terms"] if t["status"] != "dropped"]
    dropped = [t for t in terms["terms"] if t["status"] == "dropped"]

    # 1. sections
    present = set(SECTION_RE.findall(text))
    for sec in SUMMARY_SECTIONS:
        if sec not in present:
            errors.append(f"summary missing section marker <!-- section: {sec} -->")

    # 2/3/5. bold phrases
    bold = [b.strip() for b in BOLD_RE.findall(text)]
    cb_names: dict[str, dict] = {}
    for t in live:
        if t["role"] == "callback":
            cb_names[t["name_zh"]] = t
            for a in t["aliases"]:
                cb_names[a] = t
    dropped_names = {t["name_zh"] for t in dropped} | {a for t in dropped for a in t["aliases"]}
    for b in bold:
        if b in dropped_names:
            errors.append(f"bold phrase {b!r} is a DROPPED term")
        elif b not in cb_names:
            errors.append(f"bold phrase {b!r} is not a live callback term (only callbacks may be bold)")
    for t in live:
        if t["role"] == "callback":
            names = {t["name_zh"], *t["aliases"]}
            if not names & set(bold):
                errors.append(f"callback {t['id']} {t['name_zh']} never appears in bold in the summary")

    # 4. mentions
    for t in live:
        names = [t["name_zh"], *t["aliases"]]
        if not any(n and n in text for n in names):
            warnings.append(f"{t['id']} {t['name_zh']} ({t['role']}) is not mentioned anywhere in the summary")

    # 6. file validation
    e, w = validate_terms(terms, cat_path, require_classified=True, require_defined=not lenient)
    errors += [f"terms: {x}" for x in e]
    warnings += [f"terms: {x}" for x in w]
    if lenient:
        return errors, warnings
    if formal_path is not None and formal_path.exists():
        e, w = validate_formal(load_json(formal_path), terms)
        errors += [f"formal: {x}" for x in e]
        warnings += [f"formal: {x}" for x in w]
    elif formal_path is not None:
        errors.append(f"formal file {relpath(formal_path)} missing")

    # 7. dialogs
    for ds in DIALOG_STAGES:
        dp = ws / f"{ds}_dialog.json"
        if dp.exists():
            open_ids = [x["id"] for x in load_json(dp).get("entries", []) if x.get("status") == "open"]
            if open_ids:
                errors.append(f"{ds} dialog has open questions: {open_ids}")
    return errors, warnings


def render_report(errors: list[str], warnings: list[str], inputs: dict[str, str]) -> str:
    """
    Render the script part of S8_check_report.md; the agent appends a
    "Semantic review" section afterwards.

    渲染 S8_check_report.md 的脚本部分；之后由 agent 追加"语义审查"章节。
    """
    lines = ["# S8 check report", "",
             "> **Agents: follow the English part only. The Chinese part at the end is a translation for human readers.**",
             "> **说明：agent 只需参考英文；末尾中文仅供人类阅读。**", "",
             f"Generated: {now_iso()}", "",
             "## Inputs"]
    lines += [f"- {k}: `{v}`" for k, v in inputs.items()]
    lines += ["", "## Script findings", "",
              f"Errors: {len(errors)}, warnings: {len(warnings)}", ""]
    lines += [f"- ERROR: {e}" for e in errors] or ["- no errors"]
    lines += [""]
    lines += [f"- warning: {w}" for w in warnings] or ["- no warnings"]
    lines += ["", "## Semantic review (agent)", "",
              "_The agent appends here: for each execution step and exit rule in the summary, the terms it relies on, "
              "and any omission or contradiction found._", "",
              "---", "", "# 中文版（仅供人类阅读；agent 请参考上方英文）", "",
              f"脚本发现：{len(errors)} 个错误，{len(warnings)} 个警告（明细见上方英文部分）。"
              "语义审查由 agent 在上方 Semantic review 节填写：逐条核对执行步骤与出场风控所依赖的术语，记录遗漏与矛盾。", ""]
    return "\n".join(lines)


def resolve_inputs(args: argparse.Namespace) -> tuple[Path, Path, Path, Path | None, Path | None]:
    """
    Resolve workspace and input files from CLI args (defaults are the S5/S6/S7
    filenames).

    根据命令行参数解析 workspace 与输入文件（默认为 S5/S6/S7 的文件名）。
    """
    ws = resolve_workspace(args.workspace)
    summary = ws / args.summary
    terms = ws / args.terms
    formal = ws / args.formal if args.formal else None
    cats = ws / args.categories if args.categories and (ws / args.categories).exists() else None
    return ws, summary, terms, formal, cats


def cmd_run(args: argparse.Namespace) -> None:
    """
    Run the checks, write S8_check_report.md, print a summary, exit 1 on
    errors.

    执行检查、写出 S8_check_report.md、打印摘要，有错误则以 1 退出。
    """
    ws, summary, terms, formal, cats = resolve_inputs(args)
    errors, warnings = check(ws, summary, terms, formal, cats, lenient=args.lenient)
    report = ws / args.out
    write_text(report, render_report(errors, warnings, {
        "summary": relpath(summary), "terms": relpath(terms), "formal": relpath(formal) if formal else "-"}))
    for w in warnings:
        say(f"warning: {w}")
    for e in errors:
        say(f"ERROR: {e}")
    say(f"report written to {relpath(report)}: {len(errors)} errors, {len(warnings)} warnings", "报告已写出")
    if errors:
        raise SystemExit(1)


def cmd_freeze(args: argparse.Namespace) -> None:
    """
    Re-run the checks and, if error-free, copy the summary, term file, formal
    file and stub into final/ under canonical names.

    重新执行检查，无错误时把总结、术语文件、形式化文件和桩代码以固定名称复制到 final/。
    """
    ws, summary, terms, formal, cats = resolve_inputs(args)
    errors, _ = check(ws, summary, terms, formal, cats)
    if errors:
        for e in errors:
            say(f"ERROR: {e}")
        say("refusing to freeze while errors remain", "存在错误，拒绝冻结")
        raise SystemExit(1)
    final = ws / "final"
    final.mkdir(exist_ok=True)
    pairs = [(summary, final / "strategy.md"), (terms, final / "terms.json")]
    if formal:
        pairs.append((formal, final / "formal.json"))
    stub = ws / args.stub
    if stub.exists():
        pairs.append((stub, final / "callbacks_stub.py"))
    for src, dst in pairs:
        shutil.copyfile(src, dst)
        say(f"{relpath(src)} -> {relpath(dst)}")
    say("final/ frozen", "final/ 已冻结")


def build_parser() -> argparse.ArgumentParser:
    """
    Build the CLI.

    构建命令行。
    """
    p = argparse.ArgumentParser(description="S8 cross-check / 交叉核对")
    p.add_argument("--workspace", "-w")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn in (("run", cmd_run), ("freeze", cmd_freeze)):
        s = sub.add_parser(name)
        s.add_argument("--summary", default="S5_summary_marked.md")
        s.add_argument("--terms", default="S6_terms_defined.json")
        s.add_argument("--formal", default="S7_formal.json")
        s.add_argument("--categories", default="S5_categories.json")
        s.add_argument("--out", default="S8_check_report.md")
        s.add_argument("--stub", default="S7_callbacks_stub.py")
        s.add_argument("--lenient", action="store_true",
                       help="S5/S6 mode: only sections, bold and classification are checked")
        s.set_defaults(func=fn)
    return p


def main(argv: list[str] | None = None) -> None:
    """
    CLI entry point.

    命令行入口。
    """
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
