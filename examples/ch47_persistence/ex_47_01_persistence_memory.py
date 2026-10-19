# EX-47-01 | InMemorySaver + thread_id：同一会话的记忆（主线示例 4：持久化） | 运行: python3 examples/ch47_persistence/ex_47_01_persistence_memory.py
"""完整可运行：checkpointer 让图"记得"每个 thread 上次跑到哪。

三个观察点：
  1) 同一个 thread_id 连续两次 invoke，第二次能看到第一次的消息（对话记忆）；
  2) 换一个 thread_id，状态互不干扰（会话隔离）；
  3) get_state / get_state_history 查看当前快照与检查点历史。
"""
from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402
from langgraph.graph import END, START, MessagesState, StateGraph  # noqa: E402
from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402


def support_node(state: MessagesState) -> dict:
    """"客服"节点：Mock 下确定性回复；这里的关键是验证状态演进与恢复。"""
    last = state["messages"][-1].content
    return {"messages": AIMessage(content=f"已受理：{last}（{datetime.now():%H:%M:%S}）")}


def build_app() -> Any:  # noqa: F821
    g = StateGraph(MessagesState)
    g.add_node("support", support_node)
    g.add_edge(START, "support"); g.add_edge("support", END)
    return g.compile(checkpointer=InMemorySaver())


def main() -> None:
    app = build_app()
    cfg_a = {"configurable": {"thread_id": "user-A"}}

    app.invoke({"messages": [HumanMessage(content="第一次提问")]}, cfg_a)
    r2 = app.invoke({"messages": [HumanMessage(content="第二次提问")]}, cfg_a)
    print("thread user-A 第 2 次后消息数：", len(r2["messages"]),
          "← 第一次的历史还在（InMemorySaver 记住了）")

    # 换 thread：全新会话
    cfg_b = {"configurable": {"thread_id": "user-B"}}
    r_b = app.invoke({"messages": [HumanMessage(content="B 的提问")]}, cfg_b)
    print("thread user-B 消息数　　　：", len(r_b["messages"]), "← 与 user-A 互不干扰")

    # 当前快照
    snap = app.get_state(cfg_a)
    print("get_state(user-A).next =", snap.next, "（空元组=已到 END）",
          "| messages 数 =", len(snap.values["messages"]))

    # 检点历史：从新到旧
    hist = list(app.get_state_history(cfg_a))
    print("get_state_history(user-A)：共", len(hist), "个检查点，next 序列（新→旧）：",
          [h.next for h in hist])
    print("每个检查点含：config / values / next / metadata(step) / created_at —— 可回到任意一步，见 EX-47-03")


if __name__ == "__main__":
    main()
