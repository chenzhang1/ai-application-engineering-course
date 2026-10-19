# EX-43-02 | 同一条业务流，第一次画成图（预览 ch44/ch45） | 运行: python3 示例代码/ch43_graph_intro/ex_43_02_first_graph_preview.py
"""完整可运行：把 EX-43-01 的 v2 控制流搬进 LangGraph。

先跑通"节点+边+条件边"的整体骨架，逐个 API 的细节 ch44/ch45 展开。
注意：本例节点之间传递的是"共享状态"（一个 dict），不是函数返回值直连——
这是图编排与函数链最大的差异。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # 仓库根

from langgraph.graph import END, START, StateGraph  # noqa: E402


def merge_list(left: list[str] | None, right: list[str] | None) -> list[str]:
    """reducer：新值追加到旧值后面（不指定 reducer 的字段会被整体覆盖）。"""
    return (left or []) + (right or [])


class TicketState(TypedDict):
    text: str
    route: str                      # 普通字段：后写覆盖先写
    trace: Annotated[list[str], merge_list]   # 审计轨迹：追加合并


def sensitive_gate(state: TicketState) -> dict:
    """敏感闸门：命中敏感词 → 转人工，否则放行。"""
    if "身份证" in state["text"] or "银行卡" in state["text"]:
        return {"route": "manual", "trace": ["gate:敏感拦截"]}
    return {"route": "auto", "trace": ["gate:放行"]}


def manual_review(state: TicketState) -> dict:
    return {"trace": [f"manual_review:{state['text'][:10]}…"]}


def auto_pipeline(state: TicketState) -> dict:
    return {"trace": [f"auto:{state['text'][:10]}…"]}


def route_by_gate(state: TicketState) -> str:
    """条件边的路由函数：返回值决定下一跳（ch45 细讲）。"""
    return state["route"]


def main() -> None:
    g = StateGraph(TicketState)
    g.add_node("sensitive_gate", sensitive_gate)
    g.add_node("manual_review", manual_review)
    g.add_node("auto_pipeline", auto_pipeline)

    g.add_edge(START, "sensitive_gate")
    # 条件边：gate 之后按 route 字段分流；path_map 把路由值映射到节点名
    g.add_conditional_edges(
        "sensitive_gate", route_by_gate,
        {"manual": "manual_review", "auto": "auto_pipeline"},
    )
    g.add_edge("manual_review", END)
    g.add_edge("auto_pipeline", END)

    app = g.compile()
    for text in ("发票抬头开错了", "请查我的银行卡"):
        r = app.invoke({"text": text, "trace": []})
        print(f"{text!r:>12} -> route={r['route']:<6} trace={r['trace']}")

    print("图结构节点：", list(app.get_graph().nodes))


if __name__ == "__main__":
    main()
