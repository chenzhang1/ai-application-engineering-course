# tests/test_ch25.py | ch25 Embedding 与检索基础
"""覆盖：余弦手算值、归一化点积即余弦、相似度语义排序、mini 检索 top-k、边界（零向量/空列表）。"""
from __future__ import annotations

import math

import numpy as np

from examples.ch25_embeddings.ex_25_01_cosine_manual import A, B
from examples.common.embeddings import (
    MockEmbedder,
    cosine_similarity,
    get_embedder,
)


def test_cosine_manual_value() -> None:
    """手算基准：cos([3,4,0],[4,3,0]) = 24/25 = 0.96。"""
    assert math.isclose(float(A @ B) / (np.linalg.norm(A) * np.linalg.norm(B)), 0.96)


def test_normalized_dot_equals_cosine() -> None:
    a = MockEmbedder().embed_one("订单退款")
    b = MockEmbedder().embed_one("订单退款")
    assert math.isclose(cosine_similarity(a, b), 1.0, abs_tol=1e-9)
    assert math.isclose(sum(x * x for x in a), 1.0, abs_tol=1e-9)  # L2 归一化


def test_semantic_similarity_ordering() -> None:
    emb = MockEmbedder()
    v_phone, v_tel, v_pizza = (emb.embed_one(w) for w in ("手机", "电话", "披萨"))
    assert cosine_similarity(v_phone, v_tel) > cosine_similarity(v_phone, v_pizza)


def test_mini_search_top1_is_warranty_clause() -> None:
    """'手机 SIM 卡坏了' 应命中保修条款（EX-25-03 的语义检索结论）。"""
    from examples.ch25_embeddings.ex_25_03_mini_search import KB, QUERY

    emb = MockEmbedder()
    q = emb.embed_one(QUERY)
    scores = [cosine_similarity(q, v) for v in emb.embed(KB)]
    assert max(range(len(KB)), key=lambda i: scores[i]) == 0


def test_edge_cases() -> None:
    assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0  # 零向量约定
    assert math.isclose(cosine_similarity([1, 0], [-1, 0]), -1.0)
    assert MockEmbedder().embed([]) == []
    with __import__("pytest").raises(ValueError):  # dim 过小直接报错
        MockEmbedder(dim=4)
    import os

    os.environ["LLM_MODE"] = "bogus"
    try:
        get_embedder()
        raise AssertionError("应当抛 ValueError")
    except ValueError:
        pass
    finally:
        os.environ["LLM_MODE"] = "mock"
