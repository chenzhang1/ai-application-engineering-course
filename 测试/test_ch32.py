# 测试/test_ch32.py | ch32 切分：固定窗口 / 递归切分器 / 元数据设计
"""覆盖：固定切分与 overlap（正常+非法输入）、RecursiveCharacterTextSplitter 1.1.3
硬上限与边界、元数据注入与 chunk_id 唯一性。"""
from __future__ import annotations

import pytest
from langchain_text_splitters import RecursiveCharacterTextSplitter

from 示例代码.ch32_chunking.ex_32_01_fixed_window import POLICY_TEXT, fixed_split
from 示例代码.ch32_chunking.ex_32_02_recursive_splitter import (POLICY_TEXT as SPLIT_TEXT,
                                                                main as recursive_main)
from 示例代码.ch32_chunking.ex_32_03_metadata_design import DOC_META, build_chunks


def test_fixed_split_without_overlap_cuts_mid_sentence() -> None:
    chunks = fixed_split(POLICY_TEXT, size=50)
    assert all(len(c) <= 50 for c in chunks)
    assert "".join(chunks) == POLICY_TEXT  # 无损：拼回去等于原文
    assert chunks[0].endswith("病假超过三天需要")  # 教材演示的'拦腰斩断'


def test_fixed_split_with_overlap_restores_boundary() -> None:
    chunks = fixed_split(POLICY_TEXT, size=50, overlap=15)
    # 相邻块有重叠：前一块的尾部出现在后一块的开头
    assert chunks[0][-15:] in chunks[1]
    assert len(chunks) >= 3


def test_fixed_split_invalid_overlap_raises() -> None:
    with pytest.raises(ValueError, match="overlap"):
        fixed_split("abcdef", size=10, overlap=10)  # overlap == size → 死循环风险
    with pytest.raises(ValueError):
        fixed_split("abcdef", size=10, overlap=-1)


def test_recursive_splitter_respects_hard_limit() -> None:
    splitter = RecursiveCharacterTextSplitter(chunk_size=80, chunk_overlap=20,
                                              length_function=len)
    chunks = splitter.split_text(SPLIT_TEXT)
    assert all(len(c) <= 80 for c in chunks)
    assert "".join(chunks).replace("\n", "") in SPLIT_TEXT.replace("\n", "")  # 无丢失（顺序拼接覆盖原文）
    assert any(c.startswith("## 病假") for c in chunks)  # 标题留在块首的常见形态


def test_metadata_design_injects_fields_and_unique_chunk_id() -> None:
    chunks = build_chunks()
    assert len(chunks) >= 3  # 事假/年假两个小节，年假节至少切成 2 块
    ids = [c.metadata["chunk_id"] for c in chunks]
    assert len(set(ids)) == len(ids)  # chunk_id 全库唯一
    for c in chunks:
        for key in ("doc_id", "tenant_id", "department", "title", "section",
                    "start_index", "chunk_id"):
            assert key in c.metadata, f"缺元数据字段 {key}"
        assert c.metadata["doc_id"] == DOC_META["doc_id"]
        assert c.metadata["department"] == "hr"


def test_recursive_main_runs(capsys: pytest.CaptureFixture[str]) -> None:
    recursive_main()
    assert "chunk_size" in capsys.readouterr().out
