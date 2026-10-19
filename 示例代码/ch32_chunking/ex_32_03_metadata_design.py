# EX-32-03 | 元数据设计：切分块带上"身份证"，检索才有据可查 | 运行: python3 示例代码/ch32_chunking/ex_32_03_metadata_design.py
"""完整可运行（真实运行输出，langchain-text-splitters 1.1.3）：切分不只是"切文本"，
每个块还要带元数据，否则检索结果无法溯源、无法过滤。演示两级切分管线：
1) MarkdownHeaderTextSplitter 按 '#/##' 标题切出"小节"，标题进元数据；
2) 对每个小节用 RecursiveCharacterTextSplitter(create_documents) 细切，
   文档级元数据（doc_id/tenant/department）自动注入每个块，最后补 chunk_id。
这套字段就是 P1 项目检索层权限过滤与引用返回的原料（ch34）。
"""
from __future__ import annotations

from langchain_core.documents import Document
from langchain_text_splitters import (MarkdownHeaderTextSplitter,
                                      RecursiveCharacterTextSplitter)

MARKDOWN_DOC = """# 员工请假制度

## 事假
事假需提前 1 个工作日申请，由直属主管审批。单次超过 3 天需部门总监加签，事假期间按日扣薪。

## 年假
年假按工龄计算，满 1 年不满 10 年每年 5 天。年假当年 12 月 31 日 24 点清零，不可结转。离职未休年假按日薪 300% 折算， HR 系统自动生成折算单。
"""

DOC_META = {"doc_id": "hr_leave_policy", "tenant_id": "acme", "department": "hr",
            "title": "员工请假制度"}


def build_chunks() -> list[Document]:
    """两级切分管线（供 main 打印与 测试/test_ch32.py 断言复用）。"""
    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#", "h1"), ("##", "h2")])
    sections = header_splitter.split_text(MARKDOWN_DOC)
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=60, chunk_overlap=10, length_function=len,
        add_start_index=True)  # add_start_index=True：块在原文中的字符偏移进元数据
    chunks: list[Document] = []
    for sec_no, sec in enumerate(sections, 1):
        sec_meta = {**DOC_META, "section": f"{DOC_META['title']}/{sec.metadata.get('h2', '')}"}
        pieces = text_splitter.create_documents([sec.page_content], metadatas=[sec_meta])
        for i, piece in enumerate(pieces):
            # chunk_id：库内唯一、人类可读、可从引用反查回文档（P1 项目的同款格式）
            piece.metadata["chunk_id"] = f"{DOC_META['doc_id']}#{sec_no:02d}{i:02d}"
            chunks.append(piece)
    return chunks


def main() -> None:
    # ---- 第一级：按标题切小节（标题层级进元数据）----
    sections = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#", "h1"), ("##", "h2")]).split_text(MARKDOWN_DOC)
    print("[第一级] MarkdownHeaderTextSplitter 按标题切小节：")
    for sec in sections:
        print(f"    元数据={sec.metadata}")
        print(f"    正文  ={sec.page_content[:30]!r}…")

    # ---- 第二级：小节内细切，并注入文档级元数据 ----
    print("\n[第二级] 小节细切 + 元数据注入（create_documents 会复制 metadatas）：")
    chunks = build_chunks()
    for c in chunks:
        print(f"    {c.metadata['chunk_id']}  start={c.metadata['start_index']:<3}"
              f" dept={c.metadata['department']}  {c.page_content[:24]!r}…")

    print("\n[元数据设计清单]（检索层要用的字段，入库时定死）")
    print("    溯源：doc_id / chunk_id / start_index —— 引用 [doc_id, chunk_id, score] 靠它（ch34）")
    print("    权限：tenant_id / department —— 检索前过滤靠它（ch34），绝不能事后补")
    print("    展示：title / section —— 前端引用卡片直接用，不用再反查原文")
    print("    排查：入库时间/版本（生产建议）—— 文档更新后能解释'为什么新旧答案不一样'")
    print("\n[Java 对照] chunk 元数据 ≈ 索引文档的 stored fields（Lucene/Elasticsearch 术语），")
    print("    '检索返回的不只是正文，还有随行的身份信息'——同一件事，同一设计动机。")


if __name__ == "__main__":
    main()
