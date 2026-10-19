# EX-45-01 | 条件路由：conditional edges + path_map（主线示例 2：条件分支） | 运行: python3 examples/ch45_conditional_routing/ex_45_01_conditional_route.py
"""完整可运行：一个分类节点 + 三个业务节点，按分类结果分流。

关键点：
  1) add_conditional_edges(源节点, 路由函数, path_map)——路由函数返回"路由值"，
     path_map 把路由值映射成节点名；返回值也可以直接是节点名（不用 path_map）；
  2) 分类节点用 get_llm().chat_structured 演示"模型分类"接口形态；Mock 模式下
     分类值从输入文本的 key=value 解析（全书 Mock 约定，见 ch24），控制流与真实
     模式完全一致——换 LLM_MODE=real 时只换模型，不换图。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from langgraph.graph import END, START, StateGraph  # noqa: E402
from examples.common.llm_client import get_llm  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402


class TicketClass(BaseModel):
    """分类结果 schema（结构化输出，ch24）。"""

    category: str = Field(default="general", description="billing/tech/general")
    urgent: bool = Field(default=False, description="是否加急")


class TicketState(TypedDict):
    text: str
    category: str
    urgent: bool
    trace: Annotated[list[str], lambda a, b: (a or []) + (b or [])]


def classify(state: TicketState) -> dict:
    """模型节点：结构化输出分类结果。Mock 从输入 key=value 解析，real 走 response_format。"""
    llm = get_llm()
    result: TicketClass = llm.chat_structured(
        [
            {"role": "system", "content": "你是工单分类器，只输出结构化结果。"},
            {"role": "user", "content": f"工单：{state['text']}"},
        ],
        TicketClass,
    )
    return {"category": result.category, "urgent": result.urgent,
            "trace": [f"classify:{result.category}"]}


def billing(state: TicketState) -> dict:
    return {"trace": ["billing:账务处理"]}


def tech(state: TicketState) -> dict:
    return {"trace": ["tech:技术排查"]}


def general(state: TicketState) -> dict:
    return {"trace": ["general:通用应答"]}


def route_by_category(state: TicketState) -> str:
    """路由函数：读状态，返回路由值（这里直接等于节点名，可省 path_map）。"""
    return state["category"]


def main() -> None:
    g = StateGraph(TicketState)
    g.add_node("classify", classify)
    g.add_node("billing", billing)
    g.add_node("tech", tech)
    g.add_node("general", general)

    g.add_edge(START, "classify")
    g.add_conditional_edges(
        "classify", route_by_category,
        {"billing": "billing", "tech": "tech", "general": "general"},  # path_map
    )
    for leaf in ("billing", "tech", "general"):
        g.add_edge(leaf, END)

    app = g.compile()
    tickets = [
        "发票抬头开错了 category=billing urgent=true",   # Mock：key=value 决定分类
        "App 报错闪退 category=tech",
        "你们几点上班 category=general",
    ]
    for t in tickets:
        r = app.invoke({"text": t, "category": "", "urgent": False, "trace": []})
        print(f"{t.split()[0]:<10} -> trace={r['trace']} urgent={r['urgent']}")


if __name__ == "__main__":
    main()
