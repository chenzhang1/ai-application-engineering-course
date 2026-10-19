# EX-50-01 | stream 三种模式：values / updates / messages | 运行: python3 examples/ch50_streaming_errors/ex_50_01_stream_modes.py
"""完整可运行：同一个两节点图，用三种 stream_mode 观察输出的粒度差异。

  values   ：每个超步后输出"整份当前状态"（全量快照，适合 UI 展示最新态）；
  updates  ：每个节点完成后输出"谁写了什么"（增量，适合审计/日志）；
  messages ：输出图内部产生的 LLM 消息（本图节点直接返回 AIMessage，
             因此每条消息整体出现一次；若节点内是真实模型的流式调用，
             这里就是逐 token 的 AIMessageChunk —— 见教材说明）。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from langchain_core.messages import AIMessage  # noqa: E402
from langgraph.graph import END, START, StateGraph, add_messages  # noqa: E402


class ChatState(TypedDict):
    messages: Annotated[list, add_messages]


def node_a(state: ChatState) -> dict:
    return {"messages": [AIMessage(content="A 节点的回答")]}


def node_b(state: ChatState) -> dict:
    return {"messages": [AIMessage(content="B 节点的回答")]}


def build():
    g = StateGraph(ChatState)
    g.add_node("A", node_a); g.add_node("B", node_b)
    g.add_edge(START, "A"); g.add_edge("A", "B"); g.add_edge("B", END)
    return g.compile()


def main() -> None:
    app = build()
    inputs = {"messages": []}

    print("── stream_mode='values'：全量快照 ──")
    for i, snap in enumerate(app.stream(inputs, stream_mode="values"), 1):
        print(f"  第{i}帧：{[m.content for m in snap['messages']]}")

    print("── stream_mode='updates'：增量写入 ──")
    for upd in app.stream(inputs, stream_mode="updates"):
        for node, patch in upd.items():
            print(f"  节点 {node} 写入：{[m.content for m in patch['messages']]}")

    print("── stream_mode='messages'：LLM 消息流 ──")
    for msg, meta in app.stream(inputs, stream_mode="messages"):
        print(f"  消息 {type(msg).__name__}({msg.content!r}) 来自节点 {meta.get('langgraph_node')}")


if __name__ == "__main__":
    main()
