# tests/test_ch47.py | ch47 持久化
"""覆盖：thread_id 记忆与隔离、快照/历史、SqliteSaver 跨"进程"恢复、时间旅行重放与分叉。"""
from __future__ import annotations

from typing import Annotated, TypedDict

import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph

from examples.ch47_persistence.ex_47_01_persistence_memory import build_app
from examples.ch47_persistence.ex_47_02_persistence_sqlite import build_graph, support_node
from examples.ch47_persistence.ex_47_03_time_travel import merge_list, step_one, step_two


def test_same_thread_remembers_history() -> None:
    """正常路径：同 thread 两次 invoke，第二次带上第一次的历史。"""
    app = build_app()
    cfg = {"configurable": {"thread_id": "u1"}}
    app.invoke({"messages": [HumanMessage(content="第一次")]}, cfg)
    r2 = app.invoke({"messages": [HumanMessage(content="第二次")]}, cfg)
    assert len(r2["messages"]) == 4  # 2 轮 × (human + ai)


def test_threads_are_isolated() -> None:
    """隔离性：不同 thread_id 互不可见。"""
    app = build_app()
    app.invoke({"messages": [HumanMessage(content="A 的秘密")]},
               {"configurable": {"thread_id": "A"}})
    r_b = app.invoke({"messages": [HumanMessage(content="B 的提问")]},
                     {"configurable": {"thread_id": "B"}})
    assert len(r_b["messages"]) == 2
    assert all("A 的秘密" not in str(m.content) for m in r_b["messages"])


def test_get_state_and_history() -> None:
    """快照：next 为空元组表示已结束；历史按新→旧排列且含 __start__。"""
    app = build_app()
    cfg = {"configurable": {"thread_id": "u2"}}
    app.invoke({"messages": [HumanMessage(content="hi")]}, cfg)
    snap = app.get_state(cfg)
    assert snap.next == () and len(snap.values["messages"]) == 2
    hist = list(app.get_state_history(cfg))
    assert hist[0].next == () and "__start__" in [h.next[0] for h in hist if h.next]


def test_sqlite_saver_survives_new_process(tmp_path) -> None:
    """落盘恢复：新编译的图 + 新连接读到旧 thread 并接续对话。"""
    pytest.importorskip("langgraph.checkpoint.sqlite")
    from langgraph.checkpoint.sqlite import SqliteSaver

    db = str(tmp_path / "cp.db")
    cfg = {"configurable": {"thread_id": "inc-1"}}

    with SqliteSaver.from_conn_string(db) as saver1:
        app1 = build_graph().compile(checkpointer=saver1)
        app1.invoke({"messages": [HumanMessage(content="第一轮")]}, cfg)
        app1.invoke({"messages": [HumanMessage(content="第二轮")]}, cfg)

    with SqliteSaver.from_conn_string(db) as saver2:  # 模拟新进程
        app2 = build_graph().compile(checkpointer=saver2)
        assert len(app2.get_state(cfg).values["messages"]) == 4
        r = app2.invoke({"messages": [HumanMessage(content="第三轮")]}, cfg)
        assert len(r["messages"]) == 6


def test_support_node_is_deterministic() -> None:
    """节点纯函数性：同输入同输出（可独立单测）。"""
    from langchain_core.messages import AIMessage

    out = support_node({"messages": [HumanMessage(content="订单超时")]})
    assert isinstance(out["messages"][0], AIMessage)
    assert "已受理" in out["messages"][0].content and "订单超时" in out["messages"][0].content


def _tt_app():
    """复用示例模块的 merge_list：同一字段名+同一 reducer，避免通道类型冲突。"""
    class S(TypedDict):
        steps: Annotated[list[str], merge_list]

    g = StateGraph(S)
    g.add_node("s1", step_one); g.add_node("s2", step_two)
    g.add_edge(START, "s1"); g.add_edge("s1", "s2"); g.add_edge("s2", END)
    return g.compile(checkpointer=InMemorySaver())


def test_time_travel_replay_and_fork() -> None:
    """时间旅行：重放按原路跑完；分叉以新输入改写状态并产生新分支。"""
    app = _tt_app()
    cfg = {"configurable": {"thread_id": "tt"}}
    app.invoke({"steps": []}, cfg)

    cp = next(h for h in app.get_state_history(cfg) if h.next == ("s2",))
    old = {"configurable": {"thread_id": "tt",
                            "checkpoint_id": cp.config["configurable"]["checkpoint_id"]}}
    replay = app.invoke(None, old)
    assert replay["steps"] == ["step_one", "step_two"]  # 节点写入的值，重放原样追加

    fork = app.invoke({"steps": ["手工修正"]}, old)
    assert fork["steps"][1] == "手工修正" and fork["steps"][-1] == "step_two"
    assert app.get_state(cfg).values["steps"] == fork["steps"]
