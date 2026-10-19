# EX-42-03 | 中间件护栏 + 历史考古：AgentExecutor 时代与迁移表 | 运行: python3 examples/ch42_lc_agent/ex_42_03_agent_limits_legacy.py
"""完整可运行（离线）：
[1] ModelCallLimitMiddleware：给工具循环加"步数护栏"（模型抽风狂点工具的保险丝）；
    exit_behavior='error'（抛异常）与 'end'（优雅收尾）两种模式实测；
[2] 历史考古：langchain.agents 里已没有 AgentExecutor（真实 ImportError 实测）；
    老版本经 langchain-classic 1.0.8 仍可导入（仅兼容用途）；给出迁移对照表。
"""
from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware
from langchain_core.language_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool


class FakeToolChatModel(GenericFakeChatModel):
    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> Any:
        return self


@tool
def query_order(order_id: str) -> dict:
    """按订单号查询订单状态。"""
    return {"order_id": order_id, "status": "已签收"}


def tool_call_msg(i: int) -> AIMessage:
    """脚本条目：模型坚持再次调用同一工具（模拟真实世界的'抽风循环'）。"""
    return AIMessage(content="", tool_calls=[
        {"id": f"c{i}", "name": "query_order", "args": {"order_id": "ORD-1"}, "type": "tool_call"}])


def main() -> None:
    print("[1] 步数护栏：模型想连调 4 次工具，run_limit=2 拦下：")

    print("    exit_behavior='error'（护栏触发 → 抛异常，让调用方处理）：")
    agent_err = create_agent(
        model=FakeToolChatModel(messages=iter([tool_call_msg(i) for i in range(1, 5)])),
        tools=[query_order], system_prompt="x",
        middleware=[ModelCallLimitMiddleware(run_limit=2, exit_behavior="error")],
    )
    try:
        agent_err.invoke({"messages": [HumanMessage(content="查订单 ORD-1")]})
    except Exception as e:
        print(f"      {type(e).__name__}: {e}")

    print("    exit_behavior='end'（护栏触发 → 写一条收尾消息优雅结束）：")
    agent_end = create_agent(
        model=FakeToolChatModel(messages=iter([tool_call_msg(i) for i in range(1, 5)])),
        tools=[query_order], system_prompt="x",
        middleware=[ModelCallLimitMiddleware(run_limit=2, exit_behavior="end")],
    )
    r = agent_end.invoke({"messages": [HumanMessage(content="查订单 ORD-1")]})
    for m in r["messages"]:
        tc = getattr(m, "tool_calls", None)
        print(f"      {type(m).__name__:<12} {str(m.content)[:58]}{[c['name'] for c in tc] if tc else ''}")
    print("    → 裸 SDK 时代这个 while 循环要自己写 max_rounds（EX-24-03 没写，教材调试题里才补）；")
    print("      中间件把它变成一行声明式配置。同类还有 ToolRetryMiddleware/SummarizationMiddleware。")

    print("\n[2] 历史考古（真实导入实测，非凭记忆）：")
    try:
        from langchain.agents import AgentExecutor  # type: ignore[attr-defined]
        print("      langchain.agents.AgentExecutor 竟然可导入（请报告：环境异常）")
    except ImportError as e:
        print(f"      from langchain.agents import AgentExecutor → ImportError: {str(e)[:60]}...")
    import langchain
    import langchain_classic

    print(f"      langchain {langchain.__version__} + langchain-classic {langchain_classic.__version__}:")
    from langchain_classic.agents import AgentExecutor, initialize_agent  # noqa: F401

    print("      from langchain_classic.agents import AgentExecutor, initialize_agent → 导入成功")
    print("      （langchain-classic 是 1.x 为老代码保留的兼容包，新项目禁止新用）")

    print("\n[3] 迁移对照表（教材 42.7 完整版）：")
    rows = [
        ("AgentExecutor(agent, tools, max_iterations=..)", "create_agent(model, tools, middleware=[ModelCallLimitMiddleware(...)])"),
        ("initialize_agent(tools, llm, agent=ZERO_SHOT_REACT...)", "create_agent(...)（工具调用由模型原生协议驱动，不再靠 ReAct 文本协议）"),
        ("AgentType.TOOLS / StructuredChatAgent", "create_agent + @tool（结构化参数走 schema，不走文本解析）"),
        ("load_tools([...])", "按需显式构造工具列表（@tool / 各集成包自带的 toolkit）"),
        ("agent.run(input) / agent.exec(...)", "agent.invoke({'messages': [HumanMessage(content=...)]})"),
        ("AgentExecutor(return_intermediate_steps=True)", "result['messages'] 全程可见（消息即中间步骤）"),
        ("langchain.chains.ConversationChain", "create_agent + checkpointer（持久化记忆），或 messages 列表自管"),
        ("老 create_react_agent（langgraph.prebuilt）", "langchain.agents.create_agent（1.x 的统一入口）"),
    ]
    for old, new in rows:
        print(f"      {old}\n        → {new}")


if __name__ == "__main__":
    main()
