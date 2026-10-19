# 测试/test_p3.py | 项目三：Java + Python 协作的业务 Agent
"""覆盖（16 个测试）：

单侧（respx 模拟 Java，无需真进程）：
  工具参数校验 / 权限拒绝（含审计 denied）/ 业务规则超 20% 改道（且不触达 Java）/
  幂等键稳定与 Header 传递 / Agent 低风险全流程 / 高风险 interrupt 载荷（不触达 Java）/
  高风险 reject（不触达 Java）/ 工具层协作式取消 / JavaClient 超时白名单重试。
集成（fixture 真编译并启动 java/PlanServer.java 子进程，随机端口）：
  契约测试（4 端点 + data/*.json 对拍 + 幂等重放）/ /slow 超时预算 /
  TaskStore 生命周期（提交→轮询→审批 approve）/ 审批 reject / 取消与终态 409 /
  FastAPI 端到端（202 提交→轮询 succeeded；审批/取消 HTTP 语义）。

运行：cd /workspace/ai_application_course && python3 -m pytest 测试/test_p3.py -q
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
import respx

ROOT = Path(__file__).resolve().parents[1]
P3 = ROOT / "综合项目" / "项目三_Java与Python协作Agent"
if str(P3) not in sys.path:
    sys.path.insert(0, str(P3))

from planagent.agent_core import (  # noqa: E402
    HIGH_RISK_TOOL,
    resume_analysis,
    run_analysis,
)
from planagent.audit import AuditLog  # noqa: E402
from planagent.task_store import TaskConflict, TaskStore  # noqa: E402
from planagent.tools_layer import (  # noqa: E402
    BusinessRuleError,
    JavaClient,
    JavaServiceError,
    Role,
    TaskCancelled,
    ToolContext,
    ToolPermissionError,
    ToolValidationError,
    build_tools,
    idempotency_key,
)

DEMO_DATE = "2026-03-18"
PLANS_OK = {"date": DEMO_DATE, "count": 2, "plans": [
    {"plan_id": "P-1001", "product": "减速器壳体", "qty": 500, "status": "正常"},
    {"plan_id": "P-1002", "product": "转向节", "qty": 1200, "status": "延期"},
]}
ADJ_OK = {"adjustment_id": "ADJ-9001", "plan_id": "P-1002", "new_qty": 1260,
          "status": "已受理"}


def _echo_adjustment(request: httpx.Request) -> httpx.Response:
    """模拟 Java 幂等账本行为：原样回显请求的 Idempotency-Key（首次 201，重放 200）。"""
    key = request.headers["Idempotency-Key"]
    return httpx.Response(201, json={**ADJ_OK, "idempotency_key": key})


def _ctx(base_url: str, tmp_path: Path, *, role: Role = Role.OPERATOR) -> ToolContext:
    return ToolContext(
        client=JavaClient(base_url), audit=AuditLog(tmp_path / "audit.jsonl"),
        task_id="task-test", trace_id="task-test", role=role)


# ---------------------------------------------------------------------------
# 单侧：工具治理（respx 模拟 Java）
# ---------------------------------------------------------------------------


def test_tool_args_validation_rejects_bad_inputs(tmp_path) -> None:
    with respx.mock:
        tools = {t.name: t for t in build_tools(_ctx("http://java", tmp_path))}
        with pytest.raises(ToolValidationError, match="date"):
            tools["query_plans"].invoke({"date": "2026/03/18"})          # 格式错
        with pytest.raises(ToolValidationError, match="workorder_id"):
            tools["query_workorder"].invoke({"workorder_id": "2091"})    # 缺 WO- 前缀
        with pytest.raises(ToolValidationError, match="reason"):
            tools["submit_adjustment"].invoke(
                {"plan_id": "P-1002", "new_qty": 1260, "reason": "", "date": DEMO_DATE})


def test_permission_denied_for_viewer_and_high_risk_gate(tmp_path) -> None:
    with respx.mock:
        audit = AuditLog(tmp_path / "audit.jsonl")
        ctx = ToolContext(client=JavaClient("http://java"), audit=audit,
                          task_id="t", trace_id="t", role=Role.VIEWER)
        tools = {t.name: t for t in build_tools(ctx)}
        with pytest.raises(ToolPermissionError, match="viewer"):
            tools["submit_adjustment"].invoke(
                {"plan_id": "P-1002", "new_qty": 1260, "reason": "客户加急订单",
                 "date": DEMO_DATE})
        denied = [r for r in audit.by_trace("t") if r["outcome"] == "denied"]
        assert denied and "无权" in denied[0]["detail"]      # 被拒也要留痕
        # 高风险工具走统一入口也会被闸门拦下（唯一合法入口是审批流恢复）
        with pytest.raises(ToolPermissionError, match="高风险"):
            tools[HIGH_RISK_TOOL].invoke(
                {"plan_id": "P-1002", "new_qty": 2400, "reason": "急单插单请翻倍"})


def test_business_rule_over_20pct_blocks_and_never_hits_java(tmp_path) -> None:
    with respx.mock:
        plans_route = respx.get("http://java/plans").mock(
            return_value=httpx.Response(200, json=PLANS_OK))
        adj_route = respx.post("http://java/adjustments").mock(
            return_value=httpx.Response(201, json=ADJ_OK))
        tools = {t.name: t for t in build_tools(_ctx("http://java", tmp_path))}
        with pytest.raises(BusinessRuleError, match="高风险"):
            tools["submit_adjustment"].invoke(
                {"plan_id": "P-1002", "new_qty": 2000,          # 1200→2000 = 67% 超限
                 "reason": "客户要求翻倍交付", "date": DEMO_DATE})
        assert plans_route.call_count == 1                      # 到 Java 核了现量
        assert adj_route.call_count == 0                        # 但没有提交（改道审批）


def test_idempotency_key_stable_and_sent_as_header(tmp_path) -> None:
    with respx.mock:
        respx.get("http://java/plans").mock(return_value=httpx.Response(200, json=PLANS_OK))
        route = respx.post("http://java/adjustments").mock(side_effect=_echo_adjustment)
        tools = {t.name: t for t in build_tools(_ctx("http://java", tmp_path))}
        args = {"plan_id": "P-1002", "new_qty": 1260, "reason": "延期恢复提量5%",
                "date": DEMO_DATE}
        r1 = tools["submit_adjustment"].invoke(dict(args))
        r2 = tools["submit_adjustment"].invoke(dict(args))
        assert r1["idempotency_key"] == r2["idempotency_key"]   # 同 trace 同操作 → 同 key
        assert route.call_count == 2
        for call in route.calls:
            assert call.request.headers["Idempotency-Key"] == r1["idempotency_key"]
        assert idempotency_key("P-1", 10, "r", "t1") == idempotency_key("P-1", 10, "r", "t1")
        assert idempotency_key("P-1", 10, "r", "t1") != idempotency_key("P-1", 10, "r", "t2")


def test_agent_low_risk_full_flow_submits_once(tmp_path) -> None:
    with respx.mock:
        respx.get("http://java/plans").mock(return_value=httpx.Response(200, json=PLANS_OK))
        adj_route = respx.post("http://java/adjustments").mock(
            return_value=httpx.Response(201, json=ADJ_OK))
        outcome = run_analysis(_ctx("http://java", tmp_path), _cp(), 
                               "分析 2026-03-18 的延期计划并提交恢复调整")
        assert outcome["status"] == "succeeded"
        assert "P-1002" in outcome["final"] and "ADJ-9001" in outcome["final"]
        assert adj_route.call_count == 1
        body = json.loads(adj_route.calls[0].request.content)
        assert body["new_qty"] == 1260                          # 1200 + 5% = 1260（规则模型剧本）


def _cp():
    from langgraph.checkpoint.memory import InMemorySaver

    return InMemorySaver()


def test_agent_high_risk_interrupts_with_reviewable_payload(tmp_path) -> None:
    with respx.mock:
        respx.get("http://java/plans").mock(return_value=httpx.Response(200, json=PLANS_OK))
        adj_route = respx.post("http://java/adjustments").mock(
            return_value=httpx.Response(201, json=ADJ_OK))
        outcome = run_analysis(_ctx("http://java", tmp_path), _cp(),
                               "紧急：把延期的计划翻倍处理")
        assert outcome["status"] == "waiting_approval"
        req = outcome["approval_request"]
        assert req["tool"] == HIGH_RISK_TOOL
        assert req["args"]["new_qty"] == 2400                   # 1200 × 2
        assert "翻倍" in req["args"]["reason"]
        assert adj_route.call_count == 0                        # 审批前绝不触达写接口


def test_agent_high_risk_reject_records_and_skips(tmp_path) -> None:
    with respx.mock:
        respx.get("http://java/plans").mock(return_value=httpx.Response(200, json=PLANS_OK))
        adj_route = respx.post("http://java/adjustments").mock(
            return_value=httpx.Response(201, json=ADJ_OK))
        ctx = _ctx("http://java", tmp_path)
        cp = _cp()  # ch48 铁律：run 与 resume 必须共享同一个 checkpointer
        outcome = run_analysis(ctx, cp, "紧急：把延期的计划翻倍处理")
        assert outcome["status"] == "waiting_approval"
        final = resume_analysis(ctx, cp, "task-test", "reject")
        assert "拒绝" in final["final"]
        assert adj_route.call_count == 0                        # 拒绝后不执行


def test_agent_high_risk_approve_executes_once(tmp_path) -> None:
    with respx.mock:
        respx.get("http://java/plans").mock(return_value=httpx.Response(200, json=PLANS_OK))
        adj_route = respx.post("http://java/adjustments").mock(
            return_value=httpx.Response(201, json=ADJ_OK))
        ctx = _ctx("http://java", tmp_path)
        cp = _cp()
        outcome = run_analysis(ctx, cp, "紧急：把延期的计划翻倍处理")
        assert outcome["status"] == "waiting_approval"
        final = resume_analysis(ctx, cp, "task-test", "approve")
        assert "调整单" in final["final"]
        assert adj_route.call_count == 1                        # 审批后恰好执行一次


def test_tool_layer_cooperative_cancel(tmp_path) -> None:
    """协作式取消：cancel_event 置位后，工具入口在检查点拒绝执行。"""
    ctx = _ctx("http://java", tmp_path)
    ctx.cancel_event.set()
    tools = {t.name: t for t in build_tools(ctx)}
    with pytest.raises(TaskCancelled):
        tools["query_plans"].invoke({"date": DEMO_DATE})


def test_java_client_retries_only_retryable_errors(tmp_path) -> None:
    """5xx 重试（白名单），4xx 业务错误不重试；重试耗尽抛最后一次异常。"""
    with respx.mock:
        r5xx = respx.get("http://java/plans").mock(return_value=httpx.Response(503))
        client = JavaClient("http://java", max_attempts=3, base_backoff_s=0.01)
        with pytest.raises(JavaServiceError):
            client.get_json("/plans", params={"date": DEMO_DATE})
        assert r5xx.call_count == 3                              # 有限次数

    with respx.mock:
        r404 = respx.get("http://java/plans").mock(return_value=httpx.Response(404))
        client = JavaClient("http://java", max_attempts=3, base_backoff_s=0.01)
        data = client.get_json("/plans", params={"date": DEMO_DATE})
        assert data == {"_not_found": True}                      # 404 是数据不是事故
        assert r404.call_count == 1                              # 零重试


# ---------------------------------------------------------------------------
# 集成：真编译并启动 Java 服务（模块级 fixture，随机端口）
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def java_base_url() -> str:
    """编译（如需）并启动 PlanServer（PLAN_PORT=0 → 内核分配端口），结束后关闭。"""
    import os
    import shutil

    out_dir = P3 / "java" / "out"
    if not (out_dir / "PlanServer.class").exists():
        subprocess.run(["javac", "-d", str(out_dir), str(P3 / "java" / "PlanServer.java")],
                       check=True, capture_output=True)
    java_bin = shutil.which("java")
    env = {**os.environ, "PLAN_PORT": "0"}   # 继承完整环境（mise/pyenv 的 java 路径）
    proc = subprocess.Popen([java_bin, "-cp", str(out_dir), "PlanServer"],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            env=env, text=True)
    line = proc.stdout.readline()  # "LISTENING port=N"
    assert line.startswith("LISTENING port="), line
    port = int(line.strip().split("=")[1])
    yield f"http://127.0.0.1:{port}"
    proc.terminate()
    proc.wait(timeout=5)


def test_java_contract_four_endpoints_and_data_files(java_base_url: str) -> None:
    """契约测试：Java 响应形状与 data/*.json 对拍（契约单一事实来源）。"""
    with httpx.Client(base_url=java_base_url, timeout=5.0) as c:
        health = c.get("/health")
        assert health.status_code == 200 and health.json()["status"] == "UP"

        plans = c.get("/plans", params={"date": DEMO_DATE})
        assert plans.status_code == 200
        body = plans.json()
        data_file = json.loads((P3 / "data" / "plans.json").read_text("utf-8"))
        expected = {(p["plan_id"], p["product"], p["qty"], p["status"])
                    for p in data_file["plans"] if data_file["plans"]}
        got = {(p["plan_id"], p["product"], p["qty"], p["status"]) for p in body["plans"]}
        assert expected <= got                                  # data/plans.json 全部在 Java 响应中
        assert set(body["plans"][0]) == {"plan_id", "product", "qty", "status"}

        wo = c.get("/workorders/WO-2091")
        assert wo.status_code == 200
        assert set(wo.json()) == {"workorder_id", "plan_id", "status",
                                  "produced_qty", "target_qty"}
        assert c.get("/workorders/WO-9999").status_code == 404
        assert c.get("/plans", params={"date": "bad-date"}).status_code == 400


def test_java_idempotency_replay_same_result(java_base_url: str) -> None:
    headers = {"Idempotency-Key": f"idem-pytest-{time.monotonic_ns()}"}
    body = {"plan_id": "P-1002", "new_qty": 1260, "reason": "pytest 幂等验证"}
    with httpx.Client(base_url=java_base_url, timeout=5.0) as c:
        first = c.post("/adjustments", headers=headers, json=body)
        replay = c.post("/adjustments", headers=headers, json=body)
        missing = c.post("/adjustments", json=body)
    assert first.status_code == 201 and replay.status_code == 200
    assert replay.json()["adjustment_id"] == first.json()["adjustment_id"]
    assert replay.json()["idempotent_replay"] is True
    assert missing.status_code == 400                            # 缺幂等键被拒


def test_java_slow_endpoint_timeout_budget(java_base_url: str) -> None:
    """对真 Java /slow：读超时 0.3s × 2 次尝试 → 有界的最坏耗时（不无限等）。"""
    client = JavaClient(java_base_url, connect_s=0.5, read_s=0.3,
                        max_attempts=2, base_backoff_s=0.01)
    t0 = time.monotonic()
    with pytest.raises(JavaServiceError):
        client.call_slow(2000)                                   # 端点要睡 2s
    assert time.monotonic() - t0 < 5.0                           # 上界可预算
    quick = JavaClient(java_base_url, read_s=2.0, max_attempts=1)
    assert quick.call_slow(50) == {"ok": True, "delayed_ms": 50}  # 快路径正常


def test_task_store_lifecycle_low_risk_succeeds(java_base_url: str, tmp_path) -> None:
    store = TaskStore(java_base_url=java_base_url, audit_path=str(tmp_path / "a.jsonl"))
    rec = store.submit("分析 2026-03-18 的延期计划并提交恢复调整")
    deadline = time.monotonic() + 10
    while rec.status not in {"succeeded", "failed"} and time.monotonic() < deadline:
        time.sleep(0.05)
    assert rec.status == "succeeded"
    assert "P-1002" in rec.result["final"]                       # 后台跑完 Agent 全流程
    audit = AuditLog(tmp_path / "a.jsonl")
    tools_seen = {r["tool"] for r in audit.by_trace(rec.task_id)}
    assert {"query_plans", "submit_adjustment"} <= tools_seen    # 全程留痕


def test_task_store_approval_reject_flow(java_base_url: str, tmp_path) -> None:
    store = TaskStore(java_base_url=java_base_url, audit_path=str(tmp_path / "a.jsonl"))
    rec = store.submit("紧急：把延期的计划翻倍处理")
    deadline = time.monotonic() + 10
    while rec.status != "waiting_approval" and time.monotonic() < deadline:
        time.sleep(0.05)
    assert rec.status == "waiting_approval"
    assert rec.approval_request["tool"] == HIGH_RISK_TOOL
    from planagent.task_store import TaskNotFound

    with pytest.raises(TaskNotFound):                            # 不存在的任务
        store.cancel("task-nope")
    decided = store.decide(rec.task_id, "reject", "李工")
    assert decided.status == "succeeded"
    assert "拒绝" in decided.result["final"]
    with pytest.raises(TaskConflict):                            # 已决定 → 再审 409
        store.decide(rec.task_id, "approve", "张工")


def test_task_store_cancel_waiting_approval(java_base_url: str, tmp_path) -> None:
    store = TaskStore(java_base_url=java_base_url, audit_path=str(tmp_path / "a.jsonl"))
    rec = store.submit("紧急：把延期的计划翻倍处理")
    deadline = time.monotonic() + 10
    while rec.status != "waiting_approval" and time.monotonic() < deadline:
        time.sleep(0.05)
    cancelled = store.cancel(rec.task_id)
    assert cancelled.status == "cancelled"
    with pytest.raises(TaskConflict):                            # 终态不可取消（409 语义）
        store.cancel(rec.task_id)
    with pytest.raises(TaskConflict):                            # 终态不可审批
        store.decide(rec.task_id, "approve", "张工")


def test_fastapi_end_to_end_analysis_poll_and_approval(java_base_url: str, tmp_path) -> None:
    """HTTP 层端到端：202 提交 → 轮询 → 审批 approve → 结果可见；404/409 语义。"""
    from fastapi.testclient import TestClient

    from planagent.main import create_app

    app = create_app(java_base_url=java_base_url,
                     audit_path=str(tmp_path / "e2e.jsonl"))
    client = TestClient(app)

    r = client.post("/analysis", json={"question": "分析 2026-03-18 的延期计划并提交恢复调整",
                                       "operator": "demo"})
    assert r.status_code == 202
    tid = r.json()["task_id"]
    assert r.json()["poll"] == f"/analysis/{tid}"

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        body = client.get(f"/analysis/{tid}").json()
        if body["status"] in {"succeeded", "failed"}:
            break
        time.sleep(0.05)
    assert body["status"] == "succeeded"
    assert "P-1002" in body["result"]["final"]

    assert client.get("/analysis/task-nope").status_code == 404  # 未知任务

    # 高风险两分支走 HTTP
    r = client.post("/analysis", json={"question": "紧急：把延期的计划翻倍处理"})
    tid2 = r.json()["task_id"]
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        body = client.get(f"/analysis/{tid2}").json()
        if body["status"] == "waiting_approval":
            break
        time.sleep(0.05)
    assert body["approval_request"]["tool"] == HIGH_RISK_TOOL
    ok = client.post(f"/analysis/{tid2}/approval",
                     json={"decision": "approve", "operator": "张工"})
    assert ok.status_code == 200 and ok.json()["status"] == "succeeded"
    late = client.post(f"/analysis/{tid2}/approval", json={"decision": "reject"})
    assert late.status_code == 409                               # 已决定再审批 → 409


def test_fastapi_cancel_and_bad_decision(java_base_url: str, tmp_path) -> None:
    from fastapi.testclient import TestClient

    from planagent.main import create_app

    app = create_app(java_base_url=java_base_url,
                     audit_path=str(tmp_path / "e2e2.jsonl"))
    client = TestClient(app)
    r = client.post("/analysis", json={"question": "紧急：把延期的计划翻倍处理"})
    tid = r.json()["task_id"]
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if client.get(f"/analysis/{tid}").json()["status"] == "waiting_approval":
            break
        time.sleep(0.05)
    assert client.delete(f"/analysis/{tid}").status_code == 202   # 取消受理
    assert client.get(f"/analysis/{tid}").json()["status"] == "cancelled"
    assert client.delete(f"/analysis/{tid}").status_code == 409   # 终态再取消
    bad = client.post(f"/analysis/{tid}/approval", json={"decision": "approve"})
    assert bad.status_code == 409                                 # 已取消不可审批
    bad2 = client.post("/analysis", json={"question": "紧急：把延期的计划翻倍处理"})
    tid2 = bad2.json()["task_id"]
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if client.get(f"/analysis/{tid2}").json()["status"] == "waiting_approval":
            break
        time.sleep(0.05)
    bad3 = client.post(f"/analysis/{tid2}/approval", json={"decision": "maybe"})
    assert bad3.status_code == 422                                # decision 白名单（Pydantic）
