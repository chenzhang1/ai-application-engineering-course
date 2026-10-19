# tests/test_ch23.py | ch23 对话与参数
"""覆盖：消息角色结构、流式拼接一致性、多模态消息结构、参数透传契约。"""
from __future__ import annotations

import base64
import json

from examples.ch23_chat.ex_23_04_multimodal_structure import (
    build_vision_message,
    tiny_png_b64,
)
from examples.common.llm_client import MockLLM


def test_roles_message_shapes() -> None:
    """四种角色消息都含 role/content；tool 消息必须有 tool_call_id。"""
    messages = [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "q"},
        {"role": "assistant", "content": "a"},
        {"role": "tool", "tool_call_id": "call_001", "content": "{}"},
    ]
    for m in messages:
        assert "role" in m and "content" in m
    tool = messages[-1]
    assert tool["role"] == "tool" and tool["tool_call_id"] == "call_001"


def test_tool_round_trip_message_form() -> None:
    """脚本模式：第 1 次=工具调用请求，回传 tool 结果后第 2 次=脚本最终回答。"""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from examples.ch23_chat.ex_23_01_roles import TOOLS

    llm = MockLLM(script=[{"tool_calls": [{"name": "get_order_status",
                                           "arguments": {"order_id": "ORD-1001"}}]},
                          {"content": "订单已发货。"}])
    messages: list[dict] = [{"role": "user", "content": "查一下订单 ORD-1001"}]
    r1 = llm.chat(messages, tools=TOOLS)
    messages.append({"role": "assistant", "content": r1.content,
                     "tool_calls": [{"id": r1.tool_calls[0].id, "type": "function",
                                     "function": {"name": r1.tool_calls[0].name,
                                                  "arguments": json.dumps(r1.tool_calls[0].arguments)}}]})
    messages.append({"role": "tool", "tool_call_id": r1.tool_calls[0].id,
                     "content": json.dumps({"status": "已发货"}, ensure_ascii=False)})
    r2 = llm.chat(messages)
    assert r2.finish_reason == "stop" and r2.content == "订单已发货。"


def test_rule_mode_integrates_tool_result() -> None:
    """规则模式：USE_TOOL 触发调用；最后一条是 tool 消息时 Mock 整合结果、不再发起新调用。"""
    llm = MockLLM()
    messages: list[dict] = [{"role": "user", "content": "USE_TOOL:get_order_status order_id=ORD-1001"}]
    r1 = llm.chat(messages)
    assert r1.finish_reason == "tool_calls" and r1.tool_calls[0].name == "get_order_status"
    messages.append({"role": "assistant", "content": r1.content,
                     "tool_calls": [{"id": r1.tool_calls[0].id, "type": "function",
                                     "function": {"name": r1.tool_calls[0].name,
                                                  "arguments": json.dumps(r1.tool_calls[0].arguments)}}]})
    messages.append({"role": "tool", "tool_call_id": r1.tool_calls[0].id,
                     "content": json.dumps({"status": "已发货"}, ensure_ascii=False)})
    r2 = llm.chat(messages)
    assert r2.finish_reason == "stop" and "工具结果" in r2.content  # Mock 整合工具结果
    assert not r2.has_tool_calls  # 不死循环：整合轮不会再触发新调用


def test_stream_joins_to_whole() -> None:
    chunks = list(MockLLM().chat_stream([{"role": "user", "content": "流式输出"}]))
    whole = MockLLM().chat([{"role": "user", "content": "流式输出"}]).content
    assert "".join(chunks) == whole and len(chunks) >= 2


def test_multimodal_message_structure() -> None:
    """图文消息：content 是分段数组，image_url 是 data:base64 URL；base64 可逆。"""
    b64 = tiny_png_b64()
    msgs = build_vision_message("这张图里是什么颜色？", b64)
    content = msgs[0]["content"]
    assert isinstance(content, list) and content[0]["type"] == "text" and content[1]["type"] == "image_url"
    url = content[1]["image_url"]["url"]
    assert url.startswith("data:image/png;base64,")
    decoded = base64.b64decode(url.removeprefix("data:image/png;base64,"))
    assert decoded[:8] == b"\x89PNG\r\n\x1a\n"  # 合法 PNG 魔数
