# EX-44-03 | 内置 MessagesState：对话状态的"标准底座" | 运行: python3 examples/ch44_minimal_graph/ex_44_03_messages_state.py
"""完整可运行：用 langgraph.graph.MessagesState（1.2.16 实测可用）搭一个两轮对话图。

要点：
  1) MessagesState 自带 messages: Annotated[list[AnyMessage], add_messages]，不用手写 reducer；
  2) 节点返回字符串/元组也可以，add_messages 会自动包装成对应消息类型；
  3) invoke 的输入既可用 HumanMessage 对象，也可用 dict（role/content）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from langgraph.graph import END, START, MessagesState, StateGraph  # noqa: E402
from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402


def echo_node(state: MessagesState) -> dict:
    """"客服"节点：把用户最后一句复述一遍（真实系统里这里是 LLM 调用，见 ch46）。"""
    last = state["messages"][-1]
    return {"messages": AIMessage(content=f"收到：{last.content}")}


def check_node(state: MessagesState) -> dict:
    """质检节点：统计轮次，演示状态里已有完整历史。"""
    turns = sum(1 for m in state["messages"] if isinstance(m, HumanMessage))
    return {"messages": AIMessage(content=f"（质检：当前 {turns} 轮提问）")}


def main() -> None:
    g = StateGraph(MessagesState)
    g.add_node("echo", echo_node)
    g.add_node("check", check_node)
    g.add_edge(START, "echo"); g.add_edge("echo", "check"); g.add_edge("check", END)
    app = g.compile()

    # 输入用 dict（OpenAI 风格），add_messages 自动转 HumanMessage
    r1 = app.invoke({"messages": [{"role": "user", "content": "查一下订单"}]})
    print("第一轮消息序列：")
    for m in r1["messages"]:
        print(f"  {type(m).__name__:<12} {m.content}")

    # 输入用 HumanMessage 对象，效果等价
    r2 = app.invoke({"messages": [HumanMessage(content="再查一个订单")]})
    print("第二轮消息序列（注意：每次 invoke 都从输入重新开始，历史要靠 ch47 的 checkpointer）：")
    for m in r2["messages"]:
        print(f"  {type(m).__name__:<12} {m.content}")


if __name__ == "__main__":
    main()
