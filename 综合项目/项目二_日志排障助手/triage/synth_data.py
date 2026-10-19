# 综合项目/项目二_日志排障助手/triage/synth_data.py
"""合成数据生成：3 类 Java 服务日志 + 服务状态 JSON 快照 + 运维清单 SQLite。

全部内容确定性生成（固定时间戳/trace_id），保证教材与测试可复现。
数据形态：
  日志行    ts|LEVEL|service|trace_id|message
  快照      {service: {status, p99_ms, error_rate, pod_restarts, updated_at}}
  SQLite    error_events / service_dependencies / recent_deployments 三张表
故障剧本（合成案例）：payment-service v2.31.0 发布后 OOM 反复重启，
下游 order-service 调用超时，gateway 报 502；db-task-runner 恰有一条脏数据告警。
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

# ---------------------------------------------------------------------------
# 1. 日志内容（正常样本 + 超时 + 连接失败 + 数据异常）
# ---------------------------------------------------------------------------

ORDER_SERVICE_LOG = """\
2026-10-19 08:58:01.101|INFO|order-service|trace-5000|Health check OK, 12 active orders
2026-10-19 09:00:10.512|ERROR|order-service|trace-5001|Call to payment-service timed out after 3000 ms
2026-10-19 09:01:33.019|ERROR|order-service|trace-5002|Call to payment-service timed out after 3000 ms
2026-10-19 09:02:02.444|WARN|order-service|trace-5003|Connection pool usage 95% (target payment-service)
2026-10-19 09:03:45.900|ERROR|order-service|trace-5004|Call to payment-service timed out after 3000 ms
2026-10-19 09:05:12.330|INFO|order-service|trace-5005|GET /orders/ORD-1001 200 12ms
2026-10-19 09:06:40.271|ERROR|order-service|trace-5006|Call to payment-service timed out after 3000 ms
2026-10-19 09:08:05.660|INFO|order-service|trace-5007|GET /orders/ORD-1002 200 9ms
"""

GATEWAY_LOG = """\
2026-10-19 09:00:11.002|INFO|gateway|trace-6000|GET /health 200 3ms
2026-10-19 09:00:12.880|ERROR|gateway|trace-6001|Connect to order-service failed: Connection refused
2026-10-19 09:02:15.431|ERROR|gateway|trace-6002|Upstream 502 from order-service
2026-10-19 09:04:00.019|ERROR|gateway|trace-6003|Connect to order-service failed: Connection refused
2026-10-19 09:07:22.150|INFO|gateway|trace-6004|GET /orders/ORD-2001 200 18ms
"""

DB_TASK_LOG = """\
2026-10-19 08:40:00.001|INFO|db-task-runner|trace-7000|Task BATCH-30 finished, 1024 rows
2026-10-19 09:09:41.780|ERROR|db-task-runner|trace-7001|Data anomaly: order ORD-9002 total_amount is null
2026-10-19 09:10:02.115|WARN|db-task-runner|trace-7002|Slow SQL: 4.8s SELECT * FROM payment_record WHERE created_at > ?
2026-10-19 09:12:20.503|INFO|db-task-runner|trace-7003|Task BATCH-31 finished, 1024 rows
"""

LOG_FILES: dict[str, str] = {
    "order_service.log": ORDER_SERVICE_LOG,
    "gateway_service.log": GATEWAY_LOG,
    "db_task_runner.log": DB_TASK_LOG,
}

# ---------------------------------------------------------------------------
# 2. 服务状态快照（只读 JSON）
# ---------------------------------------------------------------------------

SERVICE_STATUS: dict[str, dict] = {
    "order-service": {"status": "degraded", "p99_ms": 2430, "error_rate": 0.31,
                      "pod_restarts": 0, "updated_at": "2026-10-19T09:12:00+08:00"},
    "payment-service": {"status": "down", "p99_ms": None, "error_rate": 1.0,
                        "pod_restarts": 4, "updated_at": "2026-10-19T09:12:00+08:00"},
    "gateway": {"status": "healthy", "p99_ms": 21, "error_rate": 0.02,
                "pod_restarts": 0, "updated_at": "2026-10-19T09:12:00+08:00"},
    "db-task-runner": {"status": "healthy", "p99_ms": 4800, "error_rate": 0.01,
                       "pod_restarts": 0, "updated_at": "2026-10-19T09:12:00+08:00"},
}

# ---------------------------------------------------------------------------
# 3. 运维清单 SQLite（错误事件 / 依赖关系 / 发布记录）
# ---------------------------------------------------------------------------

ERROR_EVENTS: list[tuple[str, str, str, str, str]] = [
    ("2026-10-19 08:55:12.000", "payment-service", "ERROR", "trace-8001",
     "OutOfMemoryError: Java heap space (pod payment-7d9f)"),
    ("2026-10-19 08:59:03.100", "payment-service", "ERROR", "trace-8002",
     "Readiness probe failed, container restarting"),
    ("2026-10-19 09:00:40.512", "payment-service", "ERROR", "trace-8003",
     "OutOfMemoryError: Java heap space (pod payment-7d9f)"),
    ("2026-10-19 09:02:21.030", "payment-service", "ERROR", "trace-8004",
     "Readiness probe failed, container restarting"),
    ("2026-10-19 09:04:19.444", "order-service", "ERROR", "trace-8101",
     "PaymentClient invoke timeout, circuit breaker open"),
    ("2026-10-19 09:11:02.877", "db-task-runner", "ERROR", "trace-8201",
     "Data quality check failed: 1 row rejected"),
]

DEPENDENCIES: list[tuple[str, str, int]] = [
    ("order-service", "payment-service", 50),
    ("gateway", "order-service", 200),
    ("db-task-runner", "order-service", 10),
]

DEPLOYMENTS: list[tuple[str, str, str, str]] = [
    ("payment-service", "v2.31.0", "2026-10-19 08:52:00", "改动：堆参数与连接池配置调整"),
    ("order-service", "v1.9.3", "2026-10-17 21:30:00", "例行小版本，无相关改动"),
]


def build_all(data_dir: Path) -> None:
    """生成全部合成数据文件（幂等：重复运行覆盖为同一内容）。"""
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    for name, content in LOG_FILES.items():
        (data_dir / name).write_text(content, encoding="utf-8")

    (data_dir / "service_status.json").write_text(
        json.dumps(SERVICE_STATUS, ensure_ascii=False, indent=2), encoding="utf-8")

    db_path = data_dir / "ops_inventory.sqlite"
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE error_events (
                ts TEXT NOT NULL, service TEXT NOT NULL, level TEXT NOT NULL,
                trace_id TEXT NOT NULL, message TEXT NOT NULL);
            CREATE TABLE service_dependencies (
                service TEXT NOT NULL, depends_on TEXT NOT NULL, pool_max INTEGER NOT NULL);
            CREATE TABLE recent_deployments (
                service TEXT NOT NULL, version TEXT NOT NULL,
                deployed_at TEXT NOT NULL, note TEXT NOT NULL);
            """
        )
        conn.executemany("INSERT INTO error_events VALUES (?,?,?,?,?)", ERROR_EVENTS)
        conn.executemany("INSERT INTO service_dependencies VALUES (?,?,?)", DEPENDENCIES)
        conn.executemany("INSERT INTO recent_deployments VALUES (?,?,?,?)", DEPLOYMENTS)
        conn.commit()
    finally:
        conn.close()


def build_empty_log(data_dir: Path, name: str = "empty.log") -> Path:
    """生成一个空日志文件（边界用例）。"""
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    p = data_dir / name
    p.write_text("", encoding="utf-8")
    return p
