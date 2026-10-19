# EX-51-01 | 测试 LangGraph 的四种姿势（演示文件，pytest 版见 tests/test_ch51.py） | 运行: python3 examples/ch51_graph_testing/ex_51_01_graph_testing.py
"""完整可运行：把 ch51 的测试套路浓缩成一个可执行清单。

  1) 单节点测试：节点就是"输入状态 → 部分更新"的纯函数，直接调用断言；
  2) 整图测试：invoke 后断言最终状态；
  3) 快照测试：get_state() 断言 StateSnapshot 的 next/values/metadata；
  4) Mock LLM 注入：模型节点工厂接收 llm 参数——测试用脚本化 MockLLM，
     生产传 get_llm()。控制流测试不依赖真实模型。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, Any, Callable, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402
from langgraph.graph import END, START, StateGraph  # noqa: E402
from langgraph.types import Command, interrupt  # noqa: E402
from examples.common.llm_client import MockLLM  # noqa: E402


def merge_list(a: list[str] | None, b: list[str] | None) -> list[str]:
    return (a or []) + (b or [])


class RiskState(TypedDict):
    text: str
    findings: Annotated[list[str], merge_list]
    action: str


def detect(state: RiskState) -> dict:
    findings = [w for w in ("身份证", "银行卡", "密码") if w in state["text"]]
    return {"findings": findings}


def classify_llm_node_factory(llm: Any) -> Callable[[RiskState], dict]:
    """依赖注入：模型节点由外部传入 llm（生产 get_llm() / 测试脚本 Mock）。"""

    def node(state: RiskState) -> dict:
        r = llm.chat([{"role": "user", "content": f"风险等级? {state['text']}"}])
        action = "block" if "block=true" in r.content else "allow"
        return {"action": action}

    return node


def gate(state: RiskState) -> dict:
    decision = interrupt("高风险操作等待审批")
    return {"action": "executed" if decision else "rejected"}


def build_app(llm: Any):
    g = StateGraph(RiskState)
    g.add_node("detect", detect)
    g.add_node("classify", classify_llm_node_factory(llm))
    g.add_node("gate", gate)
    g.add_edge(START, "detect"); g.add_edge("detect", "classify")
    g.add_edge("classify", "gate"); g.add_edge("gate", END)
    return g.compile(checkpointer=InMemorySaver())


def main() -> None:
    # 1) 单节点测试：纯函数直调
    out = detect({"text": "含身份证号", "findings": [], "action": ""})
    assert out == {"findings": ["身份证"]}, out
    print("1) 单节点测试　　　：PASS —— 节点是纯函数，输入 dict 输出 dict")

    # 2) 整图测试（Mock 注入：脚本让模型永远返回 block=true）
    scripted = MockLLM(script=[{"content": "风险评估 block=true"}])
    app = build_app(scripted)
    cfg_t = {"configurable": {"thread_id": "t"}}
    paused = app.invoke({"text": "查我的银行卡", "findings": [], "action": ""}, cfg_t)
    assert "__interrupt__" in paused, paused          # 整图测试也要处理暂停
    final = app.invoke(Command(resume=True), cfg_t)
    assert final["findings"] == ["银行卡"] and final["action"] == "executed", final
    print("2) 整图测试　　　　：PASS —— 注入脚本 Mock + 恢复，终点状态确定")

    # 3) 快照测试
    snap = app.get_state({"configurable": {"thread_id": "t"}})
    assert snap.next == () and snap.values["action"] == "executed"
    assert snap.metadata is not None and "step" in snap.metadata
    print("3) 快照测试　　　　：PASS —— next/values/metadata 全部可断言")

    # 4) Mock 注入 + interrupt：先断言暂停，再恢复
    app2 = build_app(MockLLM(script=[{"content": "block=true"}]))
    cfg2 = {"configurable": {"thread_id": "t2"}}
    r = app2.invoke({"text": "查我的银行卡", "findings": [], "action": ""}, cfg2)
    assert "__interrupt__" in r and app2.get_state(cfg2).next == ("gate",)
    r2 = app2.invoke(Command(resume=True), cfg2)
    assert r2["action"] == "executed"
    print("4) interrupt 流测试：PASS —— 暂停/恢复都可脚本化断言")

    print("\n以上断言在 tests/test_ch51.py 里以 pytest 形式再次出现并纳入全书回归。")


if __name__ == "__main__":
    main()
