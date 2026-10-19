# EX-45-03 | Send API：按数据动态分发（Map-Reduce） | 运行: python3 示例代码/ch45_conditional_routing/ex_45_03_send_fanout.py
"""完整可运行：条件路由函数返回 Send 列表 → 动态"扇出"任意数量的并行任务。

与静态并行（ch49 的多边并行）的区别：Send 的目标节点和份数在运行时由状态决定——
文档几段就发几份，每份还能带不同的输入（arg）。最后用 reducer 归并（Map-Reduce）。

结构：START → hub（分发中枢，无业务）→（条件边返回 Send 列表）→ score × N → combine。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from langgraph.graph import END, START, StateGraph  # noqa: E402
from langgraph.types import Send  # noqa: E402


class MapReduceState(TypedDict):
    docs: list[str]
    scores: Annotated[list[int], lambda a, b: (a or []) + (b or [])]
    best: str


def hub(state: MapReduceState) -> dict:
    """分发中枢：只读状态，不发任务——真正的扇出由它后面的条件边完成。"""
    return {}


def fan_out(state: MapReduceState) -> list[Send]:
    """条件边函数：每篇文档发一个 Send('score', 输入)。份数运行时才确定。"""
    return [Send("score", {"doc": d}) for d in state["docs"]]


def score(inputs: dict) -> dict:
    """Map 节点：注意它收到的是 Send 的 arg（单篇文档），不是整张图状态。"""
    doc: str = inputs["doc"]
    # 确定性打分：正文越长分越高（真实系统里是模型打分）
    return {"scores": [len(doc)]}


def combine(state: MapReduceState) -> dict:
    """Reduce 节点：等所有 score 分支都归并进状态后才执行。"""
    best = max(state["scores"]) if state["scores"] else 0
    return {"best": f"最高分 {best}（共 {len(state['scores'])} 份）"}


def main() -> None:
    g = StateGraph(MapReduceState)
    g.add_node("hub", hub)
    g.add_node("score", score)
    g.add_node("combine", combine)
    g.add_edge(START, "hub")
    g.add_conditional_edges("hub", fan_out)   # 返回 Send 列表：动态扇出
    g.add_edge("score", "combine")
    g.add_edge("combine", END)

    app = g.compile()
    r = app.invoke({"docs": ["短文", "这是一篇比较长的文档，用来得高分", "中等长度文档哦"],
                    "scores": [], "best": ""})
    print("scores =", r["scores"])
    print("best   =", r["best"])

    # 换输入：文档数量变化，扇出数量自动变化——这就是"动态"
    r2 = app.invoke({"docs": ["只有一篇"], "scores": [], "best": ""})
    print("第二次 ：", r2["scores"], "/", r2["best"])


if __name__ == "__main__":
    main()
