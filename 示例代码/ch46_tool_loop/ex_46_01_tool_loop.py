# EX-46-01 | 工具调用循环：模型节点与工具节点分离（主线示例 3：工具循环） | 运行: python3 示例代码/ch46_tool_loop/ex_46_01_tool_loop.py
"""完整可运行：bind_tools 接口形态 + ToolNode 执行 + 消息状态演进，Mock 驱动两轮工具循环。

架构原则（全书 LangGraph 章约定）：
  - "模型节点"（agent）只负责决定调什么工具：内部用 get_llm()（LLM_MODE=mock 默认），
    把 ChatResult 转成 AIMessage(tool_calls=...)——这就是 bind_tools 在真实模型上的
    接口形态（ch24 已实测），Mock 模式下由脚本/规则决定工具调用，控制流确定可复现；
  - "工具节点"（tools）用 langgraph.prebuilt.ToolNode 执行真函数（不依赖模型）；
  - 条件边判断最后一条消息有没有 tool_calls：有 → tools，无 → END。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from langchain_core.messages import (  # noqa: E402
    AIMessage,
    AnyMessage,
    HumanMessage,
    ToolMessage,
)
from langgraph.graph import END, START, MessagesState, StateGraph  # noqa: E402
from langgraph.prebuilt import ToolNode  # noqa: E402
from 示例代码.公共.llm_client import ChatResult, get_llm  # noqa: E402


# ---------------------------------------------------------------------------
# 工具（真函数，离线确定）
# ---------------------------------------------------------------------------


def query_order_status(order_id: str) -> str:
    """查订单状态（只读）。返回 JSON 字符串——真实工具也建议返回文本化结果。"""
    return json.dumps({"order_id": order_id, "status": "paid", "amount": 129.5},
                      ensure_ascii=False)


def query_refund_policy(order_type: str) -> str:
    """查退款政策（只读）。"""
    return json.dumps({"order_type": order_type, "policy": "7 天无理由退款"},
                      ensure_ascii=False)


TOOLS = [query_order_status, query_refund_policy]


# ---------------------------------------------------------------------------
# 模型节点：Mock → AIMessage 的适配层
# ---------------------------------------------------------------------------


def to_ai_message(result: ChatResult) -> AIMessage:
    """把全书统一的 ChatResult 转成 LangChain 消息。

    tool_calls 用 dict 形态 {name, args, id, type}——langchain-core 1.x 的
    AIMessage 构造参数（已实测），与真实 bind_tools 返回的 AIMessage 同构。
    """
    return AIMessage(
        content=result.content,
        tool_calls=[
            {"name": tc.name, "args": tc.arguments, "id": tc.id, "type": "tool_call"}
            for tc in result.tool_calls
        ],
    )


def to_openai_style(messages: list[AnyMessage]) -> list[dict[str, Any]]:
    """LangChain 消息 → llm_client 的 OpenAI 风格 dict（全书统一消息格式）。"""
    out: list[dict[str, Any]] = []
    for m in messages:
        if isinstance(m, HumanMessage):
            out.append({"role": "user", "content": m.content})
        elif isinstance(m, AIMessage):
            item: dict[str, Any] = {"role": "assistant", "content": m.content or ""}
            if m.tool_calls:
                item["tool_calls"] = [
                    {"id": tc["id"], "type": "function",
                     "function": {"name": tc["name"],
                                  "arguments": json.dumps(tc["args"], ensure_ascii=False)}}
                    for tc in m.tool_calls
                ]
            out.append(item)
        elif isinstance(m, ToolMessage):
            out.append({"role": "tool", "tool_call_id": m.tool_call_id, "content": m.content})
    return out


def make_agent_node(llm: Any):
    """模型节点工厂：闭包持有同一个 llm 实例（脚本模式的游标跨轮次推进）。"""

    def agent(state: MessagesState) -> dict:
        result = llm.chat(to_openai_style(state["messages"]))
        return {"messages": [to_ai_message(result)]}

    return agent


def route_after_agent(state: MessagesState) -> str:
    """条件边：最后一条消息带 tool_calls → 去工具节点；否则结束。"""
    last = state["messages"][-1]
    return "tools" if getattr(last, "tool_calls", None) else END


def main() -> None:
    # MockLLM 脚本模式：第 1 次调用→请求查订单；第 2 次→请求查政策；第 3 次→总结作答
    llm = get_llm(script=[
        {"tool_calls": [{"id": "call_001", "name": "query_order_status",
                         "arguments": {"order_id": "ORD-1001"}}]},
        {"tool_calls": [{"id": "call_002", "name": "query_refund_policy",
                         "arguments": {"order_type": "physical"}}]},
        {"content": "订单 ORD-1001 已支付；按政策支持 7 天无理由退款，可直接申请。"},
    ])

    g = StateGraph(MessagesState)
    g.add_node("agent", make_agent_node(llm))
    g.add_node("tools", ToolNode(TOOLS))      # 工具节点：执行真函数
    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", route_after_agent,
                            {"tools": "tools", END: END})
    g.add_edge("tools", "agent")              # 工具结果回给模型 → 形成循环
    app = g.compile()

    r = app.invoke({"messages": [HumanMessage(content="ORD-1001 想退款，能退吗？")]})
    print("消息状态演进（%d 条）：" % len(r["messages"]))
    for i, m in enumerate(r["messages"], 1):
        desc = m.content if m.content else "<空，发起工具调用>"
        print(f"  {i}. {type(m).__name__:<12} {str(desc)[:44]}")
        for tc in getattr(m, "tool_calls", None) or []:
            print(f"     └─ 请求工具 {tc['name']} args={tc['args']}")
        if isinstance(m, ToolMessage):
            print(f"     └─ 工具结果回传（tool_call_id={m.tool_call_id}）")


if __name__ == "__main__":
    main()
