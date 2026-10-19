# 测试/test_ch55.py | 第 55 章：MCP（真实 stdio 协议闭环 / 工具错误语义 / LangChain 适配）
"""覆盖（4 个测试）：initialize 握手与能力协商、构建工具/list 形状（name/description/
inputSchema）、构建工具/call 正常与业务错误（isError=True 是结果不是协议错误）、
langchain-mcp-adapters 转换后的 BaseTool 直调。

真实拉起 ex_55_02 的 stdio server 子进程（mcp 1.30.0），全程走 JSON-RPC——
这是"协议可观察"的测试形态：不 mock 协议层，mock 的是业务数据本身（服务端内置）。

运行：cd /workspace/ai_application_course && python3 -m pytest 测试/test_ch55.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "示例代码" / "ch55_mcp" / "ex_55_02_mcp_stdio_server.py"


def _params() -> StdioServerParameters:
    """stdio 服务端描述：用当前解释器拉起 ex_55_02（绝对路径，环境继承）。"""
    return StdioServerParameters(command=sys.executable, args=[str(SERVER)], env=None)


async def test_initialize_and_tools_list() -> None:
    async with stdio_client(_params()) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            init = await session.initialize()
            assert init.serverInfo.name == "plan-tools"
            caps = init.capabilities.model_dump(exclude_none=True)
            assert {"tools", "resources", "prompts"} <= set(caps)

            tools = await session.list_tools()
            names = {t.name for t in tools.tools}
            assert {"get_plan", "list_delayed_plans"} <= names
            get_plan = next(t for t in tools.tools if t.name == "get_plan")
            assert get_plan.inputSchema["required"] == ["plan_id"]
            assert get_plan.description          # 描述随协议下发（EX-54-01 的治理对象）


async def test_call_tool_success_and_business_error() -> None:
    """协议语义：工具内部异常（计划不存在）返回 isError=True 的**正常响应**，
    而不是 JSON-RPC error——"工具错误是数据"在协议层有明确形状。"""
    async with stdio_client(_params()) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            ok = await session.call_tool("get_plan", {"plan_id": "P-1002"})
            assert ok.isError is False
            assert "P-1002" in ok.content[0].text
            assert "延期" in ok.content[0].text

            bad = await session.call_tool("get_plan", {"plan_id": "P-9999"})
            assert bad.isError is True                     # 业务错误 → isError 标记
            assert "不存在" in bad.content[0].text


async def test_list_delayed_plans_filters() -> None:
    async with stdio_client(_params()) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            delayed = await session.call_tool("list_delayed_plans", {})
            assert delayed.isError is False
            assert "P-1002" in delayed.content[0].text     # 只含延期的 P-1002
            assert "P-1001" not in delayed.content[0].text


async def test_langchain_adapter_converts_and_invokes() -> None:
    """langchain-mcp-adapters 0.3.2：MCP 工具 → BaseTool（本地直调走协议）。"""
    async with stdio_client(_params()) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            from langchain_mcp_adapters.tools import load_mcp_tools

            tools = await load_mcp_tools(session)
            names = {t.name for t in tools}
            assert {"get_plan", "list_delayed_plans"} <= names
            result = await tools[0].ainvoke({"plan_id": "P-1001"})
            assert "减速器壳体" in str(result)
