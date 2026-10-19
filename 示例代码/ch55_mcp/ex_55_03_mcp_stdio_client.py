# EX-55-03 | 真实 MCP 客户端：拉起 stdio server 子进程，完成 initialize → 构建工具/list → 构建工具/call
# 运行: python3 示例代码/ch55_mcp/ex_55_03_mcp_stdio_client.py
"""全书第一个端到端 MCP 实测（mcp 1.30.0，Python 3.14.7，2026-10-19 真实运行）：

1. StdioServerParameters 描述"怎么拉起服务端子进程"（命令 + 参数 + 环境）；
2. stdio_client() 建立 stdin/stdout 管道（返回读写流）；
3. ClientSession.initialize() 完成 JSON-RPC 握手（协议版本 + 能力协商）；
4. list_tools() / call_tool() 走标准协议方法（构建工具/list、构建工具/call）。

anyio 负责异步运行时（SDK 建立在 anyio 之上，不是 asyncio 裸接口——13 章的 asyncio
知识仍然适用，但入口要用 anyio.run）。
"""
from __future__ import annotations

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER_SCRIPT = "示例代码/ch55_mcp/ex_55_02_mcp_stdio_server.py"


async def main() -> None:
    # 1) 描述服务端进程：python3 脚本，stdio 模式
    params = StdioServerParameters(
        command="python3",
        args=[SERVER_SCRIPT],
        env=None,  # None=继承当前环境；也可给最小白名单环境
    )
    # 2) stdio_client 是异步上下文管理器：进入时拉起子进程并接好管道
    async with stdio_client(params) as (read_stream, write_stream):
        # 3) ClientSession 在流上收发 JSON-RPC；initialize 完成握手
        async with ClientSession(read_stream, write_stream) as session:
            init = await session.initialize()
            print("── initialize 握手结果 ──")
            print(f"协议版本（SDK 侧协商）: {init.protocolVersion}")
            print(f"服务端名称           : {init.serverInfo.name}")
            print(f"服务端版本           : {init.serverInfo.version}")
            print(f"服务端能力           : {list(init.capabilities.model_dump(exclude_none=True).keys())}")

            # 4) 构建工具/list：服务端报出工具清单（name/description/inputSchema）
            tools = await session.list_tools()
            print("\n── 构建工具/list 返回 ──")
            for t in tools.tools:
                print(f"- {t.name}: {t.description}")
                print(f"  inputSchema 必填参数: {t.inputSchema.get('required', [])}")

            # 5) 构建工具/call：真实调用一次（服务端进程里执行函数，结果回传）
            ok = await session.call_tool("get_plan", {"plan_id": "P-1002"})
            print("\n── 构建工具/call get_plan(P-1002) ──")
            print(f"isError={ok.isError} | content={ok.content[0].text}")

            # 6) 调用不存在的工具 → 协议级错误（客户端拿到 isError=True + 错误文本）
            bad = await session.call_tool("get_plan", {"plan_id": "P-9999"})
            print("\n── 构建工具/call get_plan(P-9999)（工具内部抛 ValueError）──")
            print(f"isError={bad.isError} | content={bad.content[0].text[:60]}...")


if __name__ == "__main__":
    anyio.run(main)
