# tests/test_ch52.py | 第 52 章：Workflow vs Agent（决策表 / 事件流 / 计划-执行-验证）
"""覆盖（5 个测试）：决策表三条硬问题的组合逻辑（正常/边界/高风险改道）、
Agent loop 事件序列的外部可观察性、计划-执行-验证的失败重规划闭环。

运行：cd /workspace/ai_application_course && python3 -m pytest tests/test_ch52.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.ch52_workflow_agent.ex_52_01_workflow_vs_agent_decision import (  # noqa: E402
    decide,
)
from examples.ch52_workflow_agent.ex_52_01_workflow_vs_agent_decision import (  # noqa: E402
    Requirement,
)
from examples.ch52_workflow_agent.ex_52_03_plan_verify_loop import (  # noqa: E402
    execute,
    plan_execute_verify,
    Step,
    verify,
)


# ---------------------------------------------------------------------------
# 1. 决策表：路径可提前画死 → workflow（确定性优先原则）
# ---------------------------------------------------------------------------


def test_decision_workflow_when_steps_known() -> None:
    d = decide(Requirement("月度报表", steps_known_in_advance=True,
                           needs_reroute_on_failure=False, blast_radius="low"))
    assert d.choice == "workflow"
    assert any("Q1=能" in r for r in d.reasons)


def test_decision_agent_when_needs_reroute() -> None:
    """边界：路径未知 + 失败要换路 → agent（两条理由都应出现）。"""
    d = decide(Requirement("排障助手", steps_known_in_advance=False,
                           needs_reroute_on_failure=True, blast_radius="low"))
    assert d.choice == "agent"
    assert any("Q1=否" in r for r in d.reasons)
    assert any("Q2=要" in r for r in d.reasons)


def test_decision_high_blast_radius_diverts_to_approval() -> None:
    """高风险改道：agent + 副作用大 → workflow+审批（保留规划、动作挂人审）。"""
    d = decide(Requirement("生产计划异常分析并自动提交延期报告",
                           steps_known_in_advance=False,
                           needs_reroute_on_failure=True, blast_radius="high"))
    assert d.choice == "workflow+审批"


# ---------------------------------------------------------------------------
# 2. 计划-执行-验证：验证器拒绝坏结果，闭环带原因重规划
# ---------------------------------------------------------------------------


def test_verify_rejects_failed_execution() -> None:
    step = Step(step_id="S1", action="查计划", tool="query_plan", argument="P-1002")
    bad = execute(Step(step_id="S1", action="查计划", tool="no_such_tool", argument="x"))
    ok, why = verify(step, {"step_id": "S1", "ok": False, "output": "未知工具 no_such_tool"})
    assert not ok
    assert "执行失败" in why
    assert bad["ok"] is False  # execute 对未知工具返回失败记录而不是抛异常（错误即数据）


def test_plan_verify_loop_replans_and_converges() -> None:
    """第一轮含坏步骤（教学剧本）→ 验证失败带原因重规划 → 第二轮全部通过。"""
    outcome = plan_execute_verify("分析 P-1002 的延期并给出恢复方案", max_attempts=2)
    assert len(outcome["attempts"]) == 2
    first, second = outcome["attempts"]
    assert first["all_passed"] is False          # 第一轮故意失败
    assert first["replan_reason"]                # 重规划带原因
    assert second["all_passed"] is True          # 第二轮收敛
    assert outcome["final"] == "全部子任务通过验证"


def test_plan_verify_loop_gives_up_after_max_attempts(monkeypatch) -> None:
    """非法输入兜底：每轮都失败 → 两轮后带已有结论收口（不无限重试）。
    用 monkeypatch 强制每轮都含坏步骤，触发"验证不收敛"分支。"""
    import examples.ch52_workflow_agent.ex_52_03_plan_verify_loop as m

    original_make_plan = m.make_plan  # 先保存原函数，补丁里调用它（避免自递归）

    def always_bad(goal: str, *, with_bad_step: bool = False):
        return original_make_plan(goal, with_bad_step=True)

    monkeypatch.setattr(m, "make_plan", always_bad)
    outcome = m.plan_execute_verify("不可能完成的任务", max_attempts=2)
    assert len(outcome["attempts"]) == 2
    assert all(not a["all_passed"] for a in outcome["attempts"])
    assert outcome["final"].startswith("验证两轮未收敛")
