# tests/test_ch50.py | ch50 流式与错误处理
"""覆盖：stream 三种模式的输出形态、RetryPolicy 重试成功/耗尽、错误即数据降级。"""
from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy

from examples.ch50_streaming_errors.ex_50_01_stream_modes import build
from examples.ch50_streaming_errors.ex_50_02_retry_and_errors import (
    JobState,
    make_flaky_node,
)


def test_stream_values_full_snapshots() -> None:
    """values 模式：每帧都是全量快照，且逐帧增长。"""
    frames = list(build().stream({"messages": []}, stream_mode="values"))
    sizes = [len(f["messages"]) for f in frames]
    assert sizes == [0, 1, 2]


def test_stream_updates_per_node() -> None:
    """updates 模式：每帧是 {节点名: 部分更新}。"""
    updates = list(build().stream({"messages": []}, stream_mode="updates"))
    assert [list(u.keys())[0] for u in updates] == ["A", "B"]
    assert updates[0]["A"]["messages"][0].content == "A 节点的回答"


def test_stream_messages_mode() -> None:
    """messages 模式：产出 (消息, 元数据) 对，元数据带来源节点。"""
    pairs = list(build().stream({"messages": []}, stream_mode="messages"))
    contents = [m.content for m, _ in pairs]
    assert contents == ["A 节点的回答", "B 节点的回答"]
    assert pairs[0][1]["langgraph_node"] == "A"


def test_retry_policy_recovers() -> None:
    """正常路径：抖动 2 次 + max_attempts=3 → 第 3 次成功。"""
    g = StateGraph(JobState)
    g.add_node("flaky", make_flaky_node(2, "flaky"),
               retry_policy=RetryPolicy(retry_on=ValueError, max_attempts=3,
                                        initial_interval=0.01, jitter=False))
    g.add_edge(START, "flaky"); g.add_edge("flaky", END)
    r = g.compile().invoke({"result": "", "errors": []})
    assert r["result"] == "flaky 成功（第 3 次尝试）"


def test_retry_policy_exhausts_and_raises() -> None:
    """失败路径：重试耗尽后异常冒泡到 invoke 调用方。"""
    g = StateGraph(JobState)
    g.add_node("flaky", make_flaky_node(99, "hopeless"),
               retry_policy=RetryPolicy(retry_on=ValueError, max_attempts=2,
                                        initial_interval=0.01, jitter=False))
    g.add_edge(START, "flaky"); g.add_edge("flaky", END)
    with pytest.raises(ValueError, match="hopeless"):
        g.compile().invoke({"result": "", "errors": []})


def test_error_as_data_fallback() -> None:
    """错误即数据：节点内捕获写状态，条件边路由到降级分支。"""
    def resilient(state: JobState) -> dict:
        try:
            raise TimeoutError("下游 3 秒未响应")
        except TimeoutError as e:
            return {"errors": [f"resilient 捕获 {type(e).__name__}: {e}"], "result": ""}

    def fallback(state: JobState) -> dict:
        return {"result": "降级：返回缓存的上次结果"}

    g = StateGraph(JobState)
    g.add_node("resilient", resilient)
    g.add_node("fallback", fallback)
    g.add_edge(START, "resilient")
    g.add_conditional_edges("resilient",
                            lambda s: "fallback" if s["errors"] else END,
                            {"fallback": "fallback", END: END})
    g.add_edge("fallback", END)
    r = g.compile().invoke({"result": "", "errors": []})
    assert r["result"].startswith("降级")
    assert "TimeoutError" in r["errors"][0]


def test_retry_policy_defaults_documented() -> None:
    """API 事实锁定（1.2.16）：默认参数与 FACTS 一致，防止教材写错。"""
    p = RetryPolicy()
    assert p.max_attempts == 3 and p.initial_interval == 0.5
    assert p.backoff_factor == 2.0 and p.jitter is True
