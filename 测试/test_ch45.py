# 测试/test_ch45.py | ch45 条件路由与循环
"""覆盖：条件边路由映射、Mock 结构化分类节点、循环终止、recursion_limit、Send 动态扇出。"""
from __future__ import annotations

from typing import Annotated, TypedDict

import pytest
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from 示例代码.ch45_conditional_routing.ex_45_01_conditional_route import (
    TicketState,
    classify,
    route_by_category,
)
from 示例代码.ch45_conditional_routing.ex_45_02_loop_and_recursion import (
    draft,
    review,
    should_continue,
)
from 示例代码.ch45_conditional_routing.ex_45_03_send_fanout import combine, fan_out, score


def _blank_ticket(text: str) -> TicketState:
    return {"text": text, "category": "", "urgent": False, "trace": []}


def test_classify_node_mock_structured() -> None:
    """模型节点（Mock）：从输入 key=value 解析结构化分类，输出可复现。"""
    out = classify(_blank_ticket("发票开错 category=billing urgent=true"))
    assert out["category"] == "billing" and out["urgent"] is True
    out2 = classify(_blank_ticket("App 闪退 category=tech"))
    assert out2["category"] == "tech" and out2["urgent"] is False


def test_conditional_edges_mapping() -> None:
    """路由函数返回值决定下一跳；path_map 必须覆盖所有取值。"""
    assert route_by_category({"category": "tech"}) == "tech"

    class S(TypedDict):
        category: str

    g = StateGraph(S)
    g.add_node("classify", lambda s: {"category": s["category"]})
    g.add_node("billing", lambda s: {})
    g.add_conditional_edges("classify", route_by_category, {"billing": "billing"})
    g.add_edge(START, "classify"); g.add_edge("billing", END)
    app = g.compile()
    # 非法输入：category 取值不在 path_map → KeyError（fail fast，1.2.16 实测）
    with pytest.raises(KeyError):
        app.invoke({"category": "general"})


def test_loop_terminates_at_condition() -> None:
    """正常路径：第 3 轮评审通过后循环终止。"""
    class LoopState(TypedDict):
        draft: str
        rounds: int
        passed: bool
        trace: Annotated[list[str], lambda a, b: (a or []) + (b or [])]

    g = StateGraph(LoopState)
    g.add_node("draft", draft); g.add_node("review", review)
    g.add_edge(START, "draft"); g.add_edge("draft", "review")
    g.add_conditional_edges("review", should_continue, {"ok": END, "continue": "draft"})
    r = g.compile().invoke({"draft": "", "rounds": 0, "passed": False, "trace": []})
    assert r["rounds"] == 3 and r["passed"] is True


def test_recursion_limit_raises() -> None:
    """保险丝：自环图必须被 GraphRecursionError 熔断。"""
    class Bad(TypedDict):
        n: int

    g = StateGraph(Bad)
    g.add_node("bump", lambda s: {"n": s["n"] + 1})
    g.add_edge(START, "bump"); g.add_edge("bump", "bump")
    with pytest.raises(GraphRecursionError):
        g.compile().invoke({"n": 0}, config={"recursion_limit": 5})


def test_send_fanout_dynamic() -> None:
    """Send：份数随输入变化，Map 节点收到单份 arg。"""
    sends = fan_out({"docs": ["ab", "cdef"]})
    assert len(sends) == 2
    assert isinstance(sends[0], Send) and sends[0].arg == {"doc": "ab"}
    assert score({"doc": "abcd"}) == {"scores": [4]}
    assert combine({"scores": [2, 4], "docs": [], "best": ""})["best"].startswith("最高分 4")
