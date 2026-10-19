# tests/test_ch33.py | ch33 检索：numpy 向量检索 / BM25 / RRF 融合
"""覆盖：向量库 top-k 正确性与边界（零查询）、BM25 打分与 IDF、精确词 vs 同义改述
两路差异、RRF 融合排序性质（多路认可者优先）。"""
from __future__ import annotations

import math

import numpy as np
import pytest

from examples.ch33_retrieval.ex_33_01_numpy_vector_search import (KB_DOCS,
                                                                  NumpyVectorStore)
from examples.ch33_retrieval.ex_33_02_bm25 import BM25, CORPUS, tokenize
from examples.ch33_retrieval.ex_33_03_hybrid_rrf import CORPUS as HYBRID_CORPUS
from examples.ch33_retrieval.ex_33_03_hybrid_rrf import rrf_fuse
from examples.common.embeddings import get_embedder


def _build_store(n: int = 3) -> NumpyVectorStore:
    emb = get_embedder()
    store = NumpyVectorStore(dim=emb.dim)
    ids = [d for d, _ in KB_DOCS[:n]]
    texts = [t for _, t in KB_DOCS[:n]]
    store.add(ids, texts, emb.embed(texts))
    return store


def test_numpy_store_top1_and_sorted_order() -> None:
    emb = get_embedder()
    store = _build_store(len(KB_DOCS))
    results = store.search(emb.embed_one("笔记本键盘坏了找谁修"), top_k=3)
    assert results[0][0] == "doc_laptop"
    scores = [s for _, _, s in results]
    assert scores == sorted(scores, reverse=True)  # 降序
    assert all(-1.0 - 1e-9 <= s <= 1.0 + 1e-9 for s in scores)  # 余弦取值范围


def test_numpy_store_zero_query_returns_empty() -> None:
    emb = get_embedder()
    store = _build_store(2)
    assert store.search([0.0] * emb.dim, top_k=3) == []  # 零向量：约定返回空


def test_tokenize_cjk_bigram_and_ascii() -> None:
    assert tokenize("K3 审批") == ["k3", "审批"]
    assert "话费" in tokenize("话费")
    assert "ab" in tokenize("AB cd")  # 小写归一


def test_bm25_exact_term_beats_and_synonym_gap() -> None:
    bm25 = BM25(CORPUS)
    # 精确词：K3 只在一篇文档 → 该文档独占非零分
    hits_a = bm25.search("K3 审批流程怎么走", top_k=6)
    assert hits_a[0][0] == "doc_k3"
    assert all(d == "doc_k3" for d, _ in hits_a), "其余文档不应有 K3 相关得分"
    # 同义改述：查询与 doc_laptop 零词面重叠 → 无结果
    assert bm25.search("电脑坏了修一下要自己掏钱吗", top_k=6) == []


def test_bm25_score_zero_when_no_overlap_and_positive_when_hit() -> None:
    bm25 = BM25(CORPUS)
    assert bm25.score("话费充值", "doc_k3") == 0.0
    assert bm25.score("K3 采购审批", "doc_k3") > 0.0
    # IDF 性质：独占词的 idf 高于常见词（log((N-df+.5)/(df+.5)+1) 单调递减于 df）
    n = len(bm25.doc_ids)
    idf_unique = math.log((n - 1 + 0.5) / (1 + 0.5) + 1.0)
    idf_common = math.log((n - 2 + 0.5) / (2 + 0.5) + 1.0)
    assert idf_unique > idf_common


def test_rrf_fusion_prefers_agreed_documents() -> None:
    fused = rrf_fuse([["a", "b", "c"], ["b", "a", "d"]])
    scores = dict(fused)
    # a 与 b 两路都被认可：分数应高于只出现一路的 c/d
    assert scores["a"] > scores["c"] and scores["a"] > scores["d"]
    assert scores["b"] > scores["d"]
    # 完全互换的两路 → 并列（RRF 只看名次，与方向无关）
    tied = dict(rrf_fuse([["x", "y"], ["y", "x"]]))
    assert math.isclose(tied["x"], tied["y"], abs_tol=1e-12)
    # 融合公式抽查：1/(60+1) + 1/(60+2)
    assert math.isclose(scores["a"], 1 / 61 + 1 / 62, abs_tol=1e-12)
    assert len(fused) == len({d for r in ([["a", "b", "c"], ["b", "a", "d"]]) for d in r})
    assert set(HYBRID_CORPUS)  # 语料可用性冒烟
