# tests/test_p2.py | 项目二：生产日志与接口故障排障助手
"""覆盖（12 个测试）：正常路径 / 证据不足拒答 / 空日志 / 工具白名单（工具名、参数名、参数值）/
只读连接拒绝写入 / 人工拒绝不执行 / 恢复后状态一致 / 审计 JSONL / recursion_limit /
thread 隔离 / 幂等（重放恢复不重复执行副作用）。

运行：cd /workspace/ai_application_course && python3 -m pytest tests/test_p2.py -q
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import GraphRecursionError
from langgraph.types import Command

P2_ROOT = Path(__file__).resolve().parents[1] / "projects" / "p2_log_triage"
if str(P2_ROOT) not in sys.path:
    sys.path.insert(0, str(P2_ROOT))

from triage.audit import AuditLog                       # noqa: E402
from triage.config import TriageConfig                  # noqa: E402
from triage.graph import resume_triage, run_triage      # noqa: E402
from triage.synth_data import build_all, build_empty_log  # noqa: E402
from triage.tools_readonly import (                     # noqa: E402
    ActionLedger,
    ToolWhitelistError,
    connect_readonly,
    restart_service,
    validate_args,
)

SOURCES = ["order_service.log", "gateway_service.log", "db_task_runner.log"]


def _make_cfg(tmp_path: Path) -> TriageConfig:
    """每测试独立的数据/审计目录：先重建合成数据（确定性）。"""
    cfg = TriageConfig(data_dir=tmp_path / "data",
                       audit_path=tmp_path / "audit.jsonl",
                       ledger_path=tmp_path / "ledger.jsonl")
    cfg.ensure_dirs()
    build_all(cfg.data_dir)
    return cfg


def _run(incident_id: str, sources: list[str], cfg: TriageConfig, audit: AuditLog):
    """统一入口：审批/恢复要求 checkpointer（进程内场景用 InMemorySaver）。"""
    return run_triage(incident_id, sources, cfg, audit, checkpointer=InMemorySaver())


# ---------------------------------------------------------------------------
# 1. 正常路径：三类日志 → P1 结论 + 审批后执行
# ---------------------------------------------------------------------------


def test_normal_path_concludes_p1_and_executes_after_approval(tmp_path) -> None:
    cfg = _make_cfg(tmp_path)
    audit = AuditLog(cfg.audit_path)
    run = _run("t-normal", SOURCES, cfg, audit)
    assert run.interrupted                      # 高风险动作 → 人工审批暂停
    assert run.app.get_state(run.config).next == ("approval",)

    final = resume_triage(run, True)
    c = final.conclusion
    assert c["level"] == "P1"
    assert c["verdict"].startswith("order-service 受 payment-service")
    assert len(c["corroborations"]) == 3
    assert c["gaps"] == []
    assert c["actions_taken"][0]["status"] == "executed"
    assert ActionLedger(cfg.ledger_path).has("restart_service:payment-service:t-normal")


# ---------------------------------------------------------------------------
# 2. 证据不足拒答（含缺口清单）
# ---------------------------------------------------------------------------


def test_evidence_insufficient_refuses_with_gaps(tmp_path) -> None:
    cfg = _make_cfg(tmp_path)
    # 数据库里"干净"的依赖：billing-service 不在快照/错误事件/依赖表中 → 印证不足
    log = cfg.data_dir / "billing_only.log"
    log.write_text(
        "2026-10-19 10:00:00.000|ERROR|order-service|trace-9901|"
        "Call to billing-service timed out after 3000 ms\n",
        encoding="utf-8")
    audit = AuditLog(cfg.audit_path)
    run = _run("t-insufficient", ["billing_only.log"], cfg, audit)
    assert not run.interrupted                  # 没有高风险动作（证据不足不会提议重启）
    c = run.conclusion
    assert c["level"] == "UNKNOWN"
    assert c["verdict"] == "证据不足，无法下结论"
    assert any("billing-service" in g for g in c["gaps"])
    assert c["actions_taken"] == []


def test_empty_log_produces_unknown(tmp_path) -> None:
    cfg = _make_cfg(tmp_path)
    build_empty_log(cfg.data_dir)
    audit = AuditLog(cfg.audit_path)
    run = _run("t-empty", ["empty.log"], cfg, audit)
    c = run.conclusion
    assert c["level"] == "UNKNOWN"
    assert "无告警可取证" in c["gaps"][0]


def test_missing_source_file_is_recorded_not_fatal(tmp_path) -> None:
    cfg = _make_cfg(tmp_path)
    audit = AuditLog(cfg.audit_path)
    run = _run("t-missing", ["no_such_file.log"], cfg, audit)
    assert any(a["type"] == "missing_source" for a in run.result["alerts"])
    assert run.conclusion["level"] == "UNKNOWN"


# ---------------------------------------------------------------------------
# 3. 工具白名单：未知工具 / 未知参数 / 非法参数值
# ---------------------------------------------------------------------------


def test_whitelist_rejects_unknown_tool_and_param(tmp_path) -> None:
    with pytest.raises(ToolWhitelistError, match="未知工具"):
        validate_args("drop_table", {"service": "payment-service"})
    with pytest.raises(ToolWhitelistError, match="不接受参数"):
        validate_args("query_error_records",
                      {"service": "payment-service", "raw_sql": "DROP TABLE x"})


def test_whitelist_rejects_bad_values(tmp_path) -> None:
    # SQL 注入形态的服务名（含分号/空格/大写）必须被值规则拦下
    for bad in ("payment-service; DROP TABLE error_events", "Payment", "", "a" * 50):
        with pytest.raises(ToolWhitelistError):
            validate_args("query_error_records", {"service": bad})
    with pytest.raises(ToolWhitelistError):
        validate_args("query_error_records", {"service": "order-service", "limit": 999})


def test_sqlite_connection_is_readonly(tmp_path) -> None:
    cfg = _make_cfg(tmp_path)
    conn = connect_readonly(cfg.data_dir / "ops_inventory.sqlite")
    try:
        rows = conn.execute("SELECT COUNT(*) FROM error_events").fetchone()
        assert rows[0] >= 5
        with pytest.raises(Exception) as ei:    # 只读连接写不进去（query_only）
            conn.execute("INSERT INTO error_events VALUES ('x','x','x','x','x')")
        assert "readonly" in str(ei.value).lower() or "read-only" in str(ei.value).lower()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 4. 人工审批：拒绝不执行 / 恢复后状态一致
# ---------------------------------------------------------------------------


def test_human_rejection_blocks_side_effect(tmp_path) -> None:
    cfg = _make_cfg(tmp_path)
    audit = AuditLog(cfg.audit_path)
    run = _run("t-reject", SOURCES, cfg, audit)
    final = resume_triage(run, False)
    c = final.conclusion
    assert c["level"] == "P1"                           # 拒绝动作 ≠ 结论作废
    assert c["actions_taken"][0]["status"] == "skipped_unapproved"
    assert not ActionLedger(cfg.ledger_path).has("restart_service:payment-service:t-reject")
    # 审计里必须有审批留痕（决策=False）
    approval_events = audit.find("approval.restart_service")
    assert approval_events and approval_events[0]["args"]["decision"] is False


def test_resume_state_consistent_with_prior_snapshot(tmp_path) -> None:
    cfg = _make_cfg(tmp_path)
    audit = AuditLog(cfg.audit_path)
    run = _run("t-consistent", SOURCES, cfg, audit)
    # 暂停时的快照：假设已生成，结论未产出
    snap = run.app.get_state(run.config)
    assert snap.next == ("approval",)
    assert snap.values["hypothesis"]["suspected_dependency"] == "payment-service"
    assert snap.values.get("conclusion", {}) == {}

    final = resume_triage(run, True)
    assert final.conclusion["level"] == "P1"
    # 恢复没有破坏中断前的事实：假设与告警保持一致
    snap2 = final.app.get_state(final.config)
    assert snap2.values["hypothesis"] == snap.values["hypothesis"]
    assert len(snap2.values["alerts"]) == len(snap.values["alerts"])
    assert snap2.next == ()


# ---------------------------------------------------------------------------
# 5. 审计日志
# ---------------------------------------------------------------------------


def test_audit_jsonl_records_who_when_what_args_result(tmp_path) -> None:
    cfg = _make_cfg(tmp_path)
    audit = AuditLog(cfg.audit_path, operator="oncall-zhang")
    run = _run("t-audit", SOURCES, cfg, audit)
    resume_triage(run, True)

    events = AuditLog(cfg.audit_path).read_all()
    assert events, "审计文件应有事件"
    required = {"ts", "who", "thread_id", "what", "args", "result_summary", "status"}
    assert all(required <= set(e) for e in events)
    assert all(e["who"] == "oncall-zhang" for e in events)
    tool_events = [e for e in events if e["what"] == "query_error_records"]
    assert tool_events and "payment-service" in json.dumps(tool_events[0]["args"])
    assert any(e["what"] == "approval.restart_service" for e in events)


# ---------------------------------------------------------------------------
# 6. 递归限制 / thread 隔离 / 幂等
# ---------------------------------------------------------------------------


def test_recursion_limit_triggers_graph_recursion_error(tmp_path) -> None:
    cfg = _make_cfg(tmp_path)
    audit = AuditLog(cfg.audit_path)
    app = _run("t-recur", SOURCES, cfg, audit).app  # 复用编译好的图
    with pytest.raises(GraphRecursionError):
        app.invoke({"incident": {"thread_id": "t-recur2", "sources": list(SOURCES)},
                    "records": [], "alerts": [], "queries": [], "evidence": [],
                    "hypothesis": {}, "assessment": {}, "conclusion": {},
                    "executed_actions": []},
                   {"configurable": {"thread_id": "t-recur2"}, "recursion_limit": 3})


def test_concurrent_thread_ids_are_isolated(tmp_path) -> None:
    cfg = _make_cfg(tmp_path)
    audit = AuditLog(cfg.audit_path)
    # A：完整故障 → P1；B：空日志 → UNKNOWN；两者互不污染
    build_empty_log(cfg.data_dir)
    run_a = _run("inc-A", SOURCES, cfg, audit)
    final_a = resume_triage(run_a, True)
    run_b = _run("inc-B", ["empty.log"], cfg, audit)

    assert final_a.conclusion["level"] == "P1"
    assert run_b.conclusion["level"] == "UNKNOWN"
    assert run_b.conclusion["hypothesis"]["primary_service"] == "unknown"
    snap_a = final_a.app.get_state(final_a.config)
    assert snap_a.values["hypothesis"]["suspected_dependency"] == "payment-service"
    assert snap_a.values["incident"]["thread_id"] == "inc-A"


def test_replayed_resume_does_not_repeat_side_effect(tmp_path) -> None:
    """幂等：批准执行成功后，从暂停检查点重放恢复 → 账本命中，不重复重启。"""
    cfg = _make_cfg(tmp_path)
    audit = AuditLog(cfg.audit_path)
    run = _run("t-idem", SOURCES, cfg, audit)
    final = resume_triage(run, True)
    assert final.conclusion["actions_taken"][0]["status"] == "executed"

    # 回到 next=('approval',) 的历史检查点，再次 Command(resume=True)
    cp = next(h for h in final.app.get_state_history(final.config)
              if h.next == ("approval",))
    old_cfg = {"configurable": {"thread_id": "t-idem",
                                "checkpoint_id": cp.config["configurable"]["checkpoint_id"]}}
    r2 = final.app.invoke(Command(resume=True), old_cfg)
    statuses = [a["status"] for a in r2["executed_actions"]]
    assert statuses == ["already_done"]                 # 重放命中账本
    ledger_rows = ActionLedger(cfg.ledger_path).read_all()
    assert len([x for x in ledger_rows if x.get("status") == "executed"]) == 1


def test_restart_service_tool_is_idempotent_directly(tmp_path) -> None:
    """工具级幂等：同一 action_key 二次调用返回 already_done。"""
    ledger = ActionLedger(tmp_path / "ledger.jsonl")
    k = "restart_service:payment-service:case"
    assert restart_service(service="payment-service", action_key=k,
                           ledger=ledger, approved=True)["status"] == "executed"
    assert restart_service(service="payment-service", action_key=k,
                           ledger=ledger, approved=True)["status"] == "already_done"
    assert restart_service(service="payment-service", action_key="other-key",
                           ledger=ledger, approved=False)["status"] == "skipped_unapproved"
    assert len([x for x in ledger.read_all() if x.get("status") == "executed"]) == 1
