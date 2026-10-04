"""
Agents: read the English part only. 中文仅供人类阅读。

claude_cli.py — run one structured LLM call through the locally logged-in
Claude Code CLI.

`run_claude(prompt, schema, ...)` executes `claude -p <prompt> --model <m>
--effort <e> --output-format json --json-schema <schema> --max-turns 3
--disallowedTools ...` with a clean working directory (no CLAUDE.md, no
project memory) and with the CLAUDECODE / CLAUDE_CODE_* variables removed
from the environment, so it works both from a terminal and from inside a
Claude Code session. The file, shell, web and agent tools are disallowed, so
the extra turns serve to resubmit a structured output that failed
validation. It returns the `structured_output` object and the call's cost,
retries on transient failures, and stores the full prompt, raw response,
start/finish times and metadata under `record_dir` for audit. The function is deliberately
synchronous; callers parallelise over symbols and sides.

claude_cli.py 通过本地已登录的 Claude Code CLI 执行一次结构化 LLM 调用。`run_claude(prompt,
schema, ...)` 以干净的工作目录（无 CLAUDE.md、无项目记忆）执行 `claude -p ... --json-schema`，
并从环境中去掉 CLAUDECODE / CLAUDE_CODE_* 变量，因此在终端和 Claude Code 会话内都能运行。文件、shell、
网络和子代理工具都被禁用，`--max-turns 3` 多出的轮次用于让模型重新提交未通过校验的结构化输出。返回
`structured_output` 对象和本次费用，瞬时失败会重试，并把完整提示词、原始响应、起止时间和元数据存到
`record_dir` 供审计。函数是同步的；调用方按品种和多空两侧并行。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

DISALLOWED_TOOLS = "Bash,Read,Write,Edit,MultiEdit,NotebookEdit,WebSearch,WebFetch,Agent,Glob,Grep"


@dataclass
class ClaudeResult:
    """
    One call's outcome: the validated structured output plus bookkeeping.

    一次调用的结果：结构化输出及费用/耗时等元数据。
    """
    output: dict
    cost_usd: float
    duration_ms: int
    model: str
    raw: dict


class ClaudeCliError(RuntimeError):
    """
    Raised when the CLI fails, times out, or returns no structured output.

    CLI 失败、超时或未返回结构化输出时抛出。
    """


def _clean_env() -> dict[str, str]:
    """
    Environment for the child process without nested-session markers.

    去掉嵌套会话标记的子进程环境变量。
    """
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE" and not k.startswith("CLAUDE_CODE_")}
    return env


def run_claude(prompt: str, schema: dict, *, model: str = "opus", effort: str = "xhigh", timeout_s: int = 600,
               retries: int = 1, record_dir: Path | None = None, record_name: str = "call",
               runner: Callable[..., subprocess.CompletedProcess] | None = None) -> ClaudeResult:
    """
    Execute the CLI once (with retries) and return the structured output.
    `runner` lets tests substitute a fake subprocess.

    执行一次 CLI（带重试）并返回结构化输出。`runner` 供测试注入假的子进程。
    """
    exe = shutil.which("claude")
    if exe is None and runner is None:
        raise ClaudeCliError("claude CLI not found on PATH / 未找到 claude 命令")
    runner = runner or subprocess.run
    work = Path(tempfile.mkdtemp(prefix="resonance_claude_"))
    cmd = [exe or "claude", "-p", prompt, "--model", model, "--effort", effort, "--output-format", "json",
           "--json-schema", json.dumps(schema, ensure_ascii=False), "--max-turns", "3",
           "--disallowedTools", DISALLOWED_TOOLS]
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        t0 = time.perf_counter()
        started_at = datetime.now().astimezone().isoformat(timespec="milliseconds")
        try:
            proc = runner(cmd, cwd=str(work), env=_clean_env(), stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout_s)
        except subprocess.TimeoutExpired as exc:
            last_err = ClaudeCliError(f"claude timed out after {timeout_s}s")
            continue
        duration_ms = int((time.perf_counter() - t0) * 1000)
        raw: dict = {}
        try:
            raw = json.loads(proc.stdout) if proc.stdout.strip() else {}
        except json.JSONDecodeError:
            raw = {"_unparsed_stdout": proc.stdout[-4000:]}
        if record_dir is not None:
            record_dir.mkdir(parents=True, exist_ok=True)
            (record_dir / f"{record_name}.prompt.md").write_text(prompt, encoding="utf-8")
            (record_dir / f"{record_name}.response.json").write_text(
                json.dumps({"attempt": attempt, "returncode": proc.returncode, "started_at": started_at,
                            "finished_at": datetime.now().astimezone().isoformat(timespec="milliseconds"), "stderr": proc.stderr[-4000:], "raw": raw},
                           ensure_ascii=False, indent=2), encoding="utf-8")
        output = raw.get("structured_output")
        if output is None and isinstance(raw.get("result"), str):
            try:
                output = json.loads(raw["result"])
            except json.JSONDecodeError:
                output = None
        if proc.returncode == 0 and isinstance(output, dict) and not raw.get("is_error"):
            model_used = next(iter((raw.get("modelUsage") or {}).keys()), model)
            shutil.rmtree(work, ignore_errors=True)
            return ClaudeResult(output=output, cost_usd=float(raw.get("total_cost_usd") or 0.0),
                                duration_ms=duration_ms, model=model_used, raw=raw)
        last_err = ClaudeCliError(f"claude returned rc={proc.returncode}, is_error={raw.get('is_error')}, "
                                  f"stderr={proc.stderr[-300:]!r}, result={str(raw.get('result'))[:300]!r}")
    shutil.rmtree(work, ignore_errors=True)
    raise last_err or ClaudeCliError("claude call failed")
