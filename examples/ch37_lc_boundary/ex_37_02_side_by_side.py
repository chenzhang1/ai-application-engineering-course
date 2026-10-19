# EX-37-02 | 同一任务对照：裸 llm_client vs LangChain 链 | 运行: python3 examples/ch37_lc_boundary/ex_37_02_side_by_side.py
"""完整可运行（Mock，不联网）：同一个任务——"客服风格回答 + 打印 token 统计"——
分别用第四部分的裸 llm_client 与 LangChain（Fake 模型）实现，逐项对比"框架替你做了什么"。

诚实声明：LangChain 侧用的是 langchain-core 的 FakeListChatModel（官方测试用途的
确定性假模型，无需 API Key），回答是脚本预置的；裸 llm_client 是全书自研的规则 Mock。
两者的"回答文本"都是确定性的，比较的是【工程接口】，不是模型智力。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # 仓库根

from examples.common.llm_client import MockLLM, count_tokens  # noqa: E402

from langchain_core.language_models import FakeListChatModel  # noqa: E402
from langchain_core.output_parsers import StrOutputParser  # noqa: E402
from langchain_core.prompts import ChatPromptTemplate  # noqa: E402

QUESTION = "退货政策是什么？"


def bare_sdk_version() -> tuple[str, dict[str, int]]:
    """裸 SDK 版本（EX-24 的形态）：手写 system prompt、手拼消息 dict、手取字段。"""
    llm = MockLLM()
    messages = [
        {"role": "system", "content": "你是电商客服助手，用简洁中文回答。"},
        {"role": "user", "content": QUESTION},
    ]
    result = llm.chat(messages)
    usage = {
        "prompt_tokens": result.usage["prompt_tokens"],
        "completion_tokens": result.usage["completion_tokens"],
    }
    return result.content, usage


def langchain_version() -> tuple[str, str]:
    """LangChain 版本：模板声明式组装，prompt | model | parser 三段管道。"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是电商客服助手，用简洁中文回答。"),
        ("human", "{question}"),
    ])
    model = FakeListChatModel(responses=["（Fake）您好，7 天内可无理由退货，运费由商家承担。"])
    chain = prompt | model | StrOutputParser()
    answer: str = chain.invoke({"question": QUESTION})
    return answer, type(chain).__name__


def main() -> None:
    print("[对照 A] 裸 llm_client（第四部分接口）：")
    answer, usage = bare_sdk_version()
    n, method = count_tokens(QUESTION)
    print(f"    回答：{answer}")
    print(f"    usage：{usage}  （count_method={method}，查询本身 {n} tokens）")
    print("    你亲手写的：消息 dict 拼装、system 关键词匹配、usage 统计\n")

    print("[对照 B] LangChain（FakeListChatModel + LCEL 管道）：")
    answer, chain_type = langchain_version()
    print(f"    回答：{answer}")
    print(f"    管道类型：{chain_type}")
    print("    框架替你做的：消息对象化、模板变量注入、输出解析、统一的 invoke/batch/stream")

    print("\n[框架没替你做的——这两个实现里都有你的活]：")
    print("    1) token 统计：FakeListChatModel 不提供 usage，要自己接（真实 ChatOpenAI 响应里有 usage_metadata）")
    print("    2) 行为正确性：Mock/Fake 的回答都是脚本预置，业务正确性永远由你的测试保证")
    print("    3) 密钥与网络策略：无论裸 SDK 还是框架，Key 管理都在你这边（ch02/ch58）")

    print("\n[判断] 这个任务该用谁？")
    print("    单轮 + 单步 + 不换模型 → 裸 SDK 足够（EX-37-01 决策表建议 bare_sdk）；")
    print("    但如果明天要加'检索到政策原文再回答'，LangChain 的组件（ch41）就开始省事了。")


if __name__ == "__main__":
    main()
