# projects/p2_log_triage/triage/audit.py
"""JSONL 审计日志：who / when / what / args / result 摘要，一行一条。

生产对照：对应 Java 侧的操作审计表（actor + action + params_digest + outcome）。
工具调用、白名单拒绝、人工审批结果都必须留痕——排障助手只读为主，
但每一次"它看过什么、想做什么、被谁允许"都要可追溯。
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AuditLog:
    """线程安全的 JSONL 追加写。"""

    def __init__(self, path: Path, operator: str = "triage-bot") -> None:
        self._path = Path(path)
        self._operator = operator
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, what: str, *, thread_id: str = "", args: dict[str, Any] | None = None,
               result_summary: str = "", status: str = "ok") -> dict[str, Any]:
        """写一条审计事件并返回事件本身（便于测试与状态记录复用）。"""
        event: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "who": self._operator,
            "thread_id": thread_id,
            "what": what,
            "args": args or {},
            "result_summary": result_summary[:200],
            "status": status,
        }
        line = json.dumps(event, ensure_ascii=False)
        with self._lock, self._path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        return event

    def read_all(self) -> list[dict[str, Any]]:
        """读回全部事件（测试与 resume 演示用）。"""
        if not self._path.exists():
            return []
        out: list[dict[str, Any]] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
        return out

    def find(self, what: str, status: str | None = None) -> list[dict[str, Any]]:
        """按 what（可再按 status 过滤）检索事件。"""
        return [e for e in self.read_all()
                if e["what"] == what and (status is None or e["status"] == status)]
