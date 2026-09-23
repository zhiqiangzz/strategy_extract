"""
Agents: read the English part only. 中文仅供人类阅读。

Dialog tests: questions are stored open before answers, answers are logged,
markdown round-trips back into json including answers typed by the user.

对话测试：问题先以 open 状态落盘，回答被记录，markdown 能往返回 json，包括用户直接在
md 中填写的回答。
"""
from __future__ import annotations

import sf_dialog
from conftest import load


def test_add_answer_roundtrip(ws, capsys):
    """
    Full S6 dialog lifecycle: add two open questions in one round, answer one via CLI, answer the other by editing the markdown and merging it back, close, then confirm a new question opens round 2.

    完整的 S6 对话生命周期：同一轮添加两个 open 问题，一个用命令行回答，另一个在 markdown 中作答后合并回来，关闭，再确认新问题会开启第 2 轮。
    """
    w = str(ws)
    sf_dialog.main(["--workspace", w, "--stage", "S6", "add", "-q", "大周期具体指哪个级别？", "--affects-terms", "T001"])
    sf_dialog.main(["--workspace", w, "--stage", "S6", "add", "-q", "有利运动如何量化？", "--affects-terms", "T003"])
    d = load(ws / "S6_dialog.json")
    assert [e["status"] for e in d["entries"]] == ["open", "open"]
    assert d["entries"][0]["round"] == d["entries"][1]["round"] == 1
    sf_dialog.main(["--workspace", w, "--stage", "S6", "answer", "D001", "-a", "日线。"])
    md = (ws / "S6_dialog.md").read_text(encoding="utf-8")
    assert "### D001 [answered]" in md and "### D002 [open]" in md
    # user answers D002 by editing the markdown
    md = md.replace("**A (user, ):**\n\n", "**A (user, ):**\n浮盈达到 1R。\n\n", 1)
    (ws / "S6_dialog.md").write_text(md, encoding="utf-8")
    sf_dialog.main(["--workspace", w, "--stage", "S6", "from-md"])
    d = load(ws / "S6_dialog.json")
    assert d["entries"][1]["status"] == "answered" and d["entries"][1]["answer_zh"] == "浮盈达到 1R。"
    sf_dialog.main(["--workspace", w, "--stage", "S6", "close", "D002", "-r", "T003 定义更新"])
    assert load(ws / "S6_dialog.json")["entries"][1]["status"] == "closed"
    # a fresh question after all are answered/closed starts round 2
    sf_dialog.main(["--workspace", w, "--stage", "S6", "add", "-q", "第二轮问题"])
    assert load(ws / "S6_dialog.json")["entries"][2]["round"] == 2


def test_parse_md_multiline():
    """
    Multi-line questions and the affects line survive render_md -> parse_md.

    多行问题与 affects 行经过 render_md -> parse_md 后保持不变。
    """
    text = sf_dialog.render_md({"stage": "S3", "entries": [
        {"id": "D001", "round": 1, "status": "open", "question_zh": "第一行\n第二行", "answer_zh": None,
         "affects": {"terms": ["T001"], "sections": ["premise"]}, "resolution": None}]})
    parsed = sf_dialog.parse_md(text)
    assert parsed[0]["question_zh"] == "第一行\n第二行"
    assert parsed[0]["affects"] == {"terms": ["T001"], "sections": ["premise"]}
