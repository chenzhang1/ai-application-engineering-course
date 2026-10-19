# EX-41-01 | Document 与 RecursiveCharacterTextSplitter：复用第六部分的切分知识 | 运行: python3 examples/ch41_lc_rag_components/ex_41_01_loader_splitter.py
"""完整可运行（离线）：
[1] Document：RAG 世界的"信封"（page_content + metadata），与第六部分手写的切片对照；
[2] langchain-text-splitters 的 RecursiveCharacterTextSplitter 参数实验（中文分隔符）；
[3] loaders 简介与选型边界（langchain-community 已宣布 sunset 的实测证据）。
"""
from __future__ import annotations

import pathlib
import tempfile
import warnings

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


def main() -> None:
    print("[1] Document：最小信封（两个核心字段）：")
    doc = Document(page_content="蓝牙耳机保修 12 个月。", metadata={"source": "warranty.md", "page": 3})
    print(f"    page_content = {doc.page_content!r}")
    print(f"    metadata     = {doc.metadata}")
    print("    → 第六部分手写检索时你自建的 (text, meta) 元组，就是它（EX-25-03 的 KB 结构）")

    print("\n[2] RecursiveCharacterTextSplitter 参数实验（第六部分 ch32 的同一套直觉）：")
    text = "第一条：七天无理由退货。第二条：运费由商家承担。第三条：签收后请及时验货。" * 2
    print(f"    原文长度 = {len(text)} 字符")
    for size, overlap in [(30, 0), (30, 10), (60, 10)]:
        sp = RecursiveCharacterTextSplitter(
            chunk_size=size, chunk_overlap=overlap,
            separators=["。", "，", " ", ""],   # 中文标点优先，英文默认以 \n\n 打头
            length_function=len,                # 中文必须用 len 而非默认的 token 函数假设
            keep_separator="end",
        )
        docs = sp.create_documents([text], metadatas=[{"source": "policy.md"}])
        lens = [len(d.page_content) for d in docs]
        print(f"    chunk_size={size:>2} overlap={overlap:>2} → {len(docs)} 块，长度 {lens}")
    print("    规则：从分隔符列表自上而下找第一个'切得开'的层级，递归到块长 ≤ chunk_size；")
    print("    overlap 让相邻块共享一段尾巴，防止答案正好被切在边界上（对照 ch32 重叠切分）。")

    print("\n[3] metadata 会随块携带（引用溯源 ch34 的基础）：")
    sp = RecursiveCharacterTextSplitter(chunk_size=30, chunk_overlap=0, separators=["。", ""], keep_separator="end")
    for d in sp.create_documents([text], metadatas=[{"source": "policy.md", "tenant": "acme"}])[:2]:
        print(f"    {d.metadata} → {d.page_content[:18]}...")

    print("\n[4] loaders 简介与选型边界（诚实声明）：")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        from langchain_community.document_loaders import TextLoader  # noqa: F401

        deprecation = [str(w.message) for w in caught if "sunset" in str(w.message)]
    print(f"    from langchain_community.document_loaders import TextLoader 导入成功，")
    print(f"    但触发官方警告：{deprecation[0][:76] if deprecation else '（本次未捕获到警告）'}...")
    tmp = pathlib.Path(tempfile.mkdtemp()) / "note.txt"
    tmp.write_text("第一行文本\n第二行文本", encoding="utf-8")
    loaded = TextLoader(str(tmp), encoding="utf-8").load()
    print(f"    TextLoader.load() → {len(loaded)} 个 Document：{loaded[0].page_content!r}")
    print("    选型建议：核心包只提供 Document 与切分器；加载器按需选独立集成包，")
    print("    或者干脆自己写（第六部分 ch31 的加载/清洗代码移植性好，不锁定框架）。")


if __name__ == "__main__":
    main()
