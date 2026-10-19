# tests/test_ch38.py | ch38 LangChain 核心抽象：消息/模型/Prompt/结构化输出
"""覆盖：消息对象 role 映射（正常）、Fake 确定性与脚本耗尽（边界）、ChatOpenAI 缺 Key
（非法输入→真实报错）、模板可选占位、PydanticOutputParser 链成功/失败两路。"""
from __future__ import annotations

import pytest
from pydantic import BaseModel, Field

from langchain_core.language_models import FakeListChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder


def test_message_objects_role_mapping() -> None:
    """四类消息对象的 .type 与裸 SDK dict 的 role 一一对应。"""
    msgs = [
        SystemMessage(content="s"),
        HumanMessage(content="u"),
        AIMessage(content="a"),
        ToolMessage(content="t", tool_call_id="call_001"),
    ]
    assert [m.type for m in msgs] == ["system", "human", "ai", "tool"]
    ai = AIMessage(content="", tool_calls=[{"id": "c1", "name": "f", "args": {}, "type": "tool_call"}])
    assert ai.tool_calls[0]["name"] == "f"


def test_fake_model_cycle_vs_exhaustion() -> None:
    """边界：FakeListChatModel 脚本耗尽后循环回开头；GenericFakeChatModel 耗尽抛 StopIteration。"""
    fl = FakeListChatModel(responses=["甲", "乙"])
    q = [HumanMessage(content="同一问题")]
    assert [fl.invoke(q).content, fl.invoke(q).content] == ["甲", "乙"]
    assert fl.invoke(q).content == "甲"  # cycle（源码注释原话：Cycle back to the start）

    from langchain_core.language_models import GenericFakeChatModel

    gf = GenericFakeChatModel(messages=iter([AIMessage(content="唯一一条")]))
    assert gf.invoke(q).content == "唯一一条"
    with pytest.raises(StopIteration):
        gf.invoke(q)


def test_chatopenai_missing_key_and_offline_construct() -> None:
    """非法输入：无 Key 构造的真实报错；dummy Key 离线构造成功且不发请求。"""
    from langchain_openai import ChatOpenAI

    with pytest.raises(Exception, match="[Cc]redentials|api_key|OPENAI"):
        ChatOpenAI(model="gpt-4o-mini")  # 沙箱无 OPENAI_API_KEY
    m = ChatOpenAI(model="gpt-4o-mini", api_key="sk-dummy-not-used", temperature=0)
    assert m.model_name == "gpt-4o-mini" and m.temperature == 0
    # 签名核实（FACTS 红线）：with_structured_output 默认 json_schema
    import inspect

    sig = inspect.signature(ChatOpenAI.with_structured_output)
    assert sig.parameters["method"].default == "json_schema"


def test_prompt_template_optional_placeholder() -> None:
    """正常+边界：history 传与不传都合法（MessagesPlaceholder optional=True）。"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是{role}"),
        MessagesPlaceholder("history", optional=True),
        ("human", "{question}"),
    ])
    with_history = prompt.invoke({
        "role": "客服", "question": "Q",
        "history": [HumanMessage(content="旧消息")],
    }).to_messages()
    without = prompt.invoke({"role": "客服", "question": "Q"}).to_messages()
    assert len(with_history) == 3 and len(without) == 2
    assert without[0].content == "你是客服" and without[1].content == "Q"


class RefundCheck(BaseModel):
    order_id: str = Field(description="订单号")
    eligible: bool = Field(description="是否符合")


def test_structured_parser_chain_success_and_failure() -> None:
    """结构化链（Fake 模型 + PydanticOutputParser）：合法 JSON 成功；非法文本抛异常。"""
    prompt = ChatPromptTemplate.from_messages([("human", "{text}")])
    chain = prompt | FakeListChatModel(responses=[
        '{"order_id": "ORD-1", "eligible": true}',
        "这不是 JSON",
    ]) | PydanticOutputParser(pydantic_object=RefundCheck)
    ok = chain.invoke({"text": "x"})
    assert isinstance(ok, RefundCheck) and ok.order_id == "ORD-1" and ok.eligible is True
    with pytest.raises(Exception, match="[Pp]ars|JSON"):
        chain.invoke({"text": "y"})
