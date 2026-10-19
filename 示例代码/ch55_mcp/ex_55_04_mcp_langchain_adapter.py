# EX-55-04 | langchain-mcp-adapters：把 MCP 工具转成 LangChain BaseTool 并接入 create_agent
# 运行: python3 示例代码/ch55_mcp/ex_55_04_mcp_langchain_adapter.py
"""实测（langchain-mcp-adapters 0.3.2 + mcp 1.30.0，2026-10-19 真实运行）：

1. load_mcp_tools(session)：把 MCP 构建工具/list 的结果翻译成 langchain_core.tools.BaseTool
   ——name/description 原样保留，inputSchema 变成 Pydantic 参数 schema；
2. 转换后的工具可以直接 .invoke()（本地直调），也可以交给 create_agent()
   ——模型看到的工具与本地 @tool 写的完全同构（这正是 MCP 的价值）；
3. 用第七部分 EX-42-01 的 FakeToolChatModel 脚本驱动 create_agent，
   验证 MCP 工具在 agent 工具循环里的完整闭环（Mock 模式，离线确定性）。
"""
from __future__ import annotations

import anyio
from collections.abc import Iterator, Sequence
from typing import Any

from langchain_core.language_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import BaseTool

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER_SCRIPT = "示例代码/ch55_mcp/ex_55_02_mcp_stdio_server.py"


class FakeToolChatModel(GenericFakeChatModel):
    """与 EX-42-01 相同的教学假模型（声明 bind_tools 支持）。"""

    bind_calls: list[list[str]] = []

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> Any:
        self.bind_calls.append([getattr(t, "name", str(t)) for t in tools])
        return self


async def run_demo() -> None:
    params = StdioServerParameters(command="python3", args=[SERVER_SCRIPT], env=None)
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            # 1) MCP → LangChain 的"协议翻译层"
            from langchain_mcp_adapters.tools import load_mcp_tools

            tools: list[BaseTool] = await load_mcp_tools(session)
            print("── load_mcp_tools 转换结果 ──")
            for t in tools:
                print(f"- name={t.name} | args_schema 必填字段="
                      f"{list(t.args.keys()) if t.args else []}")
                print(f"  description={t.description}")

            # 2) 转换后的工具本地直调（内部走 MCP 协议 构建工具/call）
            direct = await tools[0].ainvoke({"plan_id": "P-1001"})
            print(f"\n── BaseTool 直调 {tools[0].name} ──\n{direct}")

            # 3) 接入 create_agent（Mock 脚本驱动一轮完整工具循环）
            from langchain.agents import create_agent

            script = iter([
                AIMessage(content="", tool_calls=[
                    {"id": "call_001", "name": "get_plan",
                     "args": {"plan_id": "P-1002"}, "type": "tool_call"}]),
                AIMessage(content="P-1002（转向节）处于延期状态，数量 1200，建议分析延期原因。"),
            ])
            model = FakeToolChatModel(messages=script)
            agent = create_agent(model=model, tools=tools,
                                 system_prompt="你是生产计划助手，回答简洁。")
            # 注意：MCP 工具是 async-only（协议调用本身是异步的），
            # 同步 agent.invoke 会抛 NotImplementedError（真实报错见 55.7②）——必须用 ainvoke
            result = await agent.ainvoke(
                {"messages": [HumanMessage(content="查一下 P-1002 的状态")]})
            print("\n── create_agent + MCP 工具的完整闭环（Mock 驱动）──")
            for m in result["messages"]:
                tc = getattr(m, "tool_calls", None)
                extra = f" tool_calls={[c['name'] for c in tc]}" if tc else ""
                if type(m).__name__ == "ToolMessage":
                    extra = f" tool_call_id={m.tool_call_id}"
                print(f"  {type(m).__name__:<12} {str(m.content)[:52]}{extra}")
            print(f"  bind_tools 记录 = {model.bind_calls}")


if __name__ == "__main__":
    anyio.run(run_demo)
