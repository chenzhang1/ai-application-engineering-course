# EX-42-01 | create_agent 最小工具循环：框架替你做了什么 | 运行: python3 示例代码/ch42_lc_agent/ex_42_01_agent_minimal.py
"""完整可运行（离线，Fake 脚本驱动）：
用 langchain 1.4.6 的 create_agent（当前推荐方式）跑通"模型点名工具→执行→回传→最终回答"，
逐条打印消息序列；对照 EX-24-03 裸 SDK 手写的六步循环，逐项标出框架接管的步骤。

为什么需要 FakeToolChatModel 子类：create_agent 会调用 model.bind_tools(tools)，
而 GenericFakeChatModel 没实现 bind_tools（真实报错见本文件 [0]）——
这本身就是教学点：绑定工具是"模型与框架的契约"，Fake 模型要显式声明支持。
"""
from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

from langchain.agents import create_agent
from langchain_core.language_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool


class FakeToolChatModel(GenericFakeChatModel):
    """教学用假模型：按脚本顺序吐 AIMessage（官方测试模型 + bind_tools 支持）。

    bind_tools 返回 self：表示"工具已声明"（真实模型会在此把工具 schema 注入请求）。
    """

    bind_calls: list[list[str]] = []

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> Any:
        self.bind_calls.append([getattr(t, "name", str(t)) for t in tools])
        return self


@tool
def get_weather(city: str) -> dict:
    """查询指定城市当日天气。"""
    db = {"北京": {"weather": "晴", "temp": 26}}
    return {"city": city, **db[city]}


def main() -> None:
    print("[0] 不实现 bind_tools 会怎样（真实报错，42.3 详述）：")
    naked = GenericFakeChatModel(messages=iter([AIMessage(content="x")]))
    try:
        naked.bind_tools([get_weather])
    except NotImplementedError as e:
        print(f"    NotImplementedError（异常消息为空——基类只声明契约，不解释）：{e!r}")

    print("\n[1] create_agent（当前推荐方式，签名含 model/tools/system_prompt/middleware/...")
    print("    response_format/state_schema/checkpointer 等——运行记录见 part07.md）：")
    script = iter([
        AIMessage(content="", tool_calls=[
            {"id": "call_001", "name": "get_weather", "args": {"city": "北京"}, "type": "tool_call"}]),
        AIMessage(content="北京今天晴，26℃，适合出行。"),
    ])
    model = FakeToolChatModel(messages=script)
    agent = create_agent(
        model=model,
        tools=[get_weather],
        system_prompt="你是天气助手，回答简洁。",
    )
    print(f"    返回类型 = {type(agent).__name__}（一个 LangGraph 编译图，第八部分的主角）")
    result = agent.invoke({"messages": [HumanMessage(content="北京天气怎么样？")]})
    print(f"    state keys = {list(result.keys())}")
    print(f"    bind_tools 调用记录 = {model.bind_calls}（每次模型节点执行都会绑定一次）")

    print("\n[2] 最终消息序列（框架维护的对话状态）：")
    for m in result["messages"]:
        tc = getattr(m, "tool_calls", None)
        extra = f" tool_calls={[c['name'] for c in tc]}" if tc else ""
        if type(m).__name__ == "ToolMessage":
            extra = f" tool_call_id={m.tool_call_id}"
        print(f"    {type(m).__name__:<12} {str(m.content)[:44]}{extra}")

    print("\n[3] 对照 EX-24-03（裸 SDK 六步手写循环）——框架替你做了什么：")
    print("    ① 声明工具        ：@tool 自动生成 schema，create_agent 自动 bind_tools（本例 bind 调用了 2 次）")
    print("    ② 解析 tool_calls ：AIMessage.tool_calls 已是结构化 dict（裸 SDK 要 json.loads arguments）")
    print("    ③ assistant 回写  ：框架自动把'发起调用的消息'写回状态（裸 SDK 手动 append，最易漏）")
    print("    ④ 执行工具        ：框架按 name 路由并调用（裸 SDK 手写 if/elif 分发）")
    print("    ⑤ tool 消息回传   ：框架生成 ToolMessage 并配对 tool_call_id（裸 SDK 手动构造 dict）")
    print("    ⑥ 循环与终止      ：框架判断'模型不再要点名工具'才停（裸 SDK 手写 while + finish_reason 判断）")
    print("    你仍然负责的：工具实现本身、参数权限校验、工具超时/幂等（ch54 工具治理）。")


if __name__ == "__main__":
    main()
