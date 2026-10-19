# EX-42-02 | checkpointer 持久化（thread_id 多轮）与三种流式 | 运行: python3 示例代码/ch42_lc_agent/ex_42_02_agent_checkpoint_stream.py
"""完整可运行（离线，asyncio 真实运行）：
[1] checkpointer=InMemorySaver + thread_id：跨 invoke 的对话记忆与 get_state 快照；
[2] stream 三模式实测：values（全量状态）/ updates（节点增量）/ messages（逐 token）；
[3] astream（异步逐条）——SSE 服务的直接素材（对照 ch17 SSE StreamingResponse）。
"""
from __future__ import annotations

import asyncio
from collections.abc import Iterator, Sequence
from typing import Any

from langchain.agents import create_agent
from langchain_core.language_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver


class FakeToolChatModel(GenericFakeChatModel):
    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> Any:
        return self


def main() -> None:
    print("[1] checkpointer：无它，两次 invoke 互不相识；有它，同 thread_id 共享状态：")
    agent = create_agent(
        model=FakeToolChatModel(messages=iter([
            AIMessage(content="已记住你的城市是北京。"),
            AIMessage(content="你上一轮说住在北京。"),
        ])),
        tools=[],
        system_prompt="记忆助手",
        checkpointer=InMemorySaver(),  # 内存版：教学/测试用，生产换持久化 Saver
    )
    cfg = {"configurable": {"thread_id": "user-42"}}
    r1 = agent.invoke({"messages": [HumanMessage(content="我住在北京")]}, cfg)
    print(f"    第 1 轮回答：{r1['messages'][-1].content}")
    r2 = agent.invoke({"messages": [HumanMessage(content="我刚才说住哪？")]}, cfg)
    print(f"    第 2 轮回答：{r2['messages'][-1].content}")
    snap = agent.get_state(cfg)
    print(f"    get_state 快照：{len(snap.values['messages'])} 条消息（2 人问 + 2 答都在）")
    print("    → 裸 SDK 的'历史管理'（ch27 手动截断/拼 messages）框架做成了线程状态；")
    print("      thread_id 换一个，就是另一个用户的会话（多租户隔离从配置开始）。")

    print("\n[2] stream 三模式（无工具 agent，脚本 1 条回答）：")
    stream_agent = create_agent(
        model=FakeToolChatModel(messages=iter([AIMessage(content="完整回答文本")]*3)),
        tools=[], system_prompt="x",
    )
    for state in stream_agent.stream({"messages": [HumanMessage(content="hi")]}, stream_mode="values"):
        pass  # values：每步推整个状态
    print(f"    values   ：最后一步 state.messages[-1] = {state['messages'][-1].content!r}")
    for update in stream_agent.stream({"messages": [HumanMessage(content="hi")]}, stream_mode="updates"):
        print(f"    updates  ：节点 {list(update.keys())}（增量：该节点写入的状态）")
    msg_chunks = [
        str(c.content)
        for c, _meta in stream_agent.stream({"messages": [HumanMessage(content="hi")]},
                                            stream_mode="messages")
        if str(c.content)
    ]
    print(f"    messages ：逐 token chunk = {msg_chunks}")

    print("\n[3] astream（异步流式）——SSE 接口的素材：")
    asyncio.run(astream_demo())
    print("    → FastAPI 里把每个 chunk 包装成 SSE 事件下发即可（ch17 的 StreamingResponse；")
    print("      真实模型上 chunk 是 token 级，前端打字机效果由此而来）。")


async def astream_demo() -> None:
    agent = create_agent(
        model=FakeToolChatModel(messages=iter([AIMessage(content="异步流式回答")])),
        tools=[], system_prompt="x",
    )
    chunks: list[str] = []
    async for chunk, meta in agent.astream(
        {"messages": [HumanMessage(content="hi")]}, stream_mode="messages"
    ):
        if str(chunk.content):
            chunks.append(f"{chunk.content}@{meta.get('langgraph_node')}")
    print(f"    收到：{chunks}")


if __name__ == "__main__":
    main()
