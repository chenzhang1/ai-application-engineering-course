# EX-24-03 | 工具调用完整闭环：请求→执行→回传→二次调用 | 运行: python3 示例代码/ch24_sdk/ex_24_03_tool_loop.py
"""完整可运行（Mock）：用脚本化 MockLLM 完整跑通 agent loop 的一次工具调用。

第 1 次调用：模型返回"我要调 get_weather(city=北京)"（finish_reason=tool_calls）
程序执行：本地函数真的算出结果
第 2 次调用：把结果以 tool 消息回传，模型基于结果给最终回答。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from 示例代码.公共.llm_client import get_llm  # noqa: E402

# ---- 1. 工具声明（JSON Schema，会随请求发给模型）--------------------------
TOOLS: list[dict[str, Any]] = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "查询指定城市当日天气",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名，如 北京"},
            },
            "required": ["city"],
        },
    },
}]

# ---- 2. 程序里的真实现（模型只"点名"，从不亲自执行）------------------------
WEATHER_DB = {"北京": {"weather": "晴", "temp": 26, "wind": "西北风 3 级"},
              "上海": {"weather": "小雨", "temp": 22, "wind": "东风 2 级"}}


def get_weather(city: str) -> dict[str, Any]:
    if city not in WEATHER_DB:
        raise ValueError(f"暂不支持城市：{city}")
    return {"city": city, **WEATHER_DB[city]}


def main() -> None:
    # 脚本化 Mock：第 1 次返回工具调用请求，第 2 次返回最终回答（Agent loop 的骨架）
    llm = get_llm()
    from 示例代码.公共.llm_client import MockLLM
    assert isinstance(llm, MockLLM), "本示例固定用 Mock 演示（LLM_MODE=real 时请改用真实模型）"
    llm = MockLLM(script=[
        {"tool_calls": [{"name": "get_weather", "arguments": {"city": "北京"}}],
         "content": ""},
        {"content": "北京今天晴，26℃，西北风 3 级，适合出行。"},
    ])

    messages: list[dict[str, Any]] = [{"role": "user", "content": "北京天气怎么样？适合跑步吗？"}]

    # ---- 第 1 轮：模型请求工具 ----
    r1 = llm.chat(messages, tools=TOOLS)
    tc = r1.tool_calls[0]
    print(f"[第 1 轮] finish_reason = {r1.finish_reason}")
    print(f"         模型请求工具：{tc.name}({json.dumps(tc.arguments, ensure_ascii=False)})  id={tc.id}")
    assert r1.finish_reason == "tool_calls"

    # ---- 程序执行工具（参数校验/权限/幂等都发生在这一层，模型无权绕过）----
    try:
        result = get_weather(**tc.arguments)
        tool_content = json.dumps(result, ensure_ascii=False)
    except Exception as e:  # 教学最小处理：错误也回传给模型，让它决定下一步
        tool_content = json.dumps({"error": str(e)}, ensure_ascii=False)

    # ---- 把"模型要点名"和"执行结果"都写回消息历史（OpenAI 风格，缺一不可）----
    messages.append({
        "role": "assistant",
        "content": r1.content,
        "tool_calls": [{"id": tc.id, "type": "function",
                        "function": {"name": tc.name,
                                     "arguments": json.dumps(tc.arguments, ensure_ascii=False)}}],
    })
    messages.append({"role": "tool", "tool_call_id": tc.id, "content": tool_content})
    print(f"[执行]   get_weather → {tool_content}")

    # ---- 第 2 轮：模型基于工具结果回答 ----
    r2 = llm.chat(messages)
    print(f"[第 2 轮] finish_reason = {r2.finish_reason}")
    print(f"         最终回答：{r2.content}")
    print(f"[usage]  两次调用合计 total_tokens = "
          f"{r1.usage['total_tokens'] + r2.usage['total_tokens']}"
          f"（prompt 每轮都重算，历史会滚雪球）")

    # 类比：这轮闭环 ≈ Java 里"回调/消息驱动"——模型发请求(HTTP 回调)，服务端执行后回投
    print("\n[闭环检查] messages 轮廓：")
    for m in messages:
        extra = f"  [tool结果] {m['content']}" if m["role"] == "tool" else ""
        print(f"    - {m['role']}: {str(m.get('content'))[:36]}{extra}")


if __name__ == "__main__":
    main()
