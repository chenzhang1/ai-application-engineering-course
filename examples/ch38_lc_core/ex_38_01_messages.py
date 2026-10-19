# EX-38-01 | 消息模型：LangChain 消息对象与裸 SDK dict 的映射 | 运行: python3 examples/ch38_lc_core/ex_38_01_messages.py
"""完整可运行（离线）：构造 HumanMessage/AIMessage/SystemMessage/ToolMessage，
对比第四部分裸 SDK 的 dict 形态；演示 FakeListChatModel 的 invoke 与 AIMessageChunk 流式聚合。
"""
from __future__ import annotations

from langchain_core.language_models import FakeListChatModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)


def main() -> None:
    print("[1] 四类消息对象 vs 裸 SDK dict（字段对照）：")
    msgs: list = [
        SystemMessage(content="你是电商客服助手。"),
        HumanMessage(content="北京天气怎么样？"),
        AIMessage(content="", tool_calls=[{
            "id": "call_001", "name": "get_weather",
            "args": {"city": "北京"}, "type": "tool_call",
        }]),
        ToolMessage(content='{"city": "北京", "weather": "晴"}', tool_call_id="call_001"),
    ]
    for m in msgs:
        extra = ""
        if isinstance(m, AIMessage) and m.tool_calls:
            extra = f" tool_calls={m.tool_calls}"
        if isinstance(m, ToolMessage):
            extra = f" tool_call_id={m.tool_call_id}"
        print(f"    {type(m).__name__:<13} content={m.content!r}{extra}")
    print("    裸 SDK dict 对照：{'role': 'system'|'user'|'assistant'|'tool', 'content': ...}")
    print("    → LangChain 把 dict 换成了带类型的对象；发给模型 API 时框架负责序列化回 dict")

    print("\n[2] 模型返回值：invoke 一次 Fake 模型：")
    model = FakeListChatModel(responses=["北京今天晴，26℃。（Fake 预置）"])
    ai = model.invoke([HumanMessage(content="北京天气怎么样？")])
    print(f"    type = {type(ai).__name__}")
    print(f"    content = {ai.content!r}")
    print(f"    id 前 8 位 = {ai.id[:8]}...  （框架自动生成消息 id）")
    print(f"    usage_metadata = {ai.usage_metadata}  （Fake 模型无 usage：None/空，真实模型有值）")

    print("\n[3] 流式：AIMessageChunk 用 + 号聚合（对照 ch23 手工拼接 delta）：")
    model2 = FakeListChatModel(responses=["逐字流式输出"])
    chunks: list[AIMessageChunk] = list(model2.stream("任意输入（Fake 不看输入）"))
    print(f"    chunk 数 = {len(chunks)}，类型 = {type(chunks[0]).__name__}")
    merged = chunks[0]
    for c in chunks[1:]:
        merged = merged + c  # AIMessageChunk 支持相加，自动合并 content/id
    print(f"    聚合后 content = {merged.content!r}")
    print("    → 裸 SDK 里你手写的 'full += delta' 循环，框架里是一个 + 运算符")


if __name__ == "__main__":
    main()
