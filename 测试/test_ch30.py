# 测试/test_ch30.py | ch30 为什么 RAG、什么时候不用
"""覆盖：决策矩阵 token 算术、决策表完整性、RAG 检索命中、Mock 脚本驱动对照（正常/边界）。"""
from __future__ import annotations

import numpy as np
import pytest

from 示例代码.ch30_rag_why.ex_30_01_why_rag_demo import POLICY_DOCS, retrieve_top1
from 示例代码.ch30_rag_why.ex_30_02_decision_matrix import POLICY_DOCS as MATRIX_DOCS
from 示例代码.ch30_rag_why.ex_30_02_decision_matrix import QUERY, TOP_K, main as matrix_main
from 示例代码.公共.embeddings import cosine_similarity, get_embedder


def test_decision_matrix_rag_cheaper_than_full_context(capsys: pytest.CaptureFixture[str]) -> None:
    """方案 A（全量塞入）的 token 必须大于方案 B（RAG top-3）——算术层面成立。"""
    matrix_main()
    out = capsys.readouterr().out
    tokens = {}
    for line in out.splitlines():
        if "每次请求 ≈" in line:
            tokens[line.split("每次请求")[0].strip("[] ：")] = int(
                line.split("≈")[1].split("tokens")[0].strip())
    assert tokens["方案 A：长上下文全量塞入"] > tokens["方案 B：RAG 只塞 top-3"]
    assert tokens["方案 B：RAG 只塞 top-3"] > tokens["方案 C：微调（SFT）"]


def test_decision_matrix_topk_contains_expected_doc() -> None:
    """RAG 方案 top-3 必须包含 hr_leave（年假文档）——检索有效性成立。"""
    emb = get_embedder()
    q_vec = np.asarray(emb.embed_one(QUERY))
    ranked = sorted(MATRIX_DOCS.items(),
                    key=lambda kv: cosine_similarity(q_vec, np.asarray(emb.embed_one(kv[1]))),
                    reverse=True)
    assert "hr_leave" in [d for d, _ in ranked[:TOP_K]]


def test_decision_table_covers_four_options(capsys: pytest.CaptureFixture[str]) -> None:
    matrix_main()
    out = capsys.readouterr().out
    for option in ("长上下文", "RAG", "微调", "工具查询"):
        assert option in out, f"决策表缺少方案：{option}"


def test_why_rag_retrieval_hits_leave_policy() -> None:
    """EX-30-01 的极简检索必须命中年假条款（教材正文引用了该余弦值）。"""
    hit, score = retrieve_top1("年假年底会清零吗？", POLICY_DOCS)
    assert "年假" in hit and "清零" in hit
    assert score > 0.3  # 与教材 EX-30-01 输出一致（MockEmbedder 确定性）


def test_why_rag_offtopic_query_misses() -> None:
    """边界：无关问题不应命中年假条款（检索器的区分度下限）。"""
    hit, _ = retrieve_top1("食堂今天的菜单是什么", POLICY_DOCS)
    assert "年假" not in hit
