# EX-38-03 | PromptTemplate / ChatPromptTemplate 与结构化输出 | 运行: python3 示例代码/ch38_lc_core/ex_38_03_prompt_structured.py
"""完整可运行（不联网）：
[1] ChatPromptTemplate：变量注入、MessagesPlaceholder、format_messages 与 invoke 的区别；
[2] with_structured_output：真实 ChatOpenAI 的调用形状（签名核实，需 Key 未实调）；
[3] 确定性替代：PydanticOutputParser 组成的"JSON 文本 → Pydantic 对象"链在 Fake 模型上真实跑通。
"""
from __future__ import annotations

import inspect

from langchain_core.language_models import FakeListChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field


class RefundCheck(BaseModel):
    """退款预检结果（与 EX-24-02 同一套 schema，方便对照）。"""

    order_id: str = Field(description="订单号，格式 ORD-数字")
    eligible: bool = Field(description="是否符合自动退款条件")
    reason: str = Field(default="无", description="不符合时的原因")


def main() -> None:
    print("[1] ChatPromptTemplate：声明式模板（对照裸 SDK 手拼 f-string）：")
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是{role}，用简洁中文回答。"),
        MessagesPlaceholder("history", optional=True),  # 可选的历史占位（ch27 对话历史）
        ("human", "{question}"),
    ])
    print(f"    input_variables = {prompt.input_variables}")
    print(f"    optional_variables = {prompt.optional_variables}")
    value = prompt.invoke({
        "role": "电商客服",
        "question": "退货政策是什么？",
        "history": [HumanMessage(content="之前问过发票"), AIMessage(content="已回答")],
    })
    print(f"    invoke 返回类型 = {type(value).__name__}")
    for m in value.to_messages():
        print(f"      {type(m).__name__}: {m.content[:30]}")
    # 不传 history（optional 生效，不报 KeyError）
    value2 = prompt.invoke({"role": "电商客服", "question": "只问一句"})
    print(f"    不传 history → {len(value2.to_messages())} 条消息（optional 占位自动省略）")

    print("\n[2] PromptTemplate（纯文本模板，非对话）：")
    pt = PromptTemplate.from_template("把这句话翻译成英文：{text}")
    print(f"    pt.invoke({{'text': '你好'}}).to_string() = {pt.invoke({'text': '你好'}).to_string()!r}")

    print("\n[3] with_structured_output 的真实形状（ChatOpenAI，需 Key 未实调，签名已核实）：")
    from langchain_openai import ChatOpenAI

    sig = inspect.signature(ChatOpenAI.with_structured_output)
    print(f"    签名：with_structured_output{sig}")
    print("    真实用法：llm = ChatOpenAI(model='gpt-4o-mini', api_key=...)")
    print("              structured = llm.with_structured_output(RefundCheck)")
    print("              obj = structured.invoke('帮我判断 ORD-1001 能否自动退款')")
    print("    → 返回 Runnable[LanguageModelInput, RefundCheck]：直接产出 Pydantic 实例")
    print("    method 默认 json_schema（服务端 schema 约束），可选 function_calling / json_mode")
    fake = FakeListChatModel(responses=["x"])
    try:
        fake.with_structured_output(RefundCheck)
    except NotImplementedError as e:
        print(f"    Fake 模型不支持（真实报错）：NotImplementedError: {e}")

    print("\n[4] 确定性替代链：Fake 模型输出 JSON 文本 → PydanticOutputParser 校验（真实运行）：")
    parser = PydanticOutputParser(pydantic_object=RefundCheck)
    chain = ChatPromptTemplate.from_messages([
        ("human", "抽取退款预检字段：{text}\n{format_instructions}"),
    ]) | FakeListChatModel(responses=[
        '{"order_id": "ORD-1001", "eligible": true, "reason": "无"}',
        '这句话根本不是 JSON',
    ]) | parser
    ok = chain.invoke({"text": "订单号 ORD-1001 符合条件", "format_instructions": parser.get_format_instructions()})
    print(f"    成功路径：type = {type(ok).__name__}, obj = {ok.model_dump()}")
    try:
        chain.invoke({"text": "失效输出演示", "format_instructions": parser.get_format_instructions()})
    except Exception as e:
        print(f"    失败路径：{type(e).__name__}（输出不是 JSON → 解析失败原样抛出，由你决定重试策略）")


if __name__ == "__main__":
    main()
