#!/usr/bin/env python3
"""
Agents: read the English part of every docstring only. 中文段落仅供人类阅读。

sf_state.py — the S1..S8 state machine and the resume entry point.

One workspace (workspace/<strategy_name>/) holds one run of the pipeline and
its state.json. Every stage moves through pending -> in_progress ->
awaiting_review -> done. The agent calls `start` when it begins a stage,
`complete` when it has written the stage outputs (this records a SHA-256
checkpoint of each output and STOPS the pipeline for human review), and
`accept` when the user says "continue" (this re-hashes the outputs, marks the
stage done and advances current_stage). `status` prints a "context pack":
current stage, the stage doc to read, which output files the user edited since
the checkpoint (they must be re-read), open dialog questions, and whether an
.xlsx is newer than its .json twin. `reopen` rewinds to an earlier stage and
resets everything downstream. Because all of this lives on disk, a new Claude
session can resume with a single `status` call.

    uv run python <scripts>/sf_state.py init --input strategy_zoo/大小周期共振
    uv run python <scripts>/sf_state.py status
    uv run python <scripts>/sf_state.py start S1
    uv run python <scripts>/sf_state.py complete S1
    uv run python <scripts>/sf_state.py accept S1
    uv run python <scripts>/sf_state.py reopen S3 --yes
    uv run python <scripts>/sf_state.py set-scheme role_x_phase

sf_state.py 是 S1..S8 的状态机，也是恢复上下文的入口。每个 workspace
（workspace/<策略名>/）对应一次流水线运行及其 state.json。每个阶段依次经历
pending -> in_progress -> awaiting_review -> done。agent 开始某阶段时调用 `start`，
写完该阶段产出后调用 `complete`（记录每个产出文件的 SHA-256 检查点，并停下来等待人工
审阅），用户说"继续"后调用 `accept`（重新计算哈希、标记 done、推进 current_stage）。
`status` 打印"上下文包"：当前阶段、应阅读的阶段说明文档、用户在检查点之后修改过的文件
（必须重新阅读）、未回答的对话问题，以及 .xlsx 是否比同名 .json 更新。`reopen` 回退到
更早的阶段并重置其下游。由于这些信息全部落盘，新的 Claude 会话只需一次 `status` 即可恢复。
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from sf_common import (ACTIVE_FILE, DIALOG_STAGES, REPO_ROOT, STAGE_DOCS, STAGE_OUTPUTS, STAGE_TITLES,
                       STAGES, STAGES_DIR, TEMPLATES_DIR, TERM_FILE_BY_STAGE, WORKSPACE_ROOT, content_hash,
                       fail, load_json, now_iso, relpath, resolve_workspace, save_json, say, stage_index)

STATE_FILE = "state.json"


# --------------------------------------------------------------------------- #
# state.json helpers
# --------------------------------------------------------------------------- #


def state_path(ws: Path) -> Path:
    """
    Return the path of state.json inside a workspace.

    返回 workspace 内 state.json 的路径。
    """
    return ws / STATE_FILE


def load_state(ws: Path) -> dict:
    """
    Load state.json from the workspace, failing with a hint to run `init` if
    it does not exist.

    从 workspace 读取 state.json；不存在时提示先运行 `init`。
    """
    p = state_path(ws)
    if not p.exists():
        fail(f"{relpath(p)} not found; run `sf_state.py init --input <dir>`",
             "state.json 不存在，请先运行 init")
    return load_json(p)


def save_state(ws: Path, state: dict) -> None:
    """
    Persist state.json, refreshing its updated_at timestamp.

    写回 state.json 并刷新 updated_at 时间戳。
    """
    state["updated_at"] = now_iso()
    save_json(state_path(ws), state)


def fresh_state(name: str, input_dir: Path, scheme: str) -> dict:
    """
    Build a new state dict from templates/state.template.json, filling in the
    strategy name, the input folder and the classification scheme id, with
    all eight stages pending and S1 as the current stage.

    基于 templates/state.template.json 构造新的状态字典：填入策略名、输入目录、分类方案
    id，八个阶段全部 pending，当前阶段为 S1。
    """
    tpl = load_json(TEMPLATES_DIR / "state.template.json")
    tpl["strategy_name"] = name
    tpl["input_dir"] = relpath(input_dir)
    tpl["scheme_id"] = scheme
    tpl["created_at"] = now_iso()
    tpl["current_stage"] = "S1"
    tpl["stages"] = {
        s: {"status": "pending", "started_at": None, "completed_at": None,
            "accepted_at": None, "checkpoint_hashes": {}}
        for s in STAGES
    }
    return tpl


def checkpoint(ws: Path, stage: str) -> dict[str, str | None]:
    """
    Hash every declared output of a stage (see sf_common.STAGE_OUTPUTS) and
    fail if a required one is missing. Optional outputs that are absent are
    recorded as null so `status` does not flag them later.

    对某阶段声明的全部产出文件（见 sf_common.STAGE_OUTPUTS）计算哈希；必需文件缺失则报错。
    不存在的可选文件记为 null，避免后续 `status` 误报。
    """
    hashes: dict[str, str | None] = {}
    missing = []
    for fname, required in STAGE_OUTPUTS[stage]:
        h = content_hash(ws / fname)
        if h is None and required:
            missing.append(fname)
        hashes[fname] = h
    if missing:
        fail(f"stage {stage} is missing required outputs: {missing}",
             f"阶段 {stage} 缺少必需产出文件: {missing}")
    return hashes


def modified_since_checkpoint(ws: Path, state: dict, stage: str) -> list[str]:
    """
    Compare current file hashes with the checkpoint stored for a stage and
    return the names of outputs that changed or disappeared. These are the
    files the agent must re-read before continuing.

    将当前文件哈希与该阶段保存的检查点比较，返回被修改或被删除的产出文件名。agent 在
    继续之前必须重新阅读这些文件。
    """
    stored = state["stages"][stage].get("checkpoint_hashes") or {}
    changed = []
    for fname, old in stored.items():
        new = content_hash(ws / fname)
        if new != old:
            changed.append(fname)
    return changed


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #


def cmd_init(args: argparse.Namespace) -> None:
    """
    Create workspace/<name>/ (name defaults to the input folder's basename),
    write a fresh state.json, and record the name in workspace/ACTIVE so
    later commands need no --workspace argument. Refuses to overwrite an
    existing state.json unless --force is given.

    创建 workspace/<name>/（name 默认取输入目录名），写入全新的 state.json，并把名字记录
    到 workspace/ACTIVE，之后的命令无需再传 --workspace。除非给 --force，否则拒绝覆盖已有
    的 state.json。
    """
    input_dir = Path(args.input)
    if not input_dir.is_absolute():
        input_dir = (REPO_ROOT / input_dir).resolve()
    if not input_dir.is_dir():
        fail(f"input folder not found: {input_dir}", "输入目录不存在")
    name = args.name or input_dir.name
    ws = Path(args.workspace).resolve() if args.workspace else WORKSPACE_ROOT / name
    ws.mkdir(parents=True, exist_ok=True)
    if state_path(ws).exists() and not args.force:
        fail(f"{relpath(state_path(ws))} exists; use --force to recreate, or `status` to resume",
             "state.json 已存在；用 --force 重建，或用 status 恢复")
    state = fresh_state(name, input_dir, args.scheme)
    save_state(ws, state)
    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    ACTIVE_FILE.write_text((name if ws.parent == WORKSPACE_ROOT else str(ws)) + "\n", encoding="utf-8")
    say(f"workspace initialised at {relpath(ws)} (active)", f"已创建 workspace {relpath(ws)} 并设为活动")
    say(f"input: {relpath(input_dir)}  scheme: {args.scheme}", "")
    say(f"next: read {relpath(STAGES_DIR / STAGE_DOCS['S1'])} and run `start S1`",
        "下一步：阅读 S1 阶段文档并运行 start S1")


def cmd_status(args: argparse.Namespace) -> None:
    """
    Print the context pack used to resume: strategy name, scheme, per-stage
    status table, the current stage and its doc, files modified since the
    last checkpoint, open dialog questions for S3/S6, and xlsx/json freshness
    for the latest term file. Exits 0 always; it is informational.

    打印用于恢复的"上下文包"：策略名、分类方案、各阶段状态表、当前阶段及其说明文档、上次
    检查点之后被修改的文件、S3/S6 未回答的问题、最新术语文件的 xlsx/json 新旧关系。始终以
    0 退出，仅供参考。
    """
    ws = resolve_workspace(args.workspace)
    state = load_state(ws)
    cur = state["current_stage"]
    print(f"== strategy-formalizer status / 状态 ==")
    print(f"workspace : {relpath(ws)}")
    print(f"input     : {state.get('input_dir')}")
    print(f"scheme    : {state.get('scheme_id')}")
    print(f"current   : {cur}  ({STAGE_TITLES[cur][0]} / {STAGE_TITLES[cur][1]})")
    print()
    print("stage  status           completed_at")
    for s in STAGES:
        st = state["stages"][s]
        marker = "->" if s == cur else "  "
        print(f"{marker} {s}   {st['status']:<16} {st.get('completed_at') or '-'}")
    print()

    # Files edited by the user during the stop
    cur_state = state["stages"][cur]
    changed = modified_since_checkpoint(ws, state, cur) if cur_state.get("checkpoint_hashes") else []
    if cur_state["status"] == "awaiting_review":
        say(f"{cur} is awaiting your review. Edit outputs, then tell the agent to continue.",
            f"{cur} 等待人工审阅。修改产出文件后告诉 agent 继续。")
    if changed:
        say(f"files modified since {cur} checkpoint (RE-READ before continuing): {changed}",
            f"检查点之后被修改的文件（继续前必须重新阅读）: {changed}")
    elif cur_state.get("checkpoint_hashes"):
        say(f"no output of {cur} was modified since its checkpoint", "检查点之后没有文件被修改")

    # Open dialog questions
    for ds in DIALOG_STAGES:
        dpath = ws / f"{ds}_dialog.json"
        if dpath.exists():
            entries = load_json(dpath).get("entries", [])
            open_ids = [e["id"] for e in entries if e.get("status") == "open"]
            if open_ids:
                say(f"{ds} has OPEN questions the user has not answered: {open_ids}",
                    f"{ds} 尚有未回答的问题: {open_ids}")

    # xlsx vs json freshness for the most recent term file
    latest_terms = None
    for s in reversed(STAGES):
        f = TERM_FILE_BY_STAGE.get(s)
        if f and (ws / f).exists():
            latest_terms = ws / f
            break
    if latest_terms is not None:
        xlsx = latest_terms.with_suffix(".xlsx")
        # The xlsx is generated right after the json, so mtime alone is meaningless; flag it only when
        # its content differs from the checkpoint taken at complete/accept (i.e. the user edited it).
        # xlsx 总是在 json 之后生成，单看 mtime 无意义；只有内容与检查点不同（用户改过）时才提示。
        rel = str(xlsx.relative_to(ws))
        stored = None
        for st_ in state["stages"].values():
            if rel in (st_.get("checkpoint_hashes") or {}):
                stored = st_["checkpoint_hashes"][rel]
        if xlsx.exists() and stored is not None and content_hash(xlsx) != stored:
            say(f"{relpath(xlsx)} is NEWER than its json; run `sf_terms.py from-xlsx` to merge it",
                f"{relpath(xlsx)} 比 json 新；请先运行 sf_terms.py from-xlsx 合并")
        else:
            say(f"latest term file: {relpath(latest_terms)} (json is authoritative)",
                f"最新术语文件: {relpath(latest_terms)}（以 json 为准）")

    print()
    say(f"stage doc to read: {relpath(STAGES_DIR / STAGE_DOCS[cur])}", "应阅读的阶段说明文档")
    if cur_state["status"] == "pending":
        say(f"next command: `start {cur}`", "下一步命令")
    elif cur_state["status"] == "in_progress":
        say(f"{cur} in progress: finish outputs then run `complete {cur}`", "完成产出后运行 complete")
    elif cur_state["status"] == "awaiting_review":
        say(f"after the user says continue: run `accept {cur}`", "用户确认继续后运行 accept")
    elif cur_state["status"] == "done":
        say("pipeline finished; final/ is frozen", "流水线已完成，final/ 已冻结")


def cmd_start(args: argparse.Namespace) -> None:
    """
    Mark a stage in_progress. Requires every earlier stage to be done and the
    stage itself to be pending (or in_progress already, which is a no-op), so
    the DAG order cannot be skipped by accident.

    将某阶段标记为 in_progress。要求之前所有阶段均为 done，且该阶段本身为 pending（已是
    in_progress 则无操作），避免意外跳过 DAG 顺序。
    """
    ws = resolve_workspace(args.workspace)
    state = load_state(ws)
    stage = args.stage
    i = stage_index(stage)
    for prev in STAGES[:i]:
        if state["stages"][prev]["status"] != "done":
            fail(f"cannot start {stage}: {prev} is {state['stages'][prev]['status']}, not done",
                 f"无法开始 {stage}：{prev} 尚未 done")
    st = state["stages"][stage]
    if st["status"] == "in_progress":
        say(f"{stage} already in progress", f"{stage} 已在进行中")
        return
    if st["status"] != "pending":
        fail(f"cannot start {stage}: status is {st['status']} (use reopen to redo it)",
             f"无法开始 {stage}：状态为 {st['status']}（重做请用 reopen）")
    st["status"] = "in_progress"
    st["started_at"] = now_iso()
    state["current_stage"] = stage
    save_state(ws, state)
    say(f"{stage} started: {STAGE_TITLES[stage][0]}", f"{stage} 已开始: {STAGE_TITLES[stage][1]}")
    say(f"read {relpath(STAGES_DIR / STAGE_DOCS[stage])}", "请阅读该阶段说明文档")


def cmd_complete(args: argparse.Namespace) -> None:
    """
    Record the checkpoint for a stage's outputs and set it to awaiting_review.
    This is the STOP point: after this command the agent must print the
    review checklist and end its turn. Fails if a required output is missing
    or the stage is not in_progress. The last stage (S8) has nothing after
    it to accept into, so completing it marks it done directly: freezing
    final/ ends the run.

    记录该阶段产出文件的检查点并置为 awaiting_review。这就是"停止点"：此命令之后 agent
    必须打印审阅清单并结束本轮。必需文件缺失或阶段不处于 in_progress 时报错。最后一个阶段
    （S8）之后没有需要 accept 进入的阶段，因此 complete 直接标记为 done：冻结 final/ 即结束。
    """
    ws = resolve_workspace(args.workspace)
    state = load_state(ws)
    stage = args.stage
    stage_index(stage)
    st = state["stages"][stage]
    if st["status"] != "in_progress":
        fail(f"cannot complete {stage}: status is {st['status']}", f"无法完成 {stage}：状态为 {st['status']}")
    st["checkpoint_hashes"] = checkpoint(ws, stage)
    st["completed_at"] = now_iso()
    state["current_stage"] = stage
    if stage == STAGES[-1]:
        st["status"] = "done"
        st["accepted_at"] = st["completed_at"]
        save_state(ws, state)
        say(f"{stage} complete -> done. The run is finished; final/ is frozen. Print the final message:",
            f"{stage} 已完成并标记 done。本次运行结束，final/ 已冻结。请打印最终消息：")
    else:
        st["status"] = "awaiting_review"
        save_state(ws, state)
        say(f"{stage} complete -> awaiting_review. STOP now and ask the user to review:",
            f"{stage} 已完成，等待审阅。现在停止，请用户审阅：")
    for fname, _ in STAGE_OUTPUTS[stage]:
        if (ws / fname).exists():
            print(f"    - {relpath(ws / fname)}")


def cmd_accept(args: argparse.Namespace) -> None:
    """
    Called after the user says continue: re-hash outputs (so user edits become
    the new baseline), mark the stage done, and advance current_stage to the
    next pending stage. Prints which files the user changed so the agent
    re-reads them before starting the next stage.

    用户说"继续"之后调用：重新计算产出哈希（用户的修改成为新基线）、标记该阶段 done、
    把 current_stage 推进到下一阶段。同时打印用户改动过的文件，供 agent 在开始下一阶段前
    重新阅读。
    """
    ws = resolve_workspace(args.workspace)
    state = load_state(ws)
    stage = args.stage
    i = stage_index(stage)
    st = state["stages"][stage]
    if st["status"] != "awaiting_review":
        fail(f"cannot accept {stage}: status is {st['status']}", f"无法接受 {stage}：状态为 {st['status']}")
    changed = modified_since_checkpoint(ws, state, stage)
    st["checkpoint_hashes"] = checkpoint(ws, stage)
    st["status"] = "done"
    st["accepted_at"] = now_iso()
    if i + 1 < len(STAGES):
        state["current_stage"] = STAGES[i + 1]
    save_state(ws, state)
    if changed:
        say(f"user edited during review (re-read them): {changed}", f"用户在审阅期间修改了: {changed}")
    say(f"{stage} accepted -> done. current stage is now {state['current_stage']}",
        f"{stage} 已接受。当前阶段为 {state['current_stage']}")


def cmd_reopen(args: argparse.Namespace) -> None:
    """
    Rewind to a stage: set it to in_progress and reset every later stage to
    pending (their files are left on disk but their checkpoints are cleared).
    Requires --yes because downstream work is invalidated; with --archive the
    later stages' outputs are moved into workspace/_archive/<timestamp>/.

    回退到某阶段：将其置为 in_progress，并把之后所有阶段重置为 pending（文件保留在磁盘，
    但检查点清空）。因为会使下游工作失效，必须显式传 --yes；加 --archive 会把下游产出移动
    到 workspace/_archive/<时间戳>/。
    """
    ws = resolve_workspace(args.workspace)
    state = load_state(ws)
    stage = args.stage
    i = stage_index(stage)
    if not args.yes:
        fail(f"reopen {stage} resets {STAGES[i + 1:]}; re-run with --yes to confirm",
             f"reopen 会重置 {STAGES[i + 1:]}，确认请加 --yes")
    if args.archive:
        dest = ws / "_archive" / now_iso().replace(":", "-")
        for later in STAGES[i + 1:]:
            for fname, _ in STAGE_OUTPUTS[later]:
                src = ws / fname
                if src.exists():
                    (dest / fname).parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(src), str(dest / fname))
        say(f"archived downstream outputs to {relpath(dest)}", "下游产出已归档")
    st = state["stages"][stage]
    st["status"] = "in_progress"
    st["started_at"] = now_iso()
    st["completed_at"] = None
    st["accepted_at"] = None
    st["checkpoint_hashes"] = {}
    for later in STAGES[i + 1:]:
        state["stages"][later] = {"status": "pending", "started_at": None, "completed_at": None,
                                  "accepted_at": None, "checkpoint_hashes": {}}
    state["current_stage"] = stage
    save_state(ws, state)
    say(f"{stage} reopened; {STAGES[i + 1:]} reset to pending", f"{stage} 已重开；下游阶段已重置")


def cmd_set_scheme(args: argparse.Namespace) -> None:
    """
    Record the classification scheme id chosen with the user in S5 (must
    match a templates/categories.<id>.json file).

    记录 S5 中与用户商定的分类方案 id（必须对应一个 templates/categories.<id>.json 文件）。
    """
    ws = resolve_workspace(args.workspace)
    state = load_state(ws)
    tpl = TEMPLATES_DIR / f"categories.{args.scheme}.json"
    if not tpl.exists():
        fail(f"no template {relpath(tpl)}", "分类方案模板不存在")
    state["scheme_id"] = args.scheme
    save_state(ws, state)
    say(f"scheme set to {args.scheme}", f"分类方案已设为 {args.scheme}")


def build_parser() -> argparse.ArgumentParser:
    """
    Build the argparse CLI with one sub-command per function above.

    构建 argparse 命令行，每个子命令对应上面的一个函数。
    """
    p = argparse.ArgumentParser(description="strategy-formalizer state machine / 状态机")
    p.add_argument("--workspace", "-w", help="workspace dir or name (default: workspace/ACTIVE)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="create a workspace for an input folder")
    s.add_argument("--input", "-i", required=True, help="strategy input folder, e.g. strategy_zoo/大小周期共振")
    s.add_argument("--name", help="workspace name (default: input folder name)")
    s.add_argument("--scheme", default="role_x_phase", help="classification scheme id")
    s.add_argument("--force", action="store_true")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("status", help="print the resume context pack")
    s.set_defaults(func=cmd_status)

    for name, fn in (("start", cmd_start), ("complete", cmd_complete), ("accept", cmd_accept)):
        s = sub.add_parser(name)
        s.add_argument("stage", choices=STAGES)
        s.set_defaults(func=fn)

    s = sub.add_parser("reopen", help="rewind to a stage and reset downstream")
    s.add_argument("stage", choices=STAGES)
    s.add_argument("--yes", action="store_true")
    s.add_argument("--archive", action="store_true", help="move downstream outputs to _archive/")
    s.set_defaults(func=cmd_reopen)

    s = sub.add_parser("set-scheme")
    s.add_argument("scheme")
    s.set_defaults(func=cmd_set_scheme)
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
