# EX-47-02 | SqliteSaver：把检查点落盘，"新进程"接续旧会话 | 运行: python3 示例代码/ch47_persistence/ex_47_02_persistence_sqlite.py
"""完整可运行（需 langgraph-checkpoint-sqlite，本书实测版本 3.1.2）。

InMemorySaver 进程一死记忆就没了。SqliteSaver 把检查点写进 SQLite 文件——
本例在同一个进程里模拟"两个进程"：第一个 app 写入，第二个 app（重新编译、
重新打开数据库）直接读到旧 thread 的状态并继续对话。真实多进程部署时，
这就是"服务重启后会话不丢"的机制。
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from langchain_core.messages import HumanMessage  # noqa: E402
from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402  (对照用，可删)
from langgraph.checkpoint.sqlite import SqliteSaver  # noqa: E402
from langgraph.graph import END, START, MessagesState, StateGraph  # noqa: E402


def support_node(state: MessagesState) -> dict:
    from langchain_core.messages import AIMessage

    last = state["messages"][-1].content
    return {"messages": [AIMessage(content=f"已受理：{last}")]}


def build_graph() -> StateGraph:
    g = StateGraph(MessagesState)
    g.add_node("support", support_node)
    g.add_edge(START, "support"); g.add_edge("support", END)
    return g


def main() -> None:
    db_path = Path(tempfile.mkdtemp()) / "checkpoints.db"
    cfg = {"configurable": {"thread_id": "incident-42"}}

    # ——"进程 1"：写入两轮对话——
    with SqliteSaver.from_conn_string(str(db_path)) as saver1:
        app1 = build_graph().compile(checkpointer=saver1)
        app1.invoke({"messages": [HumanMessage(content="订单超时未发货")]}, cfg)
        app1.invoke({"messages": [HumanMessage(content="已经 3 天了")]}, cfg)
        print("进程 1 完成 2 轮对话，检查点已写入", db_path.name)

    # ——"进程 2"：重新编译 + 重新打开同一个库文件——
    with SqliteSaver.from_conn_string(str(db_path)) as saver2:
        app2 = build_graph().compile(checkpointer=saver2)
        snap = app2.get_state(cfg)
        print("进程 2 get_state 读到 messages 数：", len(snap.values["messages"]))
        r = app2.invoke({"messages": [HumanMessage(content="继续跟进这个单子")]}, cfg)
        print("进程 2 继续对话后 messages 数：", len(r["messages"]),
              "← 历史从 SQLite 恢复，会话无缝接续")

    print("对照：InMemorySaver 停在内存（进程重启即丢）；SqliteSaver/PostgresSaver 落盘可恢复。")


if __name__ == "__main__":
    main()
