"""
Agents: read the English part only. 中文仅供人类阅读。

Regenerate `web/tests/fixtures/flow.sample.json`, the sample flow the web
template is tested against. It is built from the same tiny evidence pack and
scripted fake runner as the judge tests (no model call), in the scenario of
`test_flow.sample_outcome`. Run it after changing the shape of
`flow.build_flow`:

    uv run python -m strategies.resonance.tests.make_web_fixture

重新生成 `web/tests/fixtures/flow.sample.json`，即网页模板测试所用的样例 flow。它由与判断层测试相同的
微型证据包和脚本化假运行器生成（不调用模型），场景见 `test_flow.sample_outcome`。修改
`flow.build_flow` 的输出形状后运行上面的命令。
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from strategies.resonance.tests import conftest
from strategies.resonance.tests.test_flow import FIXTURE, sample_outcome


def main() -> None:
    """
    Build the sample flow in a temp dir and write the fixture.

    在临时目录里生成样例 flow 并写出样例文件。
    """
    with tempfile.TemporaryDirectory() as tmp:
        pack = conftest.build_pack(Path(tmp))
        _, flow = sample_outcome(pack, Path(tmp) / "runs")
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(json.dumps(flow, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {FIXTURE} ({len(flow['steps'])} steps, {len(flow['threads'])} threads)")


if __name__ == "__main__":
    main()
