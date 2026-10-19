# 测试/test_ch54.py | 第 54 章：工具治理（描述质量 / 参数校验 / 权限分级 / 审计日志）
"""覆盖（7 个测试）：描述对照实验降低误选、参数校验三类拒绝、权限矩阵
（角色拒绝 + 高风险闸门 + 审批放行）、业务规则改道、审计 JSONL 全字段与 trace 检索。

运行：cd /workspace/ai_application_course && python3 -m pytest 测试/test_ch54.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from 示例代码.ch54_tool_governance.ex_54_01_description_quality import (  # noqa: E402
    REQUESTS,
    TOOLS_BAD,
    TOOLS_GOOD,
    run_experiment,
)
from 示例代码.ch54_tool_governance.ex_54_02_param_validation_permission import (  # noqa: E402
    AdjustmentArgs,
    BusinessRuleError,
    PermissionDenied,
    REGISTRY,
    Risk,
    Role,
    ToolEntry,
    execute_tool,
)
from 示例代码.ch54_tool_governance.ex_54_03_audit_log import (  # noqa: E402
    AuditLog,
    governed_execute,
)


# ---------------------------------------------------------------------------
# 1. 描述质量：只改描述，误选率下降
# ---------------------------------------------------------------------------


def test_structured_descriptions_reduce_mispicks() -> None:
    bad = run_experiment("A", TOOLS_BAD)
    good = run_experiment("B", TOOLS_GOOD)
    assert good.wrong < bad.wrong                  # 对照实验方向性成立
    assert good.wrong_cases                        # 保留诚实标注：B 仍有误选（教学边界）


def test_experiment_covers_all_requests() -> None:
    """边界完整性：8 个请求全部参与实验（防止样例悄悄缩水）。"""
    bad = run_experiment("A", TOOLS_BAD)
    assert bad.correct + bad.wrong == len(REQUESTS) == 8


# ---------------------------------------------------------------------------
# 2. 参数校验（Pydantic 拦在实现之前）
# ---------------------------------------------------------------------------


def test_args_schema_rejects_bad_plan_id() -> None:
    with pytest.raises(ValidationError) as ei:
        AdjustmentArgs.model_validate({"plan_id": "P1002", "new_qty": 1200,
                                       "reason": "客户加急订单"})
    assert "plan_id" in str(ei.value.errors()[0]["loc"])


def test_args_schema_rejects_missing_reason_and_bad_type() -> None:
    with pytest.raises(ValidationError):
        AdjustmentArgs.model_validate({"plan_id": "P-1002", "new_qty": "abc"})
    with pytest.raises(ValidationError):
        AdjustmentArgs.model_validate({"plan_id": "P-1002", "new_qty": 1200})  # 缺 reason


# ---------------------------------------------------------------------------
# 3. 权限分级 + 高风险闸门 + 业务规则
# ---------------------------------------------------------------------------


def test_viewer_cannot_submit_adjustment() -> None:
    with pytest.raises(PermissionDenied, match="viewer"):
        execute_tool(REGISTRY, "submit_adjustment", Role.VIEWER,
                     {"plan_id": "P-1002", "new_qty": 1100, "reason": "客户加急订单"})


def test_high_risk_tool_blocked_even_for_admin_without_approval() -> None:
    """高风险闸门：任何角色不能直调 restart_line；审批恢复（approved=True）才放行。"""
    with pytest.raises(PermissionDenied, match="高风险"):
        execute_tool(REGISTRY, "restart_line", Role.ADMIN, {"line_id": "L-3"})
    ok = execute_tool(REGISTRY, "restart_line", Role.ADMIN, {"line_id": "L-3"},
                      approved=True)
    assert ok == {"restarted": "L-3"}


def test_business_rule_diverts_over_20_percent_to_approval() -> None:
    with pytest.raises(BusinessRuleError, match="高风险"):
        execute_tool(REGISTRY, "submit_adjustment", Role.OPERATOR,
                     {"plan_id": "P-1002", "new_qty": 2000, "reason": "客户要求翻倍交付"})
    ok = execute_tool(REGISTRY, "submit_adjustment", Role.OPERATOR,
                      {"plan_id": "P-1002", "new_qty": 1150, "reason": "客户加急订单5%内"})
    assert ok["accepted"] is True
    assert ok["idempotency_key"].startswith("adj:P-1002:1150:")
    with pytest.raises(KeyError):   # 未知工具
        execute_tool(REGISTRY, "nope", Role.ADMIN, {})
    assert REGISTRY["query_plan"].risk is Risk.READ  # 定级表是数据，可被审计脚本复核


# ---------------------------------------------------------------------------
# 4. 审计日志：denied 也留痕、trace_id 可检索、字段齐全
# ---------------------------------------------------------------------------


def test_audit_log_records_denied_and_ok(tmp_path) -> None:
    audit = AuditLog(tmp_path / "audit" / "tools.jsonl")
    governed_execute(audit, "trace-x", "agent-p3", "viewer", "submit_adjustment",
                     {"plan_id": "P-1002"}, allowed=False)
    governed_execute(audit, "trace-x", "agent-p3", "operator", "query_plan",
                     {"plan_id": "P-1002"}, allowed=True)
    records = audit.by_trace("trace-x")
    assert [r["outcome"] for r in records] == ["denied", "ok"]
    for r in records:  # 五个 W 字段齐全
        assert {"ts", "trace_id", "actor", "role", "tool", "args",
                "outcome", "detail", "duration_ms"} <= set(r)
    assert records[0]["detail"].startswith("角色 viewer 无权")


def test_audit_by_trace_filters_other_sessions(tmp_path) -> None:
    audit = AuditLog(tmp_path / "audit.jsonl")
    governed_execute(audit, "trace-1", "a", "operator", "query_plan", {}, allowed=True)
    governed_execute(audit, "trace-2", "a", "operator", "query_plan", {}, allowed=True)
    assert len(audit.by_trace("trace-1")) == 1
    assert audit.by_trace("trace-none") == []      # 空结果而非异常
