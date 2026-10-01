"""
Agents: read the English part only. 中文仅供人类阅读。

S7/S8 tests: scaffold formal.json from the fixture terms, validate it,
generate a compilable stub, render mermaid/dot (pdf if graphviz is
available), and run the S8 cross-check including a deliberate stray bold.

S7/S8 测试：由夹具术语生成 formal.json 并校验、生成可编译的桩代码、渲染 mermaid/dot
（有 graphviz 时渲染 pdf），并运行 S8 交叉核对，包括故意加入的错误加粗。
"""
from __future__ import annotations

import shutil

import pytest

import sf_check
import sf_driver
import sf_formal
import sf_graph
import sf_terms
from conftest import load


def _scaffold(ws):
    """
    Scaffold S7_formal.json from the fixture terms with a complete flow (via
    test_driver.formal_with_flow) and generate the stub and driver, so the
    S7 outputs exist for the check/freeze tests.

    由夹具术语生成带完整 flow 的 S7_formal.json（借用 test_driver.formal_with_flow），并生成桩
    与 driver，使 check/freeze 测试所需的 S7 产出齐全。
    """
    from test_driver import formal_with_flow
    formal = formal_with_flow(ws)
    w = str(ws)
    sf_formal.main(["--workspace", w, "gen-stub", "S7_formal.json", "--terms", "S6_terms_defined.json", "--out", "S7_callbacks_stub.py"])
    sf_driver.main(["--workspace", w, "gen", "S7_formal.json", "--terms", "S6_terms_defined.json", "--out", "S7_strategy_driver.py", "--strategy-name", "demo"])
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
    assert "def major_timeframe_direction(self, major_tf_data: MarketData, instrument: Instrument) -> Literal['long', 'short', 'uncertain']" in code
    assert "class MarketData" in code and "class EntryDecision" in code
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
    assert formal["callbacks"][0]["inputs"][0]["name"] == "major_tf_data"
    assert formal["callbacks"][0]["output"]["values"] == ["long", "short", "uncertain"]


def test_graph(ws):
    """
    Mermaid and dot outputs contain live nodes and typed edges, exclude dropped terms, and a pdf is rendered when graphviz is available.

    Mermaid 与 dot 输出包含存活节点和带类型的边、排除已丢弃术语；有 graphviz 时渲染 pdf。
    """
    _scaffold(ws)
    args = ["--workspace", str(ws), "render", "S7_formal.json", "--terms", "S6_terms_defined.json"]
    if shutil.which("pixi") or shutil.which("dot"):
        args.append("--pdf")
    sf_graph.main(args)
    mmd = (ws / "S7_term_graph.mmd").read_text(encoding="utf-8")
    dot = (ws / "S7_term_graph.dot").read_text(encoding="utf-8")
    assert "T001[[" in mmd and "T012" not in mmd
    assert "T008 -> T004" in dot
    if "--pdf" in args:
        assert (ws / "S7_term_graph.pdf").exists()


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
    drv = (ws / "final" / "strategy_driver.py").read_text(encoding="utf-8")
    assert "from callbacks_stub import" in drv
    assert "Script findings" in (ws / "S8_check_report.md").read_text(encoding="utf-8")


def test_s1_coverage():
    """
    A clean text that merges timestamped lines into paragraphs (with new
    punctuation and headings) covers the raw text; dropping a sentence is
    reported.

    把时间戳行合并成段落（带新标点和标题）的 clean 文本能覆盖原文；漏掉一句会被报告。
    """
    raw = "[0s] 大周期判断趋势方向,\n[5s] 小周期入场。\n[9s] 然后尽快把止损移到成本价。\n[12s] (与上一句重复,已并入上一句)\n"
    clean = "## 框架\n\n大周期判断趋势方向，小周期入场。然后尽快把止损移到成本价。\n"
    assert sf_check.s1_coverage(raw, clean) == []
    assert sf_check.s1_coverage(raw, "## 框架\n\n大周期判断趋势方向，小周期入场。\n") == ["[9s] 然后尽快把止损移到成本价。"]
