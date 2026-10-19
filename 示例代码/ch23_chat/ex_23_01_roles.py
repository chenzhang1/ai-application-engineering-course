# EX-23-01 | 消息角色与 messages 结构 | 运行: python3 示例代码/ch23_chat/ex_23_01_roles.py
"""完整可运行（Mock）：system/user/assistant/tool 四种角色的消息结构，
以及"assistant 发起工具调用 → tool 回传结果"的完整消息形态（OpenAI 风格 dict）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from 示例代码.公共.llm_client import get_llm  # noqa: E402

TOOLS = [{
    "type": "function",
    "function": {
        "name": "get_order_status",
        "description": "查询订单状态",
        "parameters": {
            "type": "object",
            "properties": {"order_id": {"type": "string", "description": "订单号"}},
            "required": ["order_id"],
        },
    },
}]


def dump(label: str, messages: list[dict[str, Any]]) -> None:
    print(f"--- {label} ---")
    print(json.dumps(messages, ensure_ascii=False, indent=2))


def main() -> None:
    llm = get_llm()
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": "你是订单客服助手，只回答与订单有关的问题。"},
        {"role": "user", "content": "USE_TOOL:get_order_status order_id=ORD-1001"},
    ]
    r1 = llm.chat(messages, tools=TOOLS)
    print(f"[第 1 次调用] finish_reason={r1.finish_reason}, tool_calls={[(t.name, t.arguments) for t in r1.tool_calls]}")

    # 把"模型想调工具"这件事落成 assistant 消息，再把执行结果以 tool 角色回传
    messages.append({
        "role": "assistant",
        "content": r1.content,
        "tool_calls": [{
            "id": r1.tool_calls[0].id,
            "type": "function",
            "function": {"name": r1.tool_calls[0].name,
                         "arguments": json.dumps(r1.tool_calls[0].arguments, ensure_ascii=False)},
        }],
    })
    messages.append({"role": "tool", "tool_call_id": r1.tool_calls[0].id,
                     "content": json.dumps({"order_id": "ORD-1001", "status": "已发货"},
                                           ensure_ascii=False)})
    dump("回传工具结果后的 messages（OpenAI 风格）", messages)

    r2 = llm.chat(messages)
    print(f"\n[第 2 次调用] 模型基于工具结果作答：{r2.content}")
    print(f"usage（prompt 含全部历史）：{r2.usage}")


if __name__ == "__main__":
    main()
