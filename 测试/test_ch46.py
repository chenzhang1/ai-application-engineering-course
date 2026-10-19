# 测试/test_ch46.py | ch46 工具调用循环
"""覆盖：ChatResult→AIMessage 适配、OpenAI 风格往返、路由函数、Mock 脚本驱动的完整循环、
脚本耗尽的失败路径。"""
from __future__ import annotations

import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from 示例代码.ch46_tool_loop.ex_46_01_tool_loop import (
    make_agent_node,
    query_order_status,
    query_refund_policy,
    route_after_agent,
    to_ai_message,
    to_openai_style,
)
from 示例代码.公共.llm_client import ChatResult, MockLLM, ToolCall


def _build_app(llm: MockLLM):
    g = StateGraph(MessagesState)
    g.add_node("agent", make_agent_node(llm))
    g.add_node("tools", ToolNode([query_order_status, query_refund_policy]))
    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", route_after_agent, {"tools": "tools", END: END})
    g.add_edge("tools", "agent")
    return g.compile()


def test_to_ai_message_carries_tool_calls() -> None:
    """适配层：ChatResult 的 tool_calls 变成 AIMessage 的 dict 形态。"""
    r = ChatResult(content="", tool_calls=[ToolCall(id="c1", name="t1", arguments={"x": 1})])
    m = to_ai_message(r)
    assert isinstance(m, AIMessage)
    assert m.tool_calls[0]["name"] == "t1" and m.tool_calls[0]["args"] == {"x": 1}
    assert m.tool_calls[0]["id"] == "c1" and m.tool_calls[0]["type"] == "tool_call"


def test_message_style_round_trip() -> None:
    """消息往返：LangChain 消息 → OpenAI dict，覆盖三种角色。"""
    msgs = [
        HumanMessage(content="q"),
        to_ai_message(ChatResult(content="", tool_calls=[ToolCall("c1", "t1", {})])),
        ToolMessage(content="ok", tool_call_id="c1"),
    ]
    d = to_openai_style(msgs)
    assert [x["role"] for x in d] == ["user", "assistant", "tool"]
    assert d[1]["tool_calls"][0]["function"]["name"] == "t1"
    assert json.loads(d[1]["tool_calls"][0]["function"]["arguments"]) == {}
    assert d[2]["tool_call_id"] == "c1"


def test_tools_are_real_functions() -> None:
    """工具节点用真函数：不依赖模型，输出确定；ToolNode 默认名是 tools。"""
    assert '"status": "paid"' in query_order_status("ORD-1")
    assert "7 天" in query_refund_policy("physical")
    assert ToolNode([query_order_status]).name == "tools"


def test_route_after_agent() -> None:
    """条件边：有 tool_calls 去 tools，否则结束（END 字面量是 __end__）。"""
    with_calls = to_ai_message(ChatResult(content="", tool_calls=[ToolCall("c1", "t1", {})]))
    assert route_after_agent({"messages": [with_calls]}) == "tools"
    assert route_after_agent({"messages": [AIMessage(content="final")]}) == "__end__"


def test_full_tool_loop_two_rounds() -> None:
    """完整循环：两次工具调用后模型总结，消息状态按轮次演进。"""
    llm = MockLLM(script=[
        {"tool_calls": [{"id": "call_001", "name": "query_order_status",
                         "arguments": {"order_id": "ORD-1001"}}]},
        {"tool_calls": [{"id": "call_002", "name": "query_refund_policy",
                         "arguments": {"order_type": "physical"}}]},
        {"content": "订单已支付，支持 7 天无理由退款。"},
    ])
    r = _build_app(llm).invoke({"messages": [HumanMessage(content="ORD-1001 能退款吗")]})

    kinds = [type(m).__name__ for m in r["messages"]]
    assert kinds == ["HumanMessage", "AIMessage", "ToolMessage",
                     "AIMessage", "ToolMessage", "AIMessage"]
    assert r["messages"][-1].content == "订单已支付，支持 7 天无理由退款。"
    assert len(llm.calls) == 3  # 模型被调用 3 次后停止


def test_script_exhaustion_fails_loudly() -> None:
    """失败路径：脚本耗尽时 MockLLM 抛 RuntimeError，循环不会静默失控。"""
    llm = MockLLM(script=[{"tool_calls": [{"id": "c", "name": "query_order_status",
                                           "arguments": {"order_id": "X"}}]}])
    with pytest.raises(RuntimeError) as ei:
        _build_app(llm).invoke({"messages": [HumanMessage(content="x")]},
                               config={"recursion_limit": 10})
    assert "script" in str(ei.value)
