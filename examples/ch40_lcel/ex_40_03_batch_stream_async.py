# EX-40-03 | batch / stream / ainvoke / astream_events 与异常传播链 | 运行: python3 examples/ch40_lcel/ex_40_03_batch_stream_async.py
"""完整可运行（离线，asyncio 真实运行）：
[1] 一条链免费获得 batch/stream/ainvoke/astream（裸 SDK 要给每个入口手写包装）；
[2] 异常在链中的传播：原类型原样向上抛（不被框架吞掉或包一层），finally 语义；
[3] astream_events：流式事件的"发动机舱"视图——ch42 的 agent 流式就是它的应用。
"""
from __future__ import annotations

import asyncio

from langchain_core.language_models import FakeListChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda


def build_chain(script: list[str]) -> RunnableLambda | object:
    """构造 prompt | model | parser 三段链（Fake 模型按 script 顺序消费）。"""
    prompt = ChatPromptTemplate.from_messages([("human", "{q}")])
    model = FakeListChatModel(responses=script)
    return prompt | model | StrOutputParser()


def main() -> None:
    chain = build_chain(["回答 A", "回答 B1", "回 答 C 按字流出", "回答 D"])

    print("[1] batch：并发跑多个输入（Fake 串行消费脚本，真实模型并发发请求）：")
    print(f"    {chain.batch([{'q': '问题一'}, {'q': '问题二'}])}")

    print("\n[2] stream：增量输出，parser 逐段生效：")
    print(f"    chunks = {[c for c in chain.stream({'q': '问题三'})]}")
    print("    → 裸 SDK 里你手写 'full += delta'（EX-23-03）；这里链内自动完成逐段传递")

    print("\n[3] 异常传播链（真实抛出）：链中任一节点抛异常，原类型原样冒泡：")
    def boom(_: dict) -> str:
        raise ValueError("下游业务异常：订单库连接超时")
    bad = RunnableLambda(boom) | RunnableLambda(lambda s: s.upper())
    try:
        bad.invoke({"q": "x"})
    except ValueError as e:
        print(f"    捕获到 {type(e).__name__}: {e}")
        print("    → 没有被包成框架异常：try/except 业务语义不变（对照 ch08 异常链）")
    # 流式中的异常同样在迭代处抛出
    def boom_stream(_: dict):
        yield "先吐一段"
        raise RuntimeError("流到一半炸了")
    streamy = RunnableLambda(boom_stream) | RunnableLambda(str.upper)
    try:
        for _ in streamy.stream({"q": "x"}):
            pass
    except RuntimeError as e:
        print(f"    流式同样：{type(e).__name__}: {e}（消费者在迭代时收到）")

    print("\n[4] ainvoke / astream_events（asyncio 真实运行）：")
    asyncio.run(async_demo(chain))
    print("\n[小结] LCEL 的价值公式：写一次管道 = 免费得到 batch/stream/async/config 四套协议；")
    print("       裸 SDK 每套都要手写循环（第四部分每个 EX 都在为此付费）。")


async def async_demo(chain) -> None:
    print(f"    ainvoke = {await chain.ainvoke({'q': '异步问题'})}")
    events: list[str] = []
    async for ev in chain.astream_events({"q": "事件流"}, version="v2"):
        events.append(ev["event"])
    print(f"    astream_events 前 6 个事件 = {events[:6]}")
    print(f"    共 {len(events)} 个事件：链的每一段（prompt/model/parser）的 start/end/stream")
    print("    都是独立事件 → 给 ch42 的 agent 流式与可观测性打底。")


if __name__ == "__main__":
    main()
