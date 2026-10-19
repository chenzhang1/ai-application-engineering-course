# tests/test_ch56.py | 第 56 章：对接已有 Java 服务（契约 / 幂等 / 长任务 / 超时重试）
"""覆盖（7 个测试）：替身服务与 Java 服务的契约形状、Idempotency-Key 幂等重放、
长任务状态机（提交/轮询/取消/终态 409）、HTTP 工具封装的业务 404 与基础设施错误、
超时重试预算（慢端点最坏耗时有上界）。

运行：cd /workspace/ai_application_course && python3 -m pytest tests/test_ch56.py -q
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples" / "ch56_java_bridge"))

from stub_java_service import StubJavaService  # noqa: E402


@pytest.fixture()
def base_url() -> str:
    """每个测试独立的替身服务（随机端口 + 干净的幂等账本/任务表）。"""
    svc = StubJavaService()
    url = svc.start()
    yield url
    svc.stop()


def _client(base_url: str) -> httpx.Client:
    return httpx.Client(base_url=base_url,
                        timeout=httpx.Timeout(connect=1.0, read=1.0, write=1.0, pool=1.0))


# ---------------------------------------------------------------------------
# 1. 契约：响应形状与 PlanServer.java 一致（项目三契约测试的替身版）
# ---------------------------------------------------------------------------


def test_plans_contract_shape(base_url: str) -> None:
    with _client(base_url) as c:
        r = c.get("/plans", params={"date": "2026-03-18"})
    assert r.status_code == 200
    body = r.json()
    assert body["date"] == "2026-03-18" and body["count"] == 2
    plan = body["plans"][0]
    assert set(plan) == {"plan_id", "product", "qty", "status"}


def test_workorder_404_is_business_data(base_url: str) -> None:
    with _client(base_url) as c:
        ok = c.get("/workorders/WO-2091")
        miss = c.get("/workorders/WO-9999")
    assert ok.status_code == 200
    assert set(ok.json()) == {"workorder_id", "plan_id", "status", "produced_qty", "target_qty"}
    assert miss.status_code == 404 and miss.json()["error"] == "workorder_not_found"


# ---------------------------------------------------------------------------
# 2. 幂等：同 key 重放 → 同结果 + 幂等标识
# ---------------------------------------------------------------------------


def test_idempotency_key_replay_returns_same_result(base_url: str) -> None:
    headers = {"Idempotency-Key": "idem-test-001"}
    body = {"plan_id": "P-1002", "new_qty": 1250, "reason": "客户加急（测试）"}
    with _client(base_url) as c:
        first = c.post("/adjustments", headers=headers, json=body)
        replay = c.post("/adjustments", headers=headers, json=body)
        other = c.post("/adjustments", headers={"Idempotency-Key": "idem-test-002"},
                       json=body)
    assert first.status_code == 201 and replay.status_code == 200
    assert replay.json()["adjustment_id"] == first.json()["adjustment_id"]
    assert replay.json()["idempotent_replay"] is True       # 幂等命中标识
    assert other.json()["adjustment_id"] != first.json()["adjustment_id"]
    with _client(base_url) as c:                            # 缺 key → 400（写操作强制幂等）
        assert c.post("/adjustments", json=body).status_code == 400


# ---------------------------------------------------------------------------
# 3. 长任务状态机
# ---------------------------------------------------------------------------


def test_long_task_lifecycle_submit_wait(base_url: str) -> None:
    with _client(base_url) as c:
        r = c.post("/tasks", json={"duration_s": 0.3})
        assert r.status_code == 202                          # 202 Accepted：受理即返回
        task_id = r.json()["task_id"]
        for _ in range(50):                                  # 轮询带上限
            snap = c.get(f"/tasks/{task_id}").json()
            if snap["status"] == "succeeded":
                break
            time.sleep(0.05)
        assert snap["status"] == "succeeded"
        assert snap["result"] == {"summary": "分析完成：P-1002 延期风险中"}


def test_long_task_cancel_and_conflict(base_url: str) -> None:
    with _client(base_url) as c:
        task_id = c.post("/tasks", json={"duration_s": 5.0}).json()["task_id"]
        cancelled = c.delete(f"/tasks/{task_id}")
        assert cancelled.status_code == 202
        assert cancelled.json()["status"] == "cancelled"
        assert c.get(f"/tasks/{task_id}").json()["status"] == "cancelled"
        assert c.delete(f"/tasks/{task_id}").status_code == 409   # 已终态不可再取消
        assert c.get("/tasks/TASK-nope").status_code == 404


# ---------------------------------------------------------------------------
# 4. HTTP 工具封装（EX-56-01 的错误翻译三层）
# ---------------------------------------------------------------------------


def test_tool_wrapper_translates_404_and_infra_error(base_url: str) -> None:
    from ex_56_01_http_tool_wrapper import JavaServiceError, ToolHTTPClient, init_tools, tool_query_workorder

    init_tools(base_url)
    hit = tool_query_workorder("WO-2091")
    assert hit["exists"] is True and hit["plan_id"] == "P-1002"
    miss = tool_query_workorder("WO-9999")
    assert miss["exists"] is False and "核对工单号" in miss["hint"]   # 业务 404 是数据


def test_tool_wrapper_infra_error_raises_service_error(base_url: str) -> None:
    from ex_56_01_http_tool_wrapper import JavaServiceError, ToolHTTPClient, init_tools, tool_query_plans

    init_tools(base_url)
    dead = "http://127.0.0.1:9"   # 端口 9（discard）：连接必失败 → 基础设施错误
    c = ToolHTTPClient(dead)
    c._client = httpx.Client(base_url=dead,
                             timeout=httpx.Timeout(connect=0.2, read=0.2, write=0.2, pool=0.2))
    import ex_56_01_http_tool_wrapper as m
    old, m._CLIENT = m._CLIENT, c
    try:
        with pytest.raises(JavaServiceError):
            tool_query_plans("2026-03-18")
    finally:
        m._CLIENT = old


# ---------------------------------------------------------------------------
# 5. 超时重试预算（EX-56-03 的语义）
# ---------------------------------------------------------------------------


def test_timeout_retry_has_bounded_worst_case(base_url: str) -> None:
    from ex_56_03_timeout_retry_semantics import call_with_retry

    client = httpx.Client(base_url=base_url,
                          timeout=httpx.Timeout(connect=0.5, read=0.2, write=0.5, pool=0.5))
    t0 = time.monotonic()
    with pytest.raises(httpx.TimeoutException):
        call_with_retry(client, "GET", "/slow?ms=1200", max_attempts=3, base_backoff_s=0.05)
    elapsed = time.monotonic() - t0
    assert elapsed < 5.0   # 最坏情况有确定上界（3×0.2s 超时 + 退避），而非无限等


def test_retry_success_after_transient(base_url: str) -> None:
    """快端点一次成功：零重试开销（重试预算只花在真故障上）。"""
    from ex_56_03_timeout_retry_semantics import call_with_retry

    client = httpx.Client(base_url=base_url,
                          timeout=httpx.Timeout(connect=1.0, read=1.0, write=1.0, pool=1.0))
    r = call_with_retry(client, "GET", "/slow?ms=30")
    assert r == {"ok": True, "delayed_ms": 30}
