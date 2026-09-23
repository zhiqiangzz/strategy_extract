"""
Agents: read the English part only. 中文仅供人类阅读。

S7/S8 tests: scaffold formal.json from the fixture terms, validate it,
generate a compilable stub, render mermaid/dot (png if graphviz is
available), and run the S8 cross-check including a deliberate stray bold.

S7/S8 测试：由夹具术语生成 formal.json 并校验、生成可编译的桩代码、渲染 mermaid/dot
（有 graphviz 时渲染 png），并运行 S8 交叉核对，包括故意加入的错误加粗。
"""
from __future__ import annotations

import shutil

import pytest

import sf_check
import sf_formal
import sf_graph
import sf_terms
from conftest import load


def _scaffold(ws):
    """
    Scaffold S7_formal.json from the fixture terms and fill inputs/outputs so it validates without warnings.

    由夹具术语生成 S7_formal.json 并补上输入/输出，使其无警告地通过校验。
    """
    w = str(ws)
    sf_formal.main(["--workspace", w, "scaffold", "S6_terms_defined.json", "S7_formal.json"])
    formal = load(ws / "S7_formal.json")
    for cb in formal["callbacks"]:
        cb["inputs"] = [{"name": "bars", "type": "OHLCV[]", "source_term_id": None, "description_en": "recent bars"}]
        cb["output"] = {"type": "enum", "values": ["long", "short", "uncertain"], "description_en": ""}
    (ws / "S7_formal.json").write_text(__import__("json").dumps(formal, ensure_ascii=False, indent=2), encoding="utf-8")
    return formal


def test_scaffold_validate_stub(ws):
    """
    Scaffold produces 5 callbacks and 2 parameters with supports-derived relations; the generated stub compiles and carries the auxiliary notes.

    scaffold 生成 5 个回调、2 个参数及由 supports 推出的关系；生成的桩代码可编译并包含辅助说明。
    """
    formal = _scaffold(ws)
    assert len(formal["callbacks"]) == 5 and len(formal["parameters"]) == 2
    cb1 = next(c for c in formal["callbacks"] if c["term_id"] == "T003")
    assert "T007" in cb1["aux_term_ids"] and "T011" in cb1["aux_term_ids"]
    assert any(r["from"] == "T008" and r["to"] == "T004" and r["type"] == "constrains" for r in formal["relations"])
    terms = sf_terms.load_terms(ws / "S6_terms_defined.json")
    errors, _ = sf_formal.validate(formal, terms)
    assert errors == []
    sf_formal.main(["--workspace", str(ws), "gen-stub", "S7_formal.json", "--terms", "S6_terms_defined.json",
                    "--out", "S7_callbacks_stub.py", "--strategy-name", "demo"])
    code = (ws / "S7_callbacks_stub.py").read_text(encoding="utf-8")
    assert "def major_timeframe_direction(self, bars: Any) -> Literal['long', 'short', 'uncertain']" in code
    assert "尽快但不是立刻" in code
    compile(code, "stub", "exec")


def test_formal_xlsx_roundtrip(ws):
    """
    Inputs and enum outputs survive to-xlsx -> from-xlsx.

    输入与枚举输出经 to-xlsx -> from-xlsx 往返后保持不变。
    """
    _scaffold(ws)
    w = str(ws)
    sf_formal.main(["--workspace", w, "to-xlsx", "S7_formal.json"])
    sf_formal.main(["--workspace", w, "from-xlsx", "S7_formal.xlsx"])
    formal = load(ws / "S7_formal.json")
    assert formal["callbacks"][0]["inputs"][0]["name"] == "bars"
    assert formal["callbacks"][0]["output"]["values"] == ["long", "short", "uncertain"]


def test_graph(ws):
    """
    Mermaid and dot outputs contain live nodes and typed edges, exclude dropped terms, and a png is rendered when graphviz is available.

    Mermaid 与 dot 输出包含存活节点和带类型的边、排除已丢弃术语；有 graphviz 时渲染 png。
    """
    _scaffold(ws)
    args = ["--workspace", str(ws), "render", "S7_formal.json", "--terms", "S6_terms_defined.json"]
    if shutil.which("pixi") or shutil.which("dot"):
        args.append("--png")
    sf_graph.main(args)
    mmd = (ws / "S7_term_graph.mmd").read_text(encoding="utf-8")
    dot = (ws / "S7_term_graph.dot").read_text(encoding="utf-8")
    assert "T001[[" in mmd and "T012" not in mmd
    assert "T008 -> T004" in dot
    if "--png" in args:
        assert (ws / "S7_term_graph.png").exists()


def test_check_and_freeze(ws):
    """
    The fixture passes the S8 check; a stray bold phrase is reported and blocks freeze; after reverting, run and freeze produce final/.

    夹具通过 S8 检查；多余的加粗短语被报告并阻止冻结；恢复后 run 与 freeze 生成 final/。
    """
    _scaffold(ws)
    sf_formal.main(["--workspace", str(ws), "gen-stub", "S7_formal.json", "--terms", "S6_terms_defined.json"])
    errors, warnings = sf_check.check(ws, ws / "S5_summary_marked.md", ws / "S6_terms_defined.json",
                                      ws / "S7_formal.json", None)
    assert errors == []
    text = (ws / "S5_summary_marked.md").read_text(encoding="utf-8")
    (ws / "S5_summary_marked.md").write_text(text.replace("止损只进不退", "**止损只进不退**"), encoding="utf-8")
    errors, _ = sf_check.check(ws, ws / "S5_summary_marked.md", ws / "S6_terms_defined.json",
                               ws / "S7_formal.json", None)
    assert any("止损只进不退" in e for e in errors)
    with pytest.raises(SystemExit):
        sf_check.main(["--workspace", str(ws), "freeze"])
    (ws / "S5_summary_marked.md").write_text(text, encoding="utf-8")
    sf_check.main(["--workspace", str(ws), "run"])
    sf_check.main(["--workspace", str(ws), "freeze"])
    assert (ws / "final" / "strategy.md").exists() and (ws / "final" / "callbacks_stub.py").exists()
    assert "Script findings" in (ws / "S8_check_report.md").read_text(encoding="utf-8")
