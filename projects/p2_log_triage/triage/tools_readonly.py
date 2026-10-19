# projects/p2_log_triage/triage/tools_readonly.py
"""受限只读工具 + 唯一的高风险副作用工具（须人工审批 + 幂等账本）。

安全设计（对应 syllabus ch58"只读账户+白名单+参数化 SQL"）：
  1. 查"数据库"：SQLite 只读连接——URI file:...?mode=ro + PRAGMA query_only=ON 双保险；
  2. 查"服务状态"：只读 JSON 快照；
  3. 工具入参白名单：工具名、参数名、参数值三道校验，越界即抛 ToolWhitelistError；
  4. SQL 一律参数化（? 占位），不拼接字符串；
  5. restart_service 是唯一副作用工具：审批通过才能调用，且按 action_key 幂等
     （账本 JSONL 先查后写，等价于数据库唯一索引 + 插入冲突即跳过）。
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# 白名单定义：工具名 → {参数名 → 值规则}
# ---------------------------------------------------------------------------

_SERVICE_RE = re.compile(r"^[a-z][a-z0-9-]{1,40}$")
_LEVEL_RE = re.compile(r"^(ERROR|WARN|INFO)$")

QUERY_ERROR_RECORDS = "query_error_records"
QUERY_SERVICE_STATUS = "query_service_status"
QUERY_DEPENDENCY = "query_dependency"
RESTART_SERVICE = "restart_service"

TOOL_WHITELIST: dict[str, dict[str, Any]] = {
    QUERY_ERROR_RECORDS: {
        "params": {"service": _SERVICE_RE, "level": _LEVEL_RE, "limit": (1, 50)},
        "required": ["service"],
        "risk": "read_only",
        "desc": "查询数据库 error_events 表（只读连接，参数化 SQL）",
    },
    QUERY_SERVICE_STATUS: {
        "params": {"service": _SERVICE_RE},
        "required": ["service"],
        "risk": "read_only",
        "desc": "查询服务状态 JSON 快照（只读）",
    },
    QUERY_DEPENDENCY: {
        "params": {"service": _SERVICE_RE},
        "required": ["service"],
        "risk": "read_only",
        "desc": "查询服务依赖关系（只读）",
    },
    RESTART_SERVICE: {
        "params": {"service": _SERVICE_RE},
        "required": ["service"],
        "risk": "high",
        "desc": "重启服务（高风险副作用：须人工审批 + 幂等账本）",
    },
}


class ToolWhitelistError(ValueError):
    """工具名/参数名/参数值不在白名单内。"""


def validate_args(tool: str, args: dict[str, Any]) -> dict[str, Any]:
    """三道校验：工具在册 → 参数名在册 → 参数值合规。返回清洗后的参数。"""
    if tool not in TOOL_WHITELIST:
        raise ToolWhitelistError(f"未知工具：{tool!r}，白名单：{sorted(TOOL_WHITELIST)}")
    spec = TOOL_WHITELIST[tool]
    for name in spec["required"]:
        if name not in args:
            raise ToolWhitelistError(f"工具 {tool} 缺少必填参数：{name}")
    cleaned: dict[str, Any] = {}
    for name, value in args.items():
        if name not in spec["params"]:
            raise ToolWhitelistError(
                f"工具 {tool} 不接受参数 {name!r}（白名单：{sorted(spec['params'])}）")
        rule = spec["params"][name]
        if isinstance(rule, tuple):                      # (min, max) 数值区间
            if not isinstance(value, int) or isinstance(value, bool) or not (rule[0] <= value <= rule[1]):
                raise ToolWhitelistError(f"参数 {name}={value!r} 超出区间 {rule}")
        elif not isinstance(value, str) or not rule.match(value):
            raise ToolWhitelistError(f"参数 {name}={value!r} 不匹配规则 {rule.pattern}")
        cleaned[name] = value
    return cleaned


def describe_tools() -> str:
    """给模型/人看的能力清单（真实系统里即 tools 的 schema 描述）。"""
    return "\n".join(f"- {t}: {s['desc']} [risk={s['risk']}]" for t, s in TOOL_WHITELIST.items())


# ---------------------------------------------------------------------------
# 只读数据源
# ---------------------------------------------------------------------------


def connect_readonly(db_path: Path) -> sqlite3.Connection:
    """SQLite 只读连接：URI mode=ro（文件不存在直接失败）+ query_only 双保险。"""
    uri = f"file:{Path(db_path).resolve()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.execute("PRAGMA query_only = ON")
    return conn


def query_error_records(db_path: Path, *, service: str, level: str = "ERROR",
                        limit: int = 10) -> list[dict[str, Any]]:
    """参数化 SQL 查询错误事件（只读）。"""
    conn = connect_readonly(db_path)
    try:
        rows = conn.execute(
            "SELECT ts, service, level, trace_id, message FROM error_events "
            "WHERE service = ? AND level = ? ORDER BY ts DESC LIMIT ?",
            (service, level, int(limit)),
        ).fetchall()
    finally:
        conn.close()
    return [{"ts": r[0], "service": r[1], "level": r[2], "trace_id": r[3], "message": r[4]}
            for r in rows]


def query_service_status(snapshot_path: Path, *, service: str) -> dict[str, Any]:
    """只读 JSON 快照：返回某服务状态；不在快照里返回 status=unknown。"""
    data = json.loads(Path(snapshot_path).read_text(encoding="utf-8"))
    return data.get(service) or {"service": service, "status": "unknown"}


def query_dependency(db_path: Path, *, service: str) -> list[dict[str, Any]]:
    """只读查询依赖关系：谁依赖它（上游）+ 它依赖谁（下游）。"""
    conn = connect_readonly(db_path)
    try:
        upstream = conn.execute(
            "SELECT service, depends_on, pool_max FROM service_dependencies WHERE depends_on = ?",
            (service,),
        ).fetchall()
        downstream = conn.execute(
            "SELECT service, depends_on, pool_max FROM service_dependencies WHERE service = ?",
            (service,),
        ).fetchall()
    finally:
        conn.close()
    return [{"direction": "upstream", "service": r[0], "depends_on": r[1], "pool_max": r[2]}
            for r in upstream] + \
           [{"direction": "downstream", "service": r[0], "depends_on": r[1], "pool_max": r[2]}
            for r in downstream]


# ---------------------------------------------------------------------------
# 副作用工具（高风险）：幂等账本
# ---------------------------------------------------------------------------


class ActionLedger:
    """副作用账本（JSONL 追加）：同一 action_key 只允许一条 executed 记录。

    恢复语义的关键：图检查点不保证跨系统副作用"恰好一次"；账本承担
    "at-most-once" 兜底——执行前先查账，命中即跳过（幂等消费的常见实现）。
    """

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def has(self, action_key: str) -> bool:
        return any(r.get("action_key") == action_key and r.get("status") == "executed"
                   for r in self.read_all())

    def record(self, action_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        row = {"action_key": action_key, **payload}
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row

    def read_all(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        return [json.loads(x) for x in
                self._path.read_text(encoding="utf-8").splitlines() if x.strip()]


def restart_service(*, service: str, action_key: str, ledger: ActionLedger,
                    approved: bool) -> dict[str, Any]:
    """重启服务（副作用）：账本幂等 + 必须显式 approved=True。

    返回 status: executed / skipped_unapproved / already_done（幂等命中）。
    """
    cleaned = validate_args(RESTART_SERVICE, {"service": service})
    if not approved:
        return {"action": RESTART_SERVICE, "service": cleaned["service"],
                "status": "skipped_unapproved"}
    if ledger.has(action_key):
        return {"action": RESTART_SERVICE, "service": cleaned["service"],
                "status": "already_done", "action_key": action_key}
    # —— 副作用本体：生产里是调用运维 API；沙箱里只写账本（可观察、可恢复）——
    ledger.record(action_key, {"action": RESTART_SERVICE, "service": cleaned["service"],
                               "status": "executed", "detail": "simulated restart (sandbox)"})
    return {"action": RESTART_SERVICE, "service": cleaned["service"],
            "status": "executed", "action_key": action_key}
