"""
Agents: read the English part only. 中文仅供人类阅读。

positions.py — current open positions, from the trading-core control API or
from a file.

`from_control_api(url, account)` calls `GET /api/positions?account=` and
`GET /api/account?account=` of the running trading-core and returns the net
positions (tolerant to the field spellings used by the core: `is_long` or
`direction`, `vt_symbol`/`symbol`) and the account capital. `from_file(path)`
reads the same shape from JSON for offline runs. Variety codes are derived
from the contract code (letters before the digits, upper-cased), matching
how rust_core's session gate does it.

positions.py 从 trading-core 的 control API 或文件获取当前持仓。`from_control_api(url, account)`
调用 `GET /api/positions?account=` 和 `GET /api/account?account=`，返回净持仓（兼容 core 的字段
写法：`is_long` 或 `direction`、`vt_symbol`/`symbol`）和账户资金。`from_file(path)` 从 JSON 读同样
结构以便离线运行。品种代码取合约代码中数字前的字母并大写，与 rust_core 的时段闸门做法一致。
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from .schemas import Position


def variety_of(contract: str) -> str:
    """
    "cu2611.SHFE" / "MA610.CZCE" / "CU2611" -> "CU" / "MA" / "CU".

    从合约代码取品种大写码。
    """
    code = contract.split(".")[0]
    return re.match(r"[A-Za-z]+", code).group(0).upper() if re.match(r"[A-Za-z]+", code) else code.upper()


def _position_from_obj(o: dict) -> Optional[Position]:
    """
    Build a Position from one net-position JSON object; None for flat rows.

    从一条净持仓 JSON 构造 Position；手数为 0 返回 None。
    """
    vol = int(o.get("volume") or 0)
    if vol <= 0:
        return None
    vt = o.get("vt_symbol") or o.get("symbol") or ""
    if "is_long" in o:
        direction = "long" if o["is_long"] else "short"
    else:
        d = str(o.get("direction") or "").lower()
        direction = "long" if d.startswith("l") or d == "多" else "short"
    price = o.get("entry_price") or o.get("avg_price") or o.get("open_price")
    return Position(vt_symbol=vt, variety_code=o.get("variety_code") or variety_of(vt), direction=direction,
                    volume=vol, entry_price=float(price) if price not in (None, "") else None)


def parse_positions(payload: dict | list) -> dict[str, Position]:
    """
    Map variety code -> Position from a control-API positions payload or a
    bare list.

    把 control API 的持仓响应或裸列表转为 品种代码 -> Position。
    """
    rows = payload if isinstance(payload, list) else (payload.get("positions") or payload.get("net_positions") or [])
    out: dict[str, Position] = {}
    for o in rows:
        p = _position_from_obj(o)
        if p:
            out[p.variety_code] = p
    return out


def _get(url: str, timeout: int = 10) -> dict:
    """
    GET a JSON document.

    GET 一个 JSON 文档。
    """
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def from_control_api(base_url: str, account: Optional[str]) -> tuple[dict[str, Position], Optional[float]]:
    """
    Positions and available capital from a running trading-core; raises
    urllib.error.URLError when the core is not reachable.

    从运行中的 trading-core 取持仓与可用资金；core 不可达时抛 urllib.error.URLError。
    """
    q = f"?account={account}" if account else ""
    positions = parse_positions(_get(f"{base_url}/api/positions{q}"))
    capital: Optional[float] = None
    try:
        acct = _get(f"{base_url}/api/account{q}").get("account") or {}
        capital = float(acct.get("balance") or acct.get("available") or 0) or None
    except (urllib.error.URLError, ValueError, TypeError):
        capital = None
    return positions, capital


def from_file(path: Path) -> dict[str, Position]:
    """
    Positions from a JSON file (control-API shape or a list of objects).

    从 JSON 文件读持仓（control API 形状或对象列表）。
    """
    return parse_positions(json.loads(Path(path).read_text(encoding="utf-8")))
