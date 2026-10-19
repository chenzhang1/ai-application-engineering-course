# 综合项目/项目三_Java与Python协作Agent/planagent/audit.py
"""审计日志：每次工具调用一条 JSONL（ch54 EX-54-03 的工程化版本）。

五要素：who（actor+role）/ when（ts）/ what（tool+args）/ outcome / context（trace_id）。
被拒绝的调用同样留痕（denied 是最有价值的审计事件）。
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any


class AuditLog:
    """JSONL 追加式审计日志（进程内单写者锁；多实例部署走采集管道聚合）。"""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def record(self, *, trace_id: str, actor: str, role: str, tool: str,
               args: dict[str, Any], outcome: str, detail: str = "",
               duration_ms: float = 0.0) -> dict[str, Any]:
        rec = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S") + f".{int(time.time() * 1000) % 1000:03d}",
            "trace_id": trace_id,
            "actor": actor,
            "role": role,
            "tool": tool,
            "args": args,
            "outcome": outcome,
            "detail": detail[:300],
            "duration_ms": round(duration_ms, 1),
        }
        line = json.dumps(rec, ensure_ascii=False)
        with self._lock, self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        return rec

    def by_trace(self, trace_id: str) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()
                    and json.loads(line).get("trace_id") == trace_id]
