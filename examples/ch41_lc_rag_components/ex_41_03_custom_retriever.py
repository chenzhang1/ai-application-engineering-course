# EX-41-03 | 自写 Retriever（BaseRetriever 子类）并接进 RAG 生成链 | 运行: python3 examples/ch41_lc_rag_components/ex_41_03_custom_retriever.py
"""完整可运行（离线）：
[1] 继承 BaseRetriever：第六部分手写的"embed + 余弦 + Top-k"变成框架组件；
[2] Retriever 是 Runnable：batch / 进管道 / 与 RunnablePassthrough.assign 组合成 RAG 链；
[3] 全链真实运行：检索注入 → ChatPromptTemplate → Fake 模型 → 最终回答。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # 仓库根

from examples.common.embeddings import MockEmbedder, cosine_similarity  # noqa: E402

from langchain_core.callbacks import CallbackManagerForRetrieverRun  # noqa: E402
from langchain_core.documents import Document  # noqa: E402
from langchain_core.language_models import FakeListChatModel  # noqa: E402
from langchain_core.output_parsers import StrOutputParser  # noqa: E402
from langchain_core.prompts import ChatPromptTemplate  # noqa: E402
from langchain_core.retrievers import BaseRetriever  # noqa: E402
from langchain_core.runnables import RunnableLambda, RunnablePassthrough  # noqa: E402


class MockRetriever(BaseRetriever):
    """语义检索 Retriever：核心逻辑 = EX-25-03 手写检索，外壳 = LangChain 接口。

    只需实现一个方法：_get_relevant_documents(query, run_manager) -> list[Document]。
    （Pydantic 子类：docs/k 作为字段声明，不要放进 __init__ 手动赋值。）
    """

    docs: list[Document]
    k: int = 2

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> list[Document]:
        emb = MockEmbedder()
        qv = emb.embed_one(query)
        scored = sorted(
            self.docs,
            key=lambda d: cosine_similarity(qv, emb.embed_one(d.page_content)),
            reverse=True,
        )
        return scored[: self.k]


DOCS = [
    Document(page_content="蓝牙耳机保修 12 个月。", metadata={"source": "warranty.md"}),
    Document(page_content="披萨买一送一。", metadata={"source": "promo.md"}),
    Document(page_content="手机 SIM 卡激活需要实名认证。", metadata={"source": "sim.md"}),
]


def format_docs(docs: list[Document]) -> str:
    """把检索结果拼成可放进 prompt 的文本（引用溯源在这里埋点）。"""
    return "\n".join(f"[{d.metadata['source']}] {d.page_content}" for d in docs)


def build_rag_chain(retriever: BaseRetriever) -> RunnablePassthrough:
    """RAG 链：检索注入 → 模板 → Fake 模型 → 解析（main 与测试共用同一构造）。"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", "只依据提供的背景资料回答，资料里没有就明确说不知道。"),
        ("human", "背景资料：\n{context}\n\n问题：{question}"),
    ])
    model = FakeListChatModel(responses=[
        "根据 [warranty.md]：蓝牙耳机保修 12 个月。（Fake 预置）",
    ])
    from operator import itemgetter

    return (
        RunnablePassthrough.assign(
            # 类型对齐关键点：assign 收到的输入是 dict，Retriever 只吃 str——
            # 必须先用 itemgetter 取出 question 字符串（41.5 逐段解释的高频坑）
            context=itemgetter("question") | retriever | RunnableLambda(format_docs)
        )
        | prompt
        | model
        | StrOutputParser()
    )


def main() -> None:
    retriever = MockRetriever(docs=DOCS, k=1)
    print("[1] 自写 Retriever 的 Runnable 协议（免费获得，不是巧合——基类已经实现）：")
    print(f"    invoke('耳机保修多久') → {[d.page_content for d in retriever.invoke('耳机保修多久')]}")
    print(f"    batch(['耳机保修', '披萨优惠']) → "
          f"{[[d.page_content for d in ds] for ds in retriever.batch(['耳机保修', '披萨优惠'])]}")
    print(f"    type = {type(retriever).__name__}（BaseRetriever 子类，天然是 Runnable）")

    print("\n[2] RAG 链组装：检索注入 → 模板 → Fake 模型 → 解析（全链真实运行）：")
    rag_chain = build_rag_chain(retriever)
    answer = rag_chain.invoke({"question": "耳机保修多久？"})
    print(f"    最终回答：{answer}")
    print("\n[3] 管道里各环节的输入输出类型（教材 41.4 的类型表）：")
    print("    {'question': str} → assign(context=str) → ChatPromptValue → AIMessage → str")
    print("    → 裸 SDK 版（EX-25-03）到 retrieve() 后就'手工拼字符串'了；")
    print("      LCEL 把检索、格式化、模板、生成接成一条有类型的流水线。")


if __name__ == "__main__":
    main()
