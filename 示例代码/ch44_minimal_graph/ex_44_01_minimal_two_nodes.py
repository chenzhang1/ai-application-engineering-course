# EX-44-01 | 最小两节点图：State/Node/Edge/START/END 与 reducer | 运行: python3 示例代码/ch44_minimal_graph/ex_44_01_minimal_two_nodes.py
"""完整可运行【主线示例 1：两节点】。

最小可用的 LangGraph 程序，四个构件一次看全：
  State（TypedDict + Annotated reducer）→ Node（函数）→ Edge（连线）→ compile/invoke。
重点观察：节点返回的是"部分更新"（partial update），不是全量状态。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from langgraph.graph import END, START, StateGraph  # noqa: E402


def merge_list(left: list[str] | None, right: list[str] | None) -> list[str]:
    """列表 reducer：LangGraph 语义是 (旧值, 新值) -> 合并值。

    Java 对照：相当于 ConcurrentLinkedQueue 的原子追加语义——多个节点
    同一超步（superstep）写同一字段时，由 reducer 决定怎么归并。
    """
    return (left or []) + (right or [])


class RiskState(TypedDict):
    """图状态 schema：字段 = 共享状态的"列"。"""

    text: str                                    # 无 reducer：整体覆盖
    findings: Annotated[list[str], merge_list]   # 有 reducer：追加合并


def detect(state: RiskState) -> dict:
    """节点 1：检测风险词。只返回自己负责的字段。"""
    findings = [w for w in ("身份证", "银行卡", "密码") if w in state["text"]]
    return {"findings": findings}


def act(state: RiskState) -> dict:
    """节点 2：按检测结果行动。注意它能看到节点 1 已合并进状态的结果。"""
    if state["findings"]:
        return {"text": "已打码", "findings": ["act:转人工"]}
    return {"findings": ["act:正常放行"]}


def main() -> None:
    g = StateGraph(RiskState)
    g.add_node("detect", detect)
    g.add_node("act", act)
    g.add_edge(START, "detect")   # START 是特殊入口节点
    g.add_edge("detect", "act")   # 普通边：无条件流转
    g.add_edge("act", END)        # END 是特殊出口节点

    app = g.compile()

    r1 = app.invoke({"text": "请核对我的身份证照片", "findings": []})
    print("命中风险：", r1)
    r2 = app.invoke({"text": "今天天气不错", "findings": []})
    print("无风险　：", r2)

    print("\n图结构节点：", list(app.get_graph().nodes))


if __name__ == "__main__":
    main()
