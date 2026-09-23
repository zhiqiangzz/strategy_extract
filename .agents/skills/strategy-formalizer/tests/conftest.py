"""
Agents: read the English part only. 中文仅供人类阅读。

Shared pytest fixtures: a temporary workspace populated from tests/fixtures,
and helpers that load fixture files. Tests call the scripts' main() with an
explicit --workspace so they never touch workspace/ACTIVE.

共享的 pytest 夹具：由 tests/fixtures 填充的临时 workspace，以及读取夹具文件的辅助函数。
测试用显式 --workspace 调用脚本的 main()，不会触碰 workspace/ACTIVE。
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def ws(tmp_path: Path) -> Path:
    """
    Create a temporary workspace with the fixture summary/terms/dialog copied
    under their S5/S6/S3 names.

    创建临时 workspace，把夹具中的总结/术语/对话复制为 S5/S6/S3 的文件名。
    """
    w = tmp_path / "ws"
    w.mkdir()
    shutil.copy(FIXTURES / "terms_defined.json", w / "S6_terms_defined.json")
    shutil.copy(FIXTURES / "summary_marked.md", w / "S5_summary_marked.md")
    shutil.copy(FIXTURES / "dialog_S3.json", w / "S3_dialog.json")
    return w


def load(p: Path):
    """
    Read a JSON file.

    读取 JSON 文件。
    """
    return json.loads(p.read_text(encoding="utf-8"))
