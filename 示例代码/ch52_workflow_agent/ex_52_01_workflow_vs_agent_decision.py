# EX-52-01 | Workflow 还是 Agent：把选型变成可执行的决策表
# 运行: python3 示例代码/ch52_workflow_agent/ex_52_01_workflow_vs_agent_decision.py
"""确定性演示（纯标准库，无模型调用）：

给 5 个真实业务需求逐条打分，输出"该用 Workflow 还是 Agent"的判断与理由。
判断标准来自 52.3 的三条硬问题：
    Q1 路径能不能提前画出来？（能 → Workflow）
    Q2 失败了要不要"换一条路再试"？（要 → Agent）
    Q3 出错时业务能接受多大代价？（代价高 → 收敛控制流，加人审）
决策表是代码不是散文——团队评审时可以直接跑给架构师看。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class Requirement:
    """一个待决策的 AI 功能需求。"""

    name: str
    steps_known_in_advance: bool   # Q1: 路径可提前画死吗
    needs_reroute_on_failure: bool  # Q2: 失败要换路吗（模型自主重试/改道）
    blast_radius: Literal["low", "high"]  # Q3: 出错代价


@dataclass
class Decision:
    choice: Literal["workflow", "agent", "workflow+审批"]
    reasons: list[str]


def decide(req: Requirement) -> Decision:
    """决策表本体：三条硬问题的组合逻辑（与 52.3 的表格一一对应）。"""
    reasons: list[str] = []
    if req.steps_known_in_advance:
        reasons.append("Q1=能：路径可提前画出，控制流写死反而可测试、可审计")
        choice: Literal["workflow", "agent", "workflow+审批"] = "workflow"
    else:
        reasons.append("Q1=否：路径取决于运行时读到的数据/模型判断，需要动态路由")
        choice = "agent"
    if req.needs_reroute_on_failure:
        reasons.append("Q2=要：失败后要换一条路（换参数/换工具/换顺序），这是 Agent loop 的本职")
        choice = "agent"
    if req.blast_radius == "high":
        if choice == "agent":
            reasons.append("Q3=代价高：Agent 自由度高 + 副作用大 → 保留 Agent 规划，但高风险动作挂人工审批")
            choice = "workflow+审批"
        else:
            reasons.append("Q3=代价高：Workflow 路径固定即可控，副作用节点前加人审门（ch48 interrupt）")
            choice = "workflow+审批"
    return Decision(choice=choice, reasons=reasons)


def main() -> None:
    requirements = [
        Requirement("发票抬头抽取后按类别路由工单", steps_known_in_advance=True,
                    needs_reroute_on_failure=False, blast_radius="low"),
        Requirement("按用户自然语言查订单+查物流+生成解释",
                    steps_known_in_advance=False, needs_reroute_on_failure=False,
                    blast_radius="low"),
        Requirement("排障助手：日志取证→假设→验证→（证据不足换证据再查）",
                    steps_known_in_advance=False, needs_reroute_on_failure=True,
                    blast_radius="low"),
        Requirement("生产计划异常分析并自动提交延期报告",
                    steps_known_in_advance=False, needs_reroute_on_failure=True,
                    blast_radius="high"),
        Requirement("月度报表：固定 SQL→固定模板→固定邮件",
                    steps_known_in_advance=True, needs_reroute_on_failure=False,
                    blast_radius="low"),
    ]
    print("== Workflow vs Agent 决策表（运行结果）==")
    for req in requirements:
        d = decide(req)
        print(f"\n需求：{req.name}")
        for r in d.reasons:
            print(f"  - {r}")
        print(f"  ⇒ 结论：{d.choice}")


if __name__ == "__main__":
    main()
