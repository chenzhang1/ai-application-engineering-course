# 测试/test_ch42.py | ch42 create_agent、流式与异步、历史考古
"""覆盖：工具循环消息序列（正常）、checkpointer 跨 invoke 记忆（边界）、工具错误恢复、
步数护栏两种模式、Fake 模型缺 bind_tools 的真实报错（非法输入）、AgentExecutor 迁移事实。"""
from __future__ import annotations

import importlib.metadata

from collections.abc import Iterator, Sequence
from typing import Any

import pytest
from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware
from langchain_core.language_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import ToolException, tool
from langgraph.checkpoint.memory import InMemorySaver

from 示例代码.ch42_lc_agent.ex_42_01_agent_minimal import FakeToolChatModel


@tool
def query_order(order_id: str) -> dict:
    """按订单号查询订单状态。"""
    return {"order_id": order_id, "status": "已签收"}


@tool
def divide(a: int, b: int) -> float:
    """两数相除。"""
    if b == 0:
        raise ToolException("除数不能为 0")
    return a / b


def _tool_msg(i: int) -> AIMessage:
    return AIMessage(content="", tool_calls=[
        {"id": f"c{i}", "name": "query_order", "args": {"order_id": "ORD-1"}, "type": "tool_call"}])


def test_agent_tool_loop_message_sequence() -> None:
    """工具循环：Human → AI(tool_calls) → Tool → AI，状态由框架维护。"""
    agent = create_agent(
        model=FakeToolChatModel(messages=iter([
            AIMessage(content="", tool_calls=[
                {"id": "call_001", "name": "query_order",
                 "args": {"order_id": "ORD-9"}, "type": "tool_call"}]),
            AIMessage(content="订单 ORD-9 已签收。"),
        ])),
        tools=[query_order], system_prompt="订单助手",
    )
    result = agent.invoke({"messages": [HumanMessage(content="查 ORD-9")]})
    types = [type(m).__name__ for m in result["messages"]]
    assert types == ["HumanMessage", "AIMessage", "ToolMessage", "AIMessage"]
    tool_msg = result["messages"][2]
    assert tool_msg.tool_call_id == "call_001" and "已签收" in tool_msg.content
    assert result["messages"][-1].content == "订单 ORD-9 已签收。"


def test_agent_checkpointer_thread_memory() -> None:
    """同 thread_id 两次 invoke 共享状态；get_state 快照完整。"""
    agent = create_agent(
        model=FakeToolChatModel(messages=iter([
            AIMessage(content="已记住你住北京。"), AIMessage(content="你上一轮说北京。")])),
        tools=[], system_prompt="记忆助手", checkpointer=InMemorySaver(),
    )
    cfg = {"configurable": {"thread_id": "t-42"}}
    assert agent.invoke({"messages": [HumanMessage(content="我住北京")]}, cfg)["messages"][-1].content == "已记住你住北京。"
    assert agent.invoke({"messages": [HumanMessage(content="我住哪？")]}, cfg)["messages"][-1].content == "你上一轮说北京。"
    assert len(agent.get_state(cfg).values["messages"]) == 4


def test_agent_tool_error_recovery() -> None:
    """工具抛 ToolException：handle_tool_error 让它变成 ToolMessage，循环继续而非崩掉。"""
    divide.handle_tool_error = "计算失败：除数不能为 0。"
    agent = create_agent(
        model=FakeToolChatModel(messages=iter([
            AIMessage(content="", tool_calls=[
                {"id": "c1", "name": "divide", "args": {"a": 1, "b": 0}, "type": "tool_call"}]),
            AIMessage(content="除数不能为 0，无法计算。"),
        ])),
        tools=[divide], system_prompt="计算助手",
    )
    result = agent.invoke({"messages": [HumanMessage(content="1÷0")]})
    tool_msg = result["messages"][2]
    assert isinstance(tool_msg, ToolMessage)
    assert "除数不能为 0" in tool_msg.content
    assert result["messages"][-1].content == "除数不能为 0，无法计算。"


def test_call_limit_middleware_two_modes() -> None:
    """模型想连调 4 次工具，run_limit=2：error 模式抛异常；end 模式写收尾消息。"""
    script: Iterator[AIMessage] = iter([_tool_msg(i) for i in range(1, 5)])
    agent_err = create_agent(model=FakeToolChatModel(messages=script), tools=[query_order],
                             system_prompt="x",
                             middleware=[ModelCallLimitMiddleware(run_limit=2, exit_behavior="error")])
    with pytest.raises(Exception, match="run limit"):
        agent_err.invoke({"messages": [HumanMessage(content="查")]})

    agent_end = create_agent(
        model=FakeToolChatModel(messages=iter([_tool_msg(i) for i in range(1, 5)])),
        tools=[query_order], system_prompt="x",
        middleware=[ModelCallLimitMiddleware(run_limit=2, exit_behavior="end")])
    r = agent_end.invoke({"messages": [HumanMessage(content="查")]})
    assert len(r["messages"]) == 6
    assert "run limit (2/2)" in r["messages"][-1].content


def test_fake_model_without_bind_tools_raises() -> None:
    """非法输入：GenericFakeChatModel 未实现 bind_tools——create_agent 之前就该踩到这个坑。"""
    with pytest.raises(NotImplementedError):
        GenericFakeChatModel(messages=iter([AIMessage(content="x")])).bind_tools([query_order])


def test_legacy_agentexecutor_migration_facts() -> None:
    """历史考古的代码层事实：1.x 的 langchain.agents 无 AgentExecutor；兼容包在 langchain-classic。"""
    with pytest.raises(ImportError):
        from langchain.agents import AgentExecutor  # type: ignore[attr-defined]  # noqa: F401
    from langchain_classic.agents import AgentExecutor, initialize_agent  # noqa: F401

    assert AgentExecutor is not None and initialize_agent is not None
    import langchain
    import langchain_classic

    # 版本断言只锁"主次版本线"与配套关系：1.x 主包无 AgentExecutor，兼容包同步演进。
    # （不硬编码补丁版本：镜像源补丁版本会浮动，行为事实才是考点。）
    assert langchain.__version__.startswith("1.")
    assert langchain_classic.__version__.startswith("1.")
    assert langchain.__version__ == importlib.metadata.version("langchain")
    assert langchain_classic.__version__ == importlib.metadata.version("langchain-classic")
