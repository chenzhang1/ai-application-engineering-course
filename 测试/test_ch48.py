# 测试/test_ch48.py | ch48 人工介入
"""覆盖：interrupt 暂停与恢复语义、resume=True/False 分叉、副作用重复风险、幂等账本。"""
from __future__ import annotations

from typing import Annotated, TypedDict

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from 示例代码.ch48_human_in_loop.ex_48_01_human_approval import approve, execute, propose
from 示例代码.ch48_human_in_loop.ex_48_02_side_effect_idempotency import (
    build_graph_right,
    build_graph_wrong,
)


class ApprovalState(TypedDict):
    action: str
    approved: bool | None
    trace: Annotated[list[str], lambda a, b: (a or []) + (b or [])]


def _approval_app():
    g = StateGraph(ApprovalState)
    g.add_node("propose", propose)
    g.add_node("approve", approve)
    g.add_node("execute", execute)
    g.add_edge(START, "propose"); g.add_edge("propose", "approve")
    g.add_edge("approve", "execute"); g.add_edge("execute", END)
    return g.compile(checkpointer=InMemorySaver())


def _new_state(action: str) -> ApprovalState:
    return {"action": action, "approved": None, "trace": []}


def test_interrupt_pauses_with_checkpoint() -> None:
    """暂停语义：invoke 返回 __interrupt__，get_state().next 停在审批节点。"""
    app = _approval_app()
    cfg = {"configurable": {"thread_id": "t1"}}
    r = app.invoke(_new_state("restart:db"), cfg)
    assert "__interrupt__" in r
    assert r["__interrupt__"][0].value["question"].startswith("是否批准")
    assert app.get_state(cfg).next == ("approve",)


def test_resume_true_executes_false_rejects() -> None:
    """恢复分叉：同一个暂停点，resume 值决定后续走执行还是拒绝分支。"""
    app = _approval_app()
    cfg1 = {"configurable": {"thread_id": "ok"}}
    app.invoke(_new_state("restart:db"), cfg1)
    ok = app.invoke(Command(resume=True), cfg1)
    assert ok["approved"] is True and any(t.startswith("execute:") for t in ok["trace"])

    cfg2 = {"configurable": {"thread_id": "no"}}
    app.invoke(_new_state("restart:db"), cfg2)
    no = app.invoke(Command(resume=False), cfg2)
    assert no["approved"] is False and "rejected:已拒绝，不执行" in no["trace"]


def test_side_effect_before_interrupt_runs_twice() -> None:
    """反面教材：副作用写在 interrupt 之前 → 恢复时节点重跑导致执行 2 次。"""
    log: list[str] = []
    app = build_graph_wrong(log)
    cfg = {"configurable": {"thread_id": "w"}}
    app.invoke({"action_id": "sms-1", "done": False, "trace": []}, cfg)
    assert len(log) == 1
    app.invoke(Command(resume=True), cfg)
    assert len(log) == 2  # 重复执行！


def test_idempotent_ledger_guards_replay() -> None:
    """幂等账本：从中断检查点重放时，账本命中 → 副作用恰好一次。"""
    log: list[str] = []
    app = build_graph_right(log)
    cfg = {"configurable": {"thread_id": "r"}}
    app.invoke({"action_id": "sms-2", "done": False, "trace": []}, cfg)
    app.invoke(Command(resume=True), cfg)
    assert len(log) == 1

    # 模拟"执行后崩溃、从检查点重放"：回到 next=('node',) 的检查点再恢复
    cp = next(h for h in app.get_state_history(cfg) if h.next == ("node",))
    old = {"configurable": {"thread_id": "r",
                            "checkpoint_id": cp.config["configurable"]["checkpoint_id"]}}
    r2 = app.invoke(Command(resume=True), old)
    assert len(log) == 1                       # 没有第二次副作用
    assert "idempotent-skip:sms-2" in r2["trace"]


def test_invoke_without_thread_id_fails() -> None:
    """非法用法：带 checkpointer 的图必须提供 thread_id（1.2.16 实测报错文案）。"""
    app = _approval_app()
    with pytest.raises(ValueError) as ei:
        app.invoke(_new_state("x"), {})          # 没有 configurable.thread_id
    assert "thread_id" in str(ei.value)
