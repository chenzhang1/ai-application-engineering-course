# EX-39-03 | 工具的完整生命周期：schema→渲染→调用→错误→Agent 中的恢复 | 运行: python3 示例代码/ch39_lc_tools/ex_39_03_tool_render.py
"""完整可运行（离线）：
[1] 多工具 + render_text_description_and_args：模型菜单的真实形态；
[2] @tool 的 return_direct / parse_docstring 选项；
[3] 在 create_agent 循环里验证：工具抛 ToolException 后，handle_tool_error 让循环继续
    （错误变成 ToolMessage 回传模型）——这是 39 章与 42 章的接缝。
"""
from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

from langchain.agents import create_agent
from langchain_core.language_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import ToolException, render_text_description_and_args, tool


class FakeToolChatModel(GenericFakeChatModel):
    """GenericFakeChatModel + bind_tools（42.3 详解为什么需要这个子类）。"""

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> Any:
        return self


@tool
def query_order(order_id: str) -> dict:
    """按订单号查询订单状态。"""
    return {"order_id": order_id, "status": "已签收"}


@tool(return_direct=True)  # return_direct=True：结果不经模型复述，直接返回给调用方
def risk_flag(user_id: str) -> bool:
    """标记高危用户（演示 return_direct：结果直接透出）。"""
    return user_id.startswith("R")


@tool
def divide(a: int, b: int) -> float:
    """两数相除。"""
    if b == 0:
        raise ToolException("除数不能为 0，请换一个除数")
    return a / b


def main() -> None:
    print("[1] render_text_description_and_args（模型能看到的'工具菜单'）：")
    print(render_text_description_and_args([query_order, risk_flag, divide]))

    print("\n[2] return_direct 语义（属性核实）：")
    print(f"    query_order.return_direct = {query_order.return_direct}")
    print(f"    risk_flag.return_direct   = {risk_flag.return_direct}")
    print("    → True 的工具结果会原样成为最终答案（适合计算器/查分类等'答案即结果'场景）")

    print("\n[3] create_agent 循环中的工具错误恢复（真实运行，Fake 脚本驱动）：")
    divide.handle_tool_error = "计算失败：除数不能为 0。请换一个非零除数重试，或直接告知用户无法计算。"
    script = iter([
        AIMessage(content="", tool_calls=[
            {"id": "c1", "name": "divide", "args": {"a": 1, "b": 0}, "type": "tool_call"}]),
        AIMessage(content="1 除以 0 在数学上没有定义，工具也返回了同样的错误提示。"),
    ])
    agent = create_agent(model=FakeToolChatModel(messages=script),
                         tools=[query_order, risk_flag, divide], system_prompt="计算助手")
    result = agent.invoke({"messages": [HumanMessage(content="帮我算 1 除以 0")]})
    for m in result["messages"]:
        print(f"    {type(m).__name__:<12} {str(m.content)[:60]}")
    print("    → 第 3 条 ToolMessage 就是 handle_tool_error 的文案：异常没炸掉循环，")
    print("      而是变成'模型读得懂的话'，模型基于它给出最终回答。这就是框架替你做的错误恢复。")


if __name__ == "__main__":
    main()
