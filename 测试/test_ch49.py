# 测试/test_ch49.py | ch49 并行与子图
"""覆盖：并行分支归并、缺 reducer 的并行报错、子图直接嵌入与显式映射。"""
from __future__ import annotations

from typing import Annotated, TypedDict

import pytest
from langgraph.errors import InvalidUpdateError
from langgraph.graph import END, START, StateGraph

from 示例代码.ch49_parallel_subgraph.ex_49_01_parallel_merge import (
    llm_check,
    merge_list,
    metric_check,
    summarize,
)
from 示例代码.ch49_parallel_subgraph.ex_49_02_subgraph import (
    build_subgraph,
    direct_wrap,
    mapped_bridge,
    report_direct,
    report_mapped,
)


def _parallel_graph():
    class S(TypedDict):
        service: str
        findings: Annotated[list[str], merge_list]   # 复用示例模块的 reducer
        risk_score: Annotated[int, lambda a, b: (a or 0) + (b or 0)]

    g = StateGraph(S)
    g.add_node("llm_check", llm_check)
    g.add_node("metric_check", metric_check)
    g.add_node("summarize", summarize)
    g.add_edge(START, "llm_check")
    g.add_edge(START, "metric_check")
    g.add_edge("llm_check", "summarize")
    g.add_edge("metric_check", "summarize")
    g.add_edge("summarize", END)
    return g.compile()


def test_parallel_branches_merge() -> None:
    """正常路径：两分支结果都进状态，数值 reducer 求和，汇聚节点看到全量。"""
    r = _parallel_graph().invoke({"service": "order-service", "findings": [], "risk_score": 0})
    assert len(r["findings"]) == 3
    assert r["risk_score"] == 5
    assert r["findings"][-1].startswith("汇总") and "P1" in r["findings"][-1]


def test_parallel_without_reducer_raises() -> None:
    """非法结构：并行写同一无 reducer 字段 → InvalidUpdateError。"""
    class Bad(TypedDict):
        out: str

    def w1(s: Bad) -> dict:
        return {"out": "1"}

    def w2(s: Bad) -> dict:
        return {"out": "2"}

    g = StateGraph(Bad)
    g.add_node("w1", w1); g.add_node("w2", w2)
    g.add_edge(START, "w1"); g.add_edge(START, "w2")
    g.add_edge("w1", END); g.add_edge("w2", END)
    with pytest.raises(InvalidUpdateError):
        g.compile().invoke({"out": ""})


def test_subgraph_direct_embedding() -> None:
    """schema 对齐：编译子图直接作为节点，字段同名自动映射。"""
    class P(TypedDict):
        alert: str
        cause: str
        trace: Annotated[list[str], lambda a, b: (a or []) + (b or [])]

    g = StateGraph(P)
    g.add_node("sub_alert", build_subgraph())
    g.add_node("report", report_direct)
    g.add_edge(START, "sub_alert"); g.add_edge("sub_alert", "report"); g.add_edge("report", END)
    r = g.compile().invoke({"alert": "ALERT-7", "cause": "", "trace": []})
    assert "连接池耗尽" in r["cause"]
    assert r["trace"][-1] == "direct-report:ALERT-7 的根因是连接池耗尽"


def test_subgraph_explicit_mapping() -> None:
    """schema 不同：映射节点充当 DTO 转换器，父图字段名与子图解耦。"""
    class P(TypedDict):
        incident: str
        cause: str
        trace: Annotated[list[str], lambda a, b: (a or []) + (b or [])]

    g = StateGraph(P)
    g.add_node("bridge", mapped_bridge)
    g.add_node("report", report_mapped)
    g.add_edge(START, "bridge"); g.add_edge("bridge", "report"); g.add_edge("report", END)
    r = g.compile().invoke({"incident": "INC-9", "cause": "", "trace": []})
    assert r["cause"].startswith("INC-9")
    assert direct_wrap({"alert": "x", "cause": "", "trace": []}) == {"trace": ["direct:进入子图"]}
