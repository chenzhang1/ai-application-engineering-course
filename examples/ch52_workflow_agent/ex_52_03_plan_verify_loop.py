# EX-52-03 | 任务拆解 / 规划 / 验证：一个带"验收员"的最小计划-执行循环
# 运行: python3 examples/ch52_workflow_agent/ex_52_03_plan_verify_loop.py
"""完整可运行（LLM_MODE=mock，Mock 结构化输出，离线确定性）：

Agent 的核心不是"会调工具"，而是三步闭环：
    拆解（decompose）：把模糊目标切成可验证的子任务清单；
    执行（execute）  ：逐个子任务调工具/计算，留痕；
    验证（verify）   ：对照"完成判据"检查每个子任务，不合格的**带着失败原因**重新规划。
本例用 Mock 的 chat_structured 生成计划（Plan schema），用纯函数执行，
用一个确定性验证器验收；第一轮故意让一个子任务失败，演示"验证→重规划"闭环。
循环上限 max_attempts=2——验证不收敛就带着已有结果收口，这是防失控的第一道保险丝。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # 仓库根
from examples.common.llm_client import chat_structured
from pydantic import BaseModel, Field


class Step(BaseModel):
    """计划中的一个子任务：必须自带"完成判据"，否则验证无从谈起。"""

    step_id: str
    action: str                      # 做什么（人能读懂）
    tool: str                        # 用什么工具（query_plan / check_material / estimate_recovery）
    argument: str = ""               # 工具参数（Mock 下从 key=value 提取）
    done_when: str = Field(default="工具返回非空结果")  # 完成判据（验证器的依据）


class Plan(BaseModel):
    """一次完整的执行计划（字段带默认值：Mock 解析只给 goal，steps 由教学脚本回填）。"""

    goal: str = "（未解析到目标）"
    steps: list[Step] = Field(default_factory=list)


# ---- 工具箱（与 ch54 的治理思想一致：每个工具行为确定、可单测） -------------------
def tool_query_plan(argument: str) -> str:
    data = {"P-1002": "P-1002 转向节 1200 件，状态=延期，欠 300 件"}
    return data.get(argument.strip(), f"计划 {argument} 不存在")


def tool_check_material(argument: str) -> str:
    return "库存毛坯 150 件（缺口 150 件，需紧急采购或改排产）"


def tool_estimate_recovery(argument: str) -> str:
    return "改排产后预计 3 天追平缺口，交付日期可保"


TOOLS: dict[str, Any] = {
    "query_plan": tool_query_plan,
    "check_material": tool_check_material,
    "estimate_recovery": tool_estimate_recovery,
}


def execute(step: Step) -> dict[str, Any]:
    """执行一个子任务：工具不存在/抛异常都不许炸循环——错误即数据。"""
    fn = TOOLS.get(step.tool)
    if fn is None:
        return {"step_id": step.step_id, "ok": False, "output": f"未知工具 {step.tool}"}
    try:
        return {"step_id": step.step_id, "ok": True, "output": fn(step.argument)}
    except Exception as exc:  # noqa: BLE001 —— 教学：把异常变成可验证的失败记录
        return {"step_id": step.step_id, "ok": False, "output": f"{type(exc).__name__}: {exc}"}


def verify(step: Step, result: dict[str, Any]) -> tuple[bool, str]:
    """确定性验证器：真实系统里可换成 LLM 判分/规则引擎/两者混合（52.5 展开）。"""
    if not result["ok"]:
        return False, f"执行失败：{result['output']}"
    if step.tool == "query_plan" and "不存在" in result["output"]:
        return False, "判据不满足：计划号不存在，需要先确认计划号"
    if "缺口" in result["output"] and step.tool == "check_material":
        return True, "完成：缺口已量化（后续动作：采购/改排产）"
    return True, "完成：工具返回非空结果"


def make_plan(goal: str, *, with_bad_step: bool) -> Plan:
    """Mock 场景：用 chat_structured 走一遍结构化输出（key=value 约定见第四部分）。

    教学简化：计划主体在代码里写死，schema 校验经 chat_structured 走真实链路——
    真实系统里这段由模型生成，schema 约束与"完成判据必须显式"两条不变。
    """
    user = (f"goal=P-1002延期分析 step1=query_plan:P-1002 step2=check_material:P-1002 "
            + ("step3=unknown_tool:destroy" if with_bad_step else "step3=estimate_recovery:P-1002"))
    plan = chat_structured(
        [{"role": "system", "content": "你是排产规划器，输出 Plan JSON。"},
         {"role": "user", "content": user}], Plan)
    # Mock 按 key=value 解析填充 schema 字段：goal 走真实校验链路；
    # steps 是嵌套清单、kv 解析表达不了，按教学脚本回填（保持确定性）
    steps = [
        Step(step_id="S1", action="查询生产计划当前状态", tool="query_plan", argument="P-1002",
             done_when="返回计划状态与缺口数量"),
        Step(step_id="S2", action="核对物料库存能否补缺口", tool="check_material", argument="P-1002",
             done_when="缺口被量化"),
        Step(step_id="S3", action="估算追回交付的可行方案", tool="estimate_recovery" if not with_bad_step else "destroy_plan",
             argument="P-1002", done_when="给出可执行方案"),
    ]
    return Plan(goal=plan.goal, steps=steps)


def plan_execute_verify(goal: str, *, max_attempts: int = 2) -> dict[str, Any]:
    """拆解 → 执行 → 验证 → （重规划）主循环。"""
    attempts: list[dict[str, Any]] = []
    bad_first = True  # 教学剧本：第一轮第 3 步给个坏工具名，逼出重规划
    for attempt in range(1, max_attempts + 1):
        plan = make_plan(goal, with_bad_step=(bad_first and attempt == 1))
        results = [execute(s) for s in plan.steps]
        verdicts = [verify(s, r) for s, r in zip(plan.steps, results)]
        failed = [(s, v) for s, v in zip(plan.steps, verdicts) if not v[0]]
        attempts.append({
            "attempt": attempt,
            "steps": [{"id": s.step_id, "tool": s.tool, "ok": v[0], "why": v[1]}
                      for s, v in zip(plan.steps, verdicts)],
            "all_passed": not failed,
            "replan_reason": failed[0][1][1] if failed else None,
        })
        if not failed:
            return {"goal": goal, "attempts": attempts, "final": "全部子任务通过验证"}
        print(f"  [attempt {attempt}] {len(failed)} 个子任务未过验证 → 带原因重规划：{failed[0][1][1]}")
    return {"goal": goal, "attempts": attempts, "final": "验证两轮未收敛，带已有结论收口并人工介入"}


def main() -> None:
    print("== 计划-执行-验证循环（Mock 驱动，确定性）==")
    outcome = plan_execute_verify("分析 P-1002 的延期并给出恢复方案")
    for a in outcome["attempts"]:
        print(f"\n第 {a['attempt']} 轮：")
        for st in a["steps"]:
            print(f"  {st['id']} {st['tool']:<18} {'✓' if st['ok'] else '✗'} {st['why']}")
    print(f"\n最终：{outcome['final']}")


if __name__ == "__main__":
    main()
