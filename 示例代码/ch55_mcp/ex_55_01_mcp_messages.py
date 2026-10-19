# EX-55-01 | MCP 的协议消息长什么样：手写 JSON-RPC 2.0 帧结构（纯讲解，无网络）
# 运行: python3 示例代码/ch55_mcp/ex_55_01_mcp_messages.py
"""确定性演示：把 MCP 官方规范（2026-07-28 核实，2026-10-19）里最常见的四类消息
按 JSON-RPC 2.0 的形状手工构造出来。目的不是"自己实现协议"，而是让读者在
看 SDK 黑盒之前先看清线上传输的字节内容——排障时抓包/看 stderr 日志全靠这个形状。

JSON-RPC 2.0 三种帧：
    请求   ：{"jsonrpc": "2.0", "id": 1, "method": "...", "params": {...}}
    通知   ：同请求但没有 id（不期待回复，如 notifications/initialized）
    响应   ：{"jsonrpc": "2.0", "id": 1, "result": {...}} 或 {"error": {...}}
"""
from __future__ import annotations

import json
from typing import Any


def show(title: str, frame: dict[str, Any]) -> None:
    print(f"── {title} ──")
    print(json.dumps(frame, ensure_ascii=False, indent=2))
    print()


def main() -> None:
    # 1) 客户端 → 服务端：initialize 请求（握手：协议版本 + 客户端能力）
    initialize_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25",   # 客户端希望用的规范版本（SDK 1.30.0 实测协商值）
            "capabilities": {"roots": {"listChanged": True}, "sampling": {}},
            "clientInfo": {"name": "textbook-client", "version": "1.0.0"},
        },
    }
    show("① initialize 请求（JSON-RPC Request）", initialize_request)

    # 2) 服务端 → 客户端：initialize 响应（服务端版本 + 能力清单）
    initialize_response = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "protocolVersion": "2025-11-25",
            "capabilities": {"tools": {"listChanged": False},
                             "resources": {}, "prompts": {}},
            "serverInfo": {"name": "plan-tools", "version": "1.30.0"},
        },
    }
    show("② initialize 响应（JSON-RPC Response）", initialize_response)

    # 3) 客户端 → 服务端：initialized 通知（没有 id！握手收尾，不期待回复）
    initialized_notification = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
    }
    show("③ notifications/initialized 通知（无 id = 不期待回复）", initialized_notification)

    # 4) 构建工具/list 请求与响应（工具清单：name/description/inputSchema 三件套）
    tools_list_response = {
        "jsonrpc": "2.0",
        "id": 2,
        "result": {
            "tools": [
                {
                    "name": "get_plan",
                    "description": "按计划号查询生产计划详情（产品/数量/状态）。",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"plan_id": {"type": "string"}},
                        "required": ["plan_id"],
                    },
                }
            ]
        },
    }
    show("④ 构建工具/list 响应（工具 = name + description + inputSchema）", tools_list_response)

    # 5) 构建工具/call 请求与两种响应（成功 / 工具内部异常 → isError=true）
    call_request = {
        "jsonrpc": "2.0", "id": 3, "method": "构建工具/call",
        "params": {"name": "get_plan", "arguments": {"plan_id": "P-1002"}},
    }
    call_ok = {"jsonrpc": "2.0", "id": 3, "result": {
        "content": [{"type": "text", "text": "{\"plan_id\": \"P-1002\", ...}"}], "isError": False}}
    call_err = {"jsonrpc": "2.0", "id": 3, "result": {
        "content": [{"type": "text", "text": "Error executing tool get_plan: 计划 P-9999 不存在"}],
        "isError": True}}
    show("⑤ 构建工具/call 请求", call_request)
    show("⑥ 构建工具/call 成功响应（content 是内容块列表）", call_ok)
    show("⑦ 构建工具/call 工具内部异常：仍在 result 里，isError=true（≠ JSON-RPC error）", call_err)

    # 6) 对照表：JSON-RPC 帧 ↔ 三种 MCP 消息方向
    print("── 帧类型速查 ──")
    print("Request    (有 id, 有 method) → 期待 Response")
    print("Notification(无 id, 有 method) → 不期待回复（单向）")
    print("Response   (有 id, 有 result|error) → 只能由'收到 Request 的一方'发出")
    print("MCP 规范约束：服务端不发 Request 只回 Response（2026-07-28 版核实）；")
    print("需要模型/用户输入时通过 result 内的 InputRequiredResult 语义表达（EX 演示范围外）")


if __name__ == "__main__":
    main()
