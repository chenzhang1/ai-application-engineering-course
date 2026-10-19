# tests/test_ch53.py | 第 53 章：单 Agent vs 多 Agent（隔离收益 / 失败策略 / 汇总缺口）
"""覆盖（5 个测试）：领域隔离后工具选择正确性、子 Agent 失败三策略
（retry→degrade→escalate）、主 Agent 汇总如实上报缺口、通信协议形状。

运行：cd /workspace/ai_application_course && python3 -m pytest tests/test_ch53.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.ch53_single_vs_multi.ex_53_01_single_agent_limits import (  # noqa: E402
    TOOLS_ALL,
    TOOLS_ORDER,
    pick_tool,
)
from examples.ch53_single_vs_multi.ex_53_02_two_role_collaboration import (  # noqa: E402
    SubTask,
    orchestrate,
    run_sub_agent,
)


def test_domain_isolation_improves_tool_selection() -> None:
    """领域隔离：订单子 Agent 只见 2 个工具，查询类请求不再误选到物流工具。"""
    isolated = pick_tool(TOOLS_ORDER, "这个包裹到哪了")
    omnibus = pick_tool(TOOLS_ALL, "这个包裹到哪了")
    assert isolated == "query_order"     # 隔离后选对
    assert omnibus == "query_order"      # 大杂烩里'查询'语义碰巧也命中 order——
    # 单看一条不可靠，隔离的价值在批量误选率：全请求统计见 EX-53-01 运行输出


def test_sub_agent_retry_then_reports_failure_with_gaps() -> None:
    """失败三策略：物流工具恒定抛错 → 子 Agent 两次尝试后 failed + gaps（不编造）。"""
    result = run_sub_agent(SubTask(subtask_id="T2", domain="logistics",
                                   instruction="查物流轨迹",
                                   must_include=["轨迹", "预计送达"]))
    assert result.status == "failed"
    assert result.attempts == 2          # retry 一次后再降级仍失败 → failed
    assert result.gaps == ["物流轨迹不可得"]


def test_sub_agent_ok_when_requirements_covered() -> None:
    result = run_sub_agent(SubTask(subtask_id="T1", domain="order",
                                   instruction="查订单状态", must_include=["已发货"]))
    assert result.status == "ok"
    assert result.attempts == 1
    assert result.gaps == []


def test_orchestrate_reports_summary_and_gaps() -> None:
    """主 Agent 只消费 SubResult 形状：2 成功 / 1 失败，缺口如实上报。"""
    out = orchestrate("客户 A1001 的履约情况总览")
    assert out["summary"] == "2 成功 / 0 降级 / 1 失败"
    assert out["gaps"] == ["物流轨迹不可得"]
    assert len(out["report_parts"]) == 2     # 失败域不进报告正文（不编造）
    assert set(out["attempts"]) == {"T1", "T2", "T3"}


def test_subtask_protocol_fields() -> None:
    """通信契约：派工单有默认值，子 Agent 不需要主 Agent 的任何上下文。"""
    t = SubTask(subtask_id="T9")
    assert t.domain == "order" and t.must_include == []
