# tests/test_ch51.py | ch51 测试 LangGraph
"""覆盖：单节点直调、整图测试（Mock 注入）、StateSnapshot 断言、interrupt 流的脚本化测试。"""
from __future__ import annotations

from langgraph.types import Command

from examples.ch51_graph_testing.ex_51_01_graph_testing import (
    build_app,
    detect,
)
from examples.common.llm_client import MockLLM


def test_node_as_pure_function() -> None:
    """姿势 1：节点是纯函数——直接调用，输入 dict 输出 dict。"""
    assert detect({"text": "含身份证号", "findings": [], "action": ""}) == {"findings": ["身份证"]}
    assert detect({"text": "正常内容", "findings": [], "action": ""}) == {"findings": []}


def test_whole_graph_with_scripted_mock() -> None:
    """姿势 2：注入脚本化 MockLLM，整图终点状态确定可断言。"""
    app = build_app(MockLLM(script=[{"content": "风险评估 block=true"}]))
    cfg = {"configurable": {"thread_id": "t1"}}
    paused = app.invoke({"text": "查我的银行卡", "findings": [], "action": ""}, cfg)
    assert "__interrupt__" in paused
    final = app.invoke(Command(resume=True), cfg)
    assert final["findings"] == ["银行卡"]
    assert final["action"] == "executed"


def test_snapshot_assertions() -> None:
    """姿势 3：StateSnapshot 的 next/values/metadata 全部可断言。"""
    app = build_app(MockLLM(script=[{"content": "block=false"}]))
    cfg = {"configurable": {"thread_id": "t2"}}
    app.invoke({"text": "没事", "findings": [], "action": ""}, cfg)
    # 图在 gate 处暂停：此时快照应"指向前方"
    paused = app.get_state(cfg)
    assert paused.next == ("gate",) and paused.values["action"] == "allow"
    app.invoke(Command(resume=True), cfg)
    snap = app.get_state(cfg)
    assert snap.next == ()
    assert snap.values["action"] == "executed"
    assert snap.metadata is not None and "step" in snap.metadata
    assert snap.created_at is not None


def test_interrupt_pause_then_reject() -> None:
    """姿势 4：interrupt 暂停可断言、Command(resume=False) 走拒绝分支。"""
    app = build_app(MockLLM(script=[{"content": "block=true"}]))
    cfg = {"configurable": {"thread_id": "t3"}}
    r = app.invoke({"text": "查我的银行卡", "findings": [], "action": ""}, cfg)
    assert app.get_state(cfg).next == ("gate",)
    r2 = app.invoke(Command(resume=False), cfg)
    assert r2["action"] == "rejected"


def test_mock_injection_changes_behavior_only() -> None:
    """注入边界：换 Mock 脚本只改 action，控制流（findings）不受影响。"""
    app = build_app(MockLLM(script=[{"content": "no block marker here"}]))
    r = app.invoke({"text": "查我的密码", "findings": [], "action": ""},
                   {"configurable": {"thread_id": "t4"}})
    assert r["findings"] == ["密码"]
    assert r["action"] == "allow"        # 模型没说 block=true → allow（gate 在此暂停）
