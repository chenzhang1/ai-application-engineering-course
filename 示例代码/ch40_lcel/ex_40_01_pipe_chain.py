# EX-40-01 | LCEL 管道：prompt | model | parser 的本质是 RunnableSequence | 运行: python3 示例代码/ch40_lcel/ex_40_01_pipe_chain.py
"""完整可运行（离线）：把"裸 SDK 手写组装函数"升级成 LCEL 管道，对比两种写法在
类型、组合、调试上的差异；get_graph() / get_prompts() 两个调试入口实测。
"""
from __future__ import annotations

from langchain_core.language_models import FakeListChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda, RunnableSequence


def bare_compose(question: str) -> str:
    """裸 SDK 时代的组装：一个函数包住所有步骤（对比用，不调用模型）。"""
    system = "你是电商客服，用简洁中文回答。"          # 步骤 1：手拼 prompt
    fake_reply = f"（预置回答）关于「{question}」……"   # 步骤 2：调用模型（此处为桩）
    return f"{system}{fake_reply}"                     # 步骤 3：手工拼接输出


def main() -> None:
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是{role}，用简洁中文回答。"),
        ("human", "{question}"),
    ])
    model = FakeListChatModel(responses=["（Fake）7 天内可无理由退货。"])
    chain: Runnable = prompt | model | StrOutputParser()

    print("[1] | 管道的本质（类型核实）：")
    print(f"    type(prompt | model)             = {type(prompt | model).__name__}")
    print(f"    type(prompt | model | parser)    = {type(chain).__name__}")
    print(f"    isinstance(chain, Runnable)      = {isinstance(chain, Runnable)}")
    print("    → | 不是魔法运算符，是 Runnable.__or__：链本身也是 Runnable，可继续 |")

    print("\n[2] 同一任务两种写法（输出等价）：")
    print(f"    裸组装：{bare_compose('退货政策')!r}")
    print(f"    LCEL  ：{chain.invoke({'role': '电商客服', 'question': '退货政策'})!r}")

    print("\n[3] LCEL 换来的三件事（裸函数没有）：")
    print("    a) 统一执行协议：invoke/batch/stream/ainvoke 全链自动获得（EX-40-03）")
    print("    b) 统一配置协议：RunnableConfig（tags/metadata/callbacks）贯穿每个节点（EX-40-02）")
    print("    c) 可检视：链是数据，能画出结构、取出 prompt 模板")

    print("\n[4] 调试入口一：get_prompts() 把链里所有 prompt 模板捞出来：")
    for p in chain.get_prompts():
        print(f"    {type(p).__name__}: messages 结构已还原（模板变量 {p.input_variables}）")

    print("\n[5] 调试入口二：get_graph() 拿到节点/边（print_ascii 需 grandalf，本书用节点表）：")
    g = chain.get_graph()
    for node_id, node in g.nodes.items():
        print(f"    节点 {type(node).__name__:<24} name={node.name}")

    print("\n[6] RunnableLambda 包普通函数，让它获得同样的协议：")
    upper = RunnableLambda(lambda s: s.upper())
    print(f"    upper.invoke('abc') = {upper.invoke('abc')!r}")
    print(f"    upper.batch(['a', 'b']) = {upper.batch(['a', 'b'])}")
    print(f"    复合：upper.pipe(RunnableLambda(len)).invoke('abc') = {upper.pipe(RunnableLambda(len)).invoke('abc')}")
    print("    → Java 对照：prompt | model | parser ≈ Stream.of(x).map(a).map(b) 的责任链，")
    print("      但每个环节都带统一的调用/流式/异步/配置协议（Stream API 没有这层约定）。")


if __name__ == "__main__":
    main()
