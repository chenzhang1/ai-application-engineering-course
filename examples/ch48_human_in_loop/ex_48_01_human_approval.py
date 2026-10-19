# EX-48-01 | 人工审批：interrupt() + Command(resume=)（主线示例 5：人工审批） | 运行: python3 examples/ch48_human_in_loop/ex_48_01_human_approval.py
"""完整可运行：高风险动作先"暂停等人"，凭指令放行或拒绝。

恢复语义（1.2.16 实测）：
  - interrupt(value) 抛出暂停：本次 invoke 立即返回，结果里带 __interrupt__ 列表；
  - 图停在"当前节点已执行到 interrupt 处"的检查点上，get_state().next 显示该节点；
  - invoke(Command(resume=x), 同一 thread) —— 该节点从头重跑，跑回 interrupt() 那一行时
    不再暂停，而是把 x 作为返回值（就像 interrupt 当场返回了人给的决定）；
  - 所以：interrupt() 之前的代码在恢复时会再执行一遍——只能放只读操作（EX-48-02）。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402
from langgraph.graph import END, START, StateGraph  # noqa: E402
from langgraph.types import Command, interrupt  # noqa: E402


class DeployState(TypedDict):
    action: str
    approved: bool | None
    trace: Annotated[list[str], lambda a, b: (a or []) + (b or [])]


def propose(state: DeployState) -> dict:
    return {"trace": [f"propose:{state['action']}"]}


def approve(state: DeployState) -> dict:
    """审批节点：interrupt() 之前只做只读准备。"""
    ticket = f"申请人=AI助手 action={state['action']}"   # 只读：拼审批单
    decision = interrupt({"ticket": ticket, "question": "是否批准该高风险操作？"})
    # ↑ 第一次执行到这里抛暂停；恢复后重进本节点，此行直接返回 Command(resume=...) 的值
    return {"approved": bool(decision), "trace": [f"approve:{decision}"]}


def execute(state: DeployState) -> dict:
    if state["approved"]:
        return {"trace": [f"execute:{state['action']}（真实副作用放这里）"]}
    return {"trace": ["rejected:已拒绝，不执行"]}


def main() -> None:
    g = StateGraph(DeployState)
    g.add_node("propose", propose)
    g.add_node("approve", approve)
    g.add_node("execute", execute)
    g.add_edge(START, "propose"); g.add_edge("propose", "approve")
    g.add_edge("approve", "execute"); g.add_edge("execute", END)

    app = g.compile(checkpointer=InMemorySaver())   # 没有 checkpointer 就无法恢复！
    cfg = {"configurable": {"thread_id": "deploy-1"}}

    print("── 第 1 次 invoke：跑到 interrupt 暂停 ──")
    r1 = app.invoke({"action": "restart:order-service", "approved": None, "trace": []}, cfg)
    intr = r1["__interrupt__"][0]
    print("暂停点 next =", app.get_state(cfg).next, "| 审批单 =", intr.value["ticket"])

    print("── 第 2 次 invoke：Command(resume=True) 放行 ──")
    r2 = app.invoke(Command(resume=True), cfg)
    print("轨迹：", r2["trace"], "| approved =", r2["approved"])

    print("── 新 thread：Command(resume=False) 拒绝 ──")
    cfg2 = {"configurable": {"thread_id": "deploy-2"}}
    app.invoke({"action": "restart:order-service", "approved": None, "trace": []}, cfg2)
    r4 = app.invoke(Command(resume=False), cfg2)
    print("轨迹：", r4["trace"], "| approved =", r4["approved"])

    print("\n事件序列：invoke(暂停/含 __interrupt__) → 人工决定 → invoke(Command(resume=...)) → 从暂停节点继续")


if __name__ == "__main__":
    main()
