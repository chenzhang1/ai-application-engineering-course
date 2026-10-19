# tests/test_ch40.py | ch40 LCEL / Runnable
"""覆盖：管道类型与输出（正常）、assign 并行分支（边界语义）、异常原样传播（非法输入）、
batch/stream 与异步协议（pytest-asyncio auto 模式）。"""
from __future__ import annotations

from langchain_core.language_models import FakeListChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import (
    Runnable,
    RunnableLambda,
    RunnableParallel,
    RunnablePassthrough,
    RunnableSequence,
)

from examples.ch40_lcel.ex_40_01_pipe_chain import bare_compose
from examples.ch40_lcel.ex_40_03_batch_stream_async import build_chain


def _mini_chain(script: list[str]):
    prompt = ChatPromptTemplate.from_messages([("human", "{q}")])
    return prompt | FakeListChatModel(responses=script) | StrOutputParser()


def test_pipe_chain_type_and_output() -> None:
    chain = _mini_chain(["（Fake）7 天无理由退货。"])
    assert isinstance(chain, Runnable) and isinstance(chain, RunnableSequence)
    out = chain.invoke({"q": "退货政策"})
    assert out == "（Fake）7 天无理由退货。"
    assert isinstance(bare_compose("x"), str)  # 裸组装对照线仍然可用


def test_passthrough_assign_keeps_keys() -> None:
    """assign：原键透传 + 新键注入（RAG 旁路注入的语义契约）。"""
    inject = RunnablePassthrough.assign(ctx=RunnableLambda(lambda x: "检索结果"))
    out = inject.invoke({"question": "Q", "tenant": "acme"})
    assert out == {"question": "Q", "tenant": "acme", "ctx": "检索结果"}


def test_parallel_branches_share_input() -> None:
    parallel = RunnableParallel(a=RunnableLambda(str.upper), b=RunnableLambda(len))
    assert parallel.invoke("ab") == {"a": "AB", "b": 2}
    assert parallel.batch(["x", "yz"]) == [{"a": "X", "b": 1}, {"a": "YZ", "b": 2}]


def test_exception_propagates_unchanged() -> None:
    """非法路径：链中节点抛 ValueError，invoke 处收到原类型原信息（不被框架包装）。"""
    def boom(_: str) -> str:
        raise ValueError("订单库连接超时")

    bad = RunnableLambda(boom) | RunnableLambda(str.upper)
    import pytest

    with pytest.raises(ValueError, match="订单库连接超时"):
        bad.invoke("x")


def test_batch_and_stream_protocol() -> None:
    chain = _mini_chain(["答 1", "答 2", "流式输出文本"])  # batch 消费 2 条，stream 消费第 3 条
    assert chain.batch([{"q": "a"}, {"q": "b"}]) == ["答 1", "答 2"]
    chunks = list(chain.stream({"q": "c"}))
    assert "".join(chunks) == "流式输出文本"
    assert len(chunks) >= 2  # Fake 流式按字切（确定性）


async def test_ainvoke_async() -> None:
    """异步协议：ainvoke 与 invoke 结果一致（asyncio_mode=auto，协程测试直接跑）。"""
    chain = _mini_chain(["异步回答"])
    assert await chain.ainvoke({"q": "x"}) == "异步回答"
