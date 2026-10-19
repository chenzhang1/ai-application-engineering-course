# EX-49-01 | 并行分支与结果合并：同一超步的多路写入 | 运行: python3 examples/ch49_parallel_subgraph/ex_49_01_parallel_merge.py
"""完整可运行：START 同时连两个节点 → 它们在同一个超步（superstep）里并行执行，
各自返回部分更新，由字段的 reducer 归并。

LangGraph 的并行不是你写的线程池：Pregel 执行模型按超步推进——"一个超步内
所有可运行节点都执行完，才进入下一超步"。所以 reducer 是必须的（否则同字段
多路写入会报 InvalidUpdateError）。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from langgraph.graph import END, START, StateGraph  # noqa: E402


def merge_list(a: list[str] | None, b: list[str] | None) -> list[str]:
    return (a or []) + (b or [])


class CheckState(TypedDict):
    service: str
    findings: Annotated[list[str], merge_list]
    risk_score: Annotated[int, lambda a, b: (a or 0) + (b or 0)]   # 数值 reducer：求和


def llm_check(state: CheckState) -> dict:
    """分支 1：模型视角（Mock 确定性输出）。"""
    return {"findings": [f"模型: {state['service']} 日志含 timeout 关键词"], "risk_score": 2}


def metric_check(state: CheckState) -> dict:
    """分支 2：指标视角。"""
    return {"findings": [f"指标: {state['service']} P99 上升 40%"], "risk_score": 3}


def summarize(state: CheckState) -> dict:
    """汇聚节点：等两个分支都到齐才执行（超步屏障）。"""
    total = state["risk_score"]
    level = "P1" if total >= 4 else "P2"
    return {"findings": [f"汇总: 综合 {total} 分 → {level}"]}


def main() -> None:
    g = StateGraph(CheckState)
    g.add_node("llm_check", llm_check)
    g.add_node("metric_check", metric_check)
    g.add_node("summarize", summarize)
    g.add_edge(START, "llm_check")        # 同一起点两条边 = 并行分支
    g.add_edge(START, "metric_check")
    g.add_edge("llm_check", "summarize")  # 汇聚：两条边都指向 summarize
    g.add_edge("metric_check", "summarize")
    g.add_edge("summarize", END)

    app = g.compile()
    r = app.invoke({"service": "order-service", "findings": [], "risk_score": 0})
    for f in r["findings"]:
        print(" -", f)
    print("risk_score =", r["risk_score"], "（2+3 由数值 reducer 求和）")
    print("\n若把 findings 字段的 reducer 去掉，两个分支的写入会抛 InvalidUpdateError —— 并行必有归并。")


if __name__ == "__main__":
    main()
