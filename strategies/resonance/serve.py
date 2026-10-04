"""
Agents: read the English part only. 中文仅供人类阅读。

serve.py — a localhost HTTP server for the page template and its data.

`serve(runs_dir, port)` serves the built template (`web/dist`, produced by
`pixi run web-build`) at `/` and, under `/runs/`, only the files the page
reads: `index.json` and `<pack_date>/<symbol>/flow.json`. Everything else
in the runs directory (prompts, raw responses, decision caches) answers
404. `make_server` builds the server without starting it, for tests and for
callers that want their own loop.

serve.py 是页面模板及其数据的本机 HTTP 服务。`serve(runs_dir, port)` 在 `/` 提供构建好的模板
（`web/dist`，由 `pixi run web-build` 生成），在 `/runs/` 下只提供页面读取的文件：`index.json` 和
`<包日期>/<品种>/flow.json`；runs 目录里的其他内容（提示词、原始响应、决策缓存）一律返回 404。
`make_server` 只构造不启动，供测试和需要自己控制循环的调用方使用。
"""
from __future__ import annotations

import re
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .config import PACKAGE_DIR

DIST_DIR = PACKAGE_DIR / "web" / "dist"
_DATA_PATH = re.compile(r"^/runs/(index\.json|\d{4}-\d{2}-\d{2}/[A-Za-z0-9]+/flow\.json)$")


class _Handler(SimpleHTTPRequestHandler):
    """
    Static files from the template build; `/runs/` limited to flow data.

    模板构建产物的静态文件；`/runs/` 只放行 flow 数据。
    """

    def __init__(self, *args, runs_dir: Path, **kwargs):
        """Remember where the flow data lives.

        记下 flow 数据所在目录。
        """
        self.runs_dir = Path(runs_dir)
        super().__init__(*args, **kwargs)

    def do_GET(self):  # noqa: N802 - name fixed by http.server
        """Serve an allowed data file, or fall through to the template.

        返回放行的数据文件，否则交给模板静态文件处理。
        """
        path = self.path.split("?", 1)[0].split("#", 1)[0]
        if not path.startswith("/runs/"):
            return super().do_GET()
        target = self.runs_dir / path[len("/runs/"):]
        if not _DATA_PATH.match(path) or not target.is_file():
            return self.send_error(404, "not a flow data file")
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: A002 - signature fixed by http.server
        """Keep the console quiet.

        不向控制台打印访问日志。
        """


def make_server(runs_dir: Path, port: int = 8770, dist_dir: Path = DIST_DIR) -> ThreadingHTTPServer:
    """
    Build the server bound to 127.0.0.1 (port 0 picks a free port).

    构造绑定在 127.0.0.1 的服务（端口 0 表示自动选空闲端口）。
    """
    return ThreadingHTTPServer(("127.0.0.1", port), partial(_Handler, directory=str(dist_dir), runs_dir=runs_dir))


def serve(runs_dir: Path, port: int = 8770, dist_dir: Path = DIST_DIR) -> int:
    """
    Serve until interrupted; returns an exit code. Refuses to start when the
    template has not been built.

    持续服务直到被中断；返回退出码。模板尚未构建时拒绝启动。
    """
    if not (dist_dir / "index.html").exists():
        print(f"[web] {dist_dir} has no build yet: run `pixi run web-install` once, then `pixi run web-build`")
        return 2
    server = make_server(runs_dir, port, dist_dir)
    print(f"[web] http://127.0.0.1:{server.server_address[1]}/  (template {dist_dir}, data {runs_dir})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
