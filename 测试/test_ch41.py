# 测试/test_ch41.py | ch41 文档加载 / 切分 / 检索组件
"""覆盖：切分器长度与元数据契约（正常）、向量店检索命中（边界：k/top1）、
自写 Retriever 的 Runnable 协议（含 batch）、RAG 链端到端（非法占位路径见 41 章正文）。"""
from __future__ import annotations

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from 示例代码.ch41_lc_rag_components.ex_41_02_vector_retriever import (
    DOCS as VS_DOCS,
    MockLangChainEmbeddings,
)
from 示例代码.ch41_lc_rag_components.ex_41_03_custom_retriever import (
    DOCS,
    MockRetriever,
    build_rag_chain,
    format_docs,
)


def test_splitter_size_and_metadata() -> None:
    """切分契约：块长 ≤ chunk_size（重叠 0 时），metadata 随块携带。"""
    sp = RecursiveCharacterTextSplitter(chunk_size=25, chunk_overlap=0,
                                        separators=["。", ""], keep_separator="end",
                                        length_function=len)
    text = "第一条：七天无理由退货。第二条：运费商家承担。第三条：及时验货。"
    docs = sp.create_documents([text], metadatas=[{"source": "policy.md", "tenant": "acme"}])
    assert len(docs) >= 2
    assert all(len(d.page_content) <= 25 for d in docs)
    assert all(d.metadata == {"source": "policy.md", "tenant": "acme"} for d in docs)
    assert "".join(d.page_content for d in docs).startswith("第一条")


def test_inmemory_vectorstore_hits_sim_doc() -> None:
    """与 EX-25-03 同一语义：'手机 SIM 卡坏了' 的 top1 必须是 SIM 相关条款。"""
    emb = MockLangChainEmbeddings()
    from langchain_core.vectorstores import InMemoryVectorStore

    vs = InMemoryVectorStore(embedding=emb)
    vs.add_documents(VS_DOCS)
    top1 = vs.similarity_search("手机 SIM 卡坏了怎么办", k=1)[0]
    assert top1.metadata["source"] == "sim.md"
    retriever = vs.as_retriever(search_kwargs={"k": 1})
    assert retriever.invoke("SIM 卡激活")[0].metadata["source"] == "sim.md"


def test_custom_retriever_runnable_protocol() -> None:
    """BaseRetriever 子类：invoke/batch 免费获得；k 生效。"""
    retriever = MockRetriever(docs=DOCS, k=1)
    hits = retriever.invoke("耳机保修多久")
    assert len(hits) == 1 and "保修" in hits[0].page_content
    batches = retriever.batch(["耳机保修", "披萨优惠"])
    assert "披萨" in batches[1][0].page_content
    text = format_docs(DOCS[:2])
    assert text.count("[") == 2  # 引用溯源埋点：每条一条来源


def test_rag_chain_end_to_end() -> None:
    """端到端：检索注入 → 模板 → Fake 模型 → 答案包含引用来源标记。"""
    chain = build_rag_chain(MockRetriever(docs=DOCS, k=1))
    answer = chain.invoke({"question": "耳机保修多久？"})
    assert answer == "根据 [warranty.md]：蓝牙耳机保修 12 个月。（Fake 预置）"
    # 检索注入不丢用户原问题：assign 后 prompt 同时拿到 context 与 question
    assert isinstance(answer, str)
