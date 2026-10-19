# tests/test_ch44.py | ch44 最小两节点图
"""覆盖：reducer 追加/覆盖语义、add_messages 包装与同 id 替换、MessagesState、非法更新。"""
from __future__ import annotations

from typing import Annotated, TypedDict

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.errors import InvalidUpdateError
from langgraph.graph import END, START, MessagesState, StateGraph, add_messages

from examples.ch44_minimal_graph.ex_44_01_minimal_two_nodes import act, detect, merge_list
from examples.ch44_minimal_graph.ex_44_02_reducer_semantics import (
    merge_unique,
    step_a1,
    step_a2,
    step_b1,
    step_same_id,
)
from examples.ch44_minimal_graph.ex_44_03_messages_state import check_node, echo_node


def _risk_graph():
    class RiskState(TypedDict):
        text: str
        findings: Annotated[list[str], merge_list]

    g = StateGraph(RiskState)
    g.add_node("detect", detect)
    g.add_node("act", act)
    g.add_edge(START, "detect"); g.add_edge("detect", "act"); g.add_edge("act", END)
    return g.compile()


def test_reducer_appends_instead_of_overwrites() -> None:
    """正常路径：reducer 字段把节点 1 的结果留给节点 2 看。"""
    r = _risk_graph().invoke({"text": "请核对我的身份证", "findings": []})
    assert r["findings"] == ["身份证", "act:转人工"]


def test_no_reducer_overwrites() -> None:
    """覆盖语义：无 reducer 字段被最后一次写入整体顶掉（教学实验 A）。"""
    class Plain(TypedDict):
        history: list[str]

    g = StateGraph(Plain)
    g.add_node("a1", step_a1); g.add_node("a2", step_a2)
    g.add_edge(START, "a1"); g.add_edge("a1", "a2"); g.add_edge("a2", END)
    r = g.compile().invoke({"history": ["init"]})
    assert r["history"] == ["a2"]


def test_add_messages_upsert_by_id() -> None:
    """add_messages：追加新 id、同 id 替换（消息级 upsert）。"""
    class ChatState(TypedDict):
        messages: Annotated[list, add_messages]

    g = StateGraph(ChatState)
    g.add_node("b1", step_b1); g.add_node("same", step_same_id)
    g.add_edge(START, "b1"); g.add_edge("b1", "same"); g.add_edge("same", END)
    r = g.compile().invoke({"messages": []})
    assert len(r["messages"]) == 1                     # 同 id 被替换而非追加
    assert r["messages"][0].content == "同 id 替换版"

    # 元组输入自动包装为 HumanMessage
    merged = add_messages([("user", "你好")], [])
    assert isinstance(merged[0], HumanMessage)


def test_messages_state_nodes() -> None:
    """MessagesState：节点直返消息对象；质检节点能数出轮次。"""
    g = StateGraph(MessagesState)
    g.add_node("echo", echo_node); g.add_node("check", check_node)
    g.add_edge(START, "echo"); g.add_edge("echo", "check"); g.add_edge("check", END)
    r = g.compile().invoke({"messages": [HumanMessage(content="查订单")]})
    assert r["messages"][0].content == "查订单"
    assert isinstance(r["messages"][1], AIMessage)
    assert "1 轮" in r["messages"][2].content


def test_parallel_write_without_reducer_rejected() -> None:
    """非法输入：同一超步两个节点写同一无 reducer 字段 → InvalidUpdateError。"""
    class Bad(TypedDict):
        out: str

    def w1(s: Bad) -> dict:
        return {"out": "1"}

    def w2(s: Bad) -> dict:
        return {"out": "2"}

    g = StateGraph(Bad)
    g.add_node("w1", w1); g.add_node("w2", w2)
    g.add_edge(START, "w1"); g.add_edge(START, "w2"); g.add_edge("w1", END); g.add_edge("w2", END)
    with pytest.raises(InvalidUpdateError):
        g.compile().invoke({"out": ""})


def test_merge_unique_dedups_within_superstep() -> None:
    """自定义 reducer：同一节点重复事件也会去重。"""
    assert merge_unique(["a", "a"], ["a", "b"]) == ["a", "b"]
