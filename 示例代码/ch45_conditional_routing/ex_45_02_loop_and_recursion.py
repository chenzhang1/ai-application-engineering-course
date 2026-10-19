# EX-45-02 | 循环与终止条件：迭代改进 + recursion_limit 保险丝 | 运行: python3 示例代码/ch45_conditional_routing/ex_45_02_loop_and_recursion.py
"""完整可运行：LangGraph 的"循环"就是一条回到上游节点的边。

两个实验：
  A. 有终止条件的循环：草稿→评审→不通过→再草稿，第 3 轮通过（确定性规则）；
  B. 忘写终止条件：GraphRecursionError 在 recursion_limit 处熔断——
     这是你调试循环图时最常见的朋友。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from langgraph.errors import GraphRecursionError  # noqa: E402
from langgraph.graph import END, START, StateGraph  # noqa: E402


class LoopState(TypedDict):
    draft: str
    rounds: int
    passed: bool
    trace: Annotated[list[str], lambda a, b: (a or []) + (b or [])]


def draft(state: LoopState) -> dict:
    """草稿节点：每轮迭代质量 +1（真实系统里是 LLM 重写，Mock 用确定性规则）。"""
    n = state["rounds"] + 1
    return {"draft": f"草稿 v{n}", "rounds": n, "trace": [f"draft:v{n}"]}


def review(state: LoopState) -> dict:
    """评审节点：第 3 轮起通过（确定性，保证输出可复现）。"""
    ok = state["rounds"] >= 3
    return {"passed": ok, "trace": [f"review:{'通过' if ok else '打回'}"]}


def should_continue(state: LoopState) -> str:
    """终止条件：通过 → END；否则 → 回 draft（'continue' 路由值映射回 draft）。"""
    return "ok" if state["passed"] else "continue"


def main() -> None:
    # A：有终止条件的循环
    g = StateGraph(LoopState)
    g.add_node("draft", draft)
    g.add_node("review", review)
    g.add_edge(START, "draft")
    g.add_edge("draft", "review")
    g.add_conditional_edges("review", should_continue, {"ok": END, "continue": "draft"})
    app = g.compile()

    r = app.invoke({"draft": "", "rounds": 0, "passed": False, "trace": []})
    print("A 循环轨迹：", " -> ".join(r["trace"]))

    # B：忘写终止条件 → recursion_limit 熔断
    class BadState(TypedDict):
        rounds: int

    def bump(s: BadState) -> dict:
        return {"rounds": s["rounds"] + 1}   # 永远返回继续跑

    gb = StateGraph(BadState)
    gb.add_node("bump", bump)
    gb.add_edge(START, "bump"); gb.add_edge("bump", "bump")   # 自环：永不停止
    app_b = gb.compile()
    try:
        app_b.invoke({"rounds": 0}, config={"recursion_limit": 5})
    except GraphRecursionError as e:
        print("B 熔断　　　：", type(e).__name__, "—", str(e)[:48], "…")
        print("（recursion_limit 按'超步 superstep'计数：本图 5 个超步 ≈ 5 次节点执行）")


if __name__ == "__main__":
    main()
