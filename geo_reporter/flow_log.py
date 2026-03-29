"""流程追踪：统一输出到 stderr。"""

from __future__ import annotations

import sys
from datetime import datetime


def flow_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def flow_info(msg: str) -> None:
    for line in msg.splitlines():
        print(f"[geo_reporter] [{flow_ts()}] {line}", file=sys.stderr)
