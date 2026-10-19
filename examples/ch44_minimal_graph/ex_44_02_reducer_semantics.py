# EX-44-02 | reducer 语义实验：覆盖 vs 追加，add_messages 到底做了什么 | 运行: python3 examples/ch44_minimal_graph/ex_44_02_reducer_semantics.py
"""完整可运行：同一个更新动作，在"无 reducer"与"add_messages reducer"下的不同命运。

三个实验：
  A. 无 reducer 字段：后写覆盖先写（丢失历史）；
  B. add_messages 字段：消息追加（自动转类型、同 id 覆盖——这是"更新"而非"重复"）；
  C. 自定义 reducer：追加 + 去重，业务可自定合并策略。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from langgraph.graph import END, START, StateGraph, add_messages  # noqa: E402
from langchain_core.messages import AIMessage, AnyMessage  # noqa: E402


# --- 实验 A：无 reducer → 覆盖 -------------------------------------------------

class OverwriteState(TypedDict):
    history: list[str]


def step_a1(s: OverwriteState) -> dict:
    return {"history": ["a1"]}


def step_a2(s: OverwriteState) -> dict:
    return {"history": ["a2"]}   # 直接顶掉 ["a1"]


# --- 实验 B：add_messages → 追加（同 id 替换） ---------------------------------

class ChatState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def step_b1(s: ChatState) -> dict:
    return {"messages": [AIMessage(id="m-1", content="第一版回答")]}


def step_b2(s: ChatState) -> dict:
    # 不同 id → 追加为第二条消息
    return {"messages": [AIMessage(id="m-2", content="第二版回答")]}


def step_same_id(s: ChatState) -> dict:
    # 与 step_b1 的 id 相同 → 不是追加，而是"替换"第一条（消息级 upsert）
    return {"messages": [AIMessage(id="m-1", content="同 id 替换版")]}


# --- 实验 C：自定义 reducer（追加 + 去重） -------------------------------------

def merge_unique(left: list[str] | None, right: list[str] | None) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in (left or []) + (right or []):
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


class DedupState(TypedDict):
    events: Annotated[list[str], merge_unique]


def step_c1(s: DedupState) -> dict:
    return {"events": ["tool_call", "tool_call"]}   # 同一超步内的重复也会被合并


def main() -> None:
    # A：覆盖
    ga = StateGraph(OverwriteState)
    ga.add_node("a1", step_a1)
    ga.add_node("a2", step_a2)
    ga.add_edge(START, "a1"); ga.add_edge("a1", "a2"); ga.add_edge("a2", END)
    ra = ga.compile().invoke({"history": ["init"]})
    print("A 无 reducer　：", ra["history"], "← a2 覆盖了 a1，'init' 和 'a1' 都丢了")

    # B：add_messages
    gb = StateGraph(ChatState)
    gb.add_node("b1", step_b1)
    gb.add_node("b2", step_b2)
    gb.add_edge(START, "b1"); gb.add_edge("b1", "b2"); gb.add_edge("b2", END)
    rb = gb.compile().invoke({"messages": []})
    print("B add_messages：", [(m.id, m.content) for m in rb["messages"]],
          "← 自动包装成 AIMessage 并追加")

    # B'：同 id 覆盖（upsert）—— step_same_id 已在模块级定义
    gb2 = StateGraph(ChatState)
    gb2.add_node("b1", step_b1)
    gb2.add_node("b_same", step_same_id)
    gb2.add_edge(START, "b1"); gb2.add_edge("b1", "b_same"); gb2.add_edge("b_same", END)
    rb2 = gb2.compile().invoke({"messages": []})
    print("B' 同 id 更新　：", [(m.id, m.content) for m in rb2["messages"]],
          "← 仍 1 条：id 相同即替换")

    # C：自定义 reducer
    gc = StateGraph(DedupState)
    gc.add_node("c1", step_c1)
    gc.add_edge(START, "c1"); gc.add_edge("c1", END)
    rc = gc.compile().invoke({"events": []})
    print("C 去重 reducer：", rc["events"], "← 合并策略由你定义")


if __name__ == "__main__":
    main()
