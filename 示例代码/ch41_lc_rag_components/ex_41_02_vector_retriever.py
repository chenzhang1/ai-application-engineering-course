# EX-41-02 | InMemoryVectorStore：把 MockEmbedder 适配成 LangChain Embeddings | 运行: python3 示例代码/ch41_lc_rag_components/ex_41_02_vector_retriever.py
"""完整可运行（离线）：
[1] 适配器模式：全书 MockEmbedder（embed/embed_one）→ LangChain Embeddings 接口
    （embed_documents/embed_query），两个方法的分工对应"入库"与"查询"；
[2] InMemoryVectorStore（langchain-core 1.6.12 自带，无需向量库服务）增查实测；
[3] as_retriever()：向量店一步变 Runnable，直接接进 LCEL 管道。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # 仓库根

from 示例代码.公共.embeddings import MockEmbedder  # noqa: E402

from langchain_core.documents import Document  # noqa: E402
from langchain_core.embeddings import Embeddings  # noqa: E402
from langchain_core.vectorstores import InMemoryVectorStore  # noqa: E402


class MockLangChainEmbeddings(Embeddings):
    """适配器（Adapter）：把全书基座 MockEmbedder 包装成 LangChain 接口。

    Embeddings 接口只有两个方法（已核实 langchain_core.embeddings.Embeddings）：
        embed_documents(texts)  —— 批量：入库阶段给文档算向量；
        embed_query(text)       —— 单条：查询阶段给用户问题算向量。
    真实 embedding 模型接口也是这两个方法（如 OpenAIEmbeddings），换模型只换这一层。
    """

    def __init__(self, dim: int = 64) -> None:
        self._inner = MockEmbedder(dim=dim)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._inner.embed(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._inner.embed_one(text)


DOCS = [
    Document(page_content="蓝牙耳机保修 12 个月，人为损坏除外。", metadata={"source": "warranty.md"}),
    Document(page_content="披萨买一送一，活动到月底。", metadata={"source": "promo.md"}),
    Document(page_content="手机 SIM 卡激活需要实名认证。", metadata={"source": "sim.md"}),
]


def main() -> None:
    emb = MockLangChainEmbeddings()
    print("[1] 适配器接口实测（MockEmbedder 语义不变）：")
    print(f"    embed_documents(['手机'])[:3] = {[round(x, 3) for x in emb.embed_documents(['手机'])[0][:3]]}...")
    print(f"    与 embed_query('手机') 一致 = {emb.embed_documents(['手机'])[0] == emb.embed_query('手机')}")

    print("\n[2] InMemoryVectorStore：入库 + 相似度检索（纯内存，进程重启即失）：")
    store = InMemoryVectorStore(embedding=emb)
    ids = store.add_documents(DOCS)
    print(f"    add_documents → 生成 {len(ids)} 个内部 id（示例：{ids[0][:8]}...）")
    hits = store.similarity_search("手机 SIM 卡坏了怎么办", k=2)
    for d in hits:
        print(f"    命中：{d.metadata['source']:<12} {d.page_content}")
    scored = store.similarity_search_with_score("手机 SIM 卡坏了怎么办", k=1)
    print(f"    带分数：{scored[0][0].metadata['source']} score={scored[0][1]:.4f}")
    print("    → 对照 EX-25-03 手写的 8 行 numpy 检索：InMemoryVectorStore 内部就是")
    print("      'embedding + 暴力余弦 + 排序'，量小够用；上量换 FAISS/云服务，接口不变。")

    print("\n[3] as_retriever()：向量店一步变 Runnable（可进管道、可 batch）：")
    retriever = store.as_retriever(search_kwargs={"k": 1})
    docs = retriever.invoke("SIM 卡激活流程")
    print(f"    invoke → {[d.page_content for d in docs]}")
    print(f"    batch(['耳机保修', '披萨']) → {[[d.page_content for d in ds] for ds in retriever.batch(['耳机保修', '披萨'])]}")
    print(f"    type = {type(retriever).__name__}（VectorStoreRetriever，是 Runnable）")


if __name__ == "__main__":
    main()
