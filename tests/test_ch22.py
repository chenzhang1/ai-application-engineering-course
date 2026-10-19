# tests/test_ch22.py | ch22 Transformer 直觉
"""覆盖：softmax 性质（行和 1、非负）、缩放点积注意力形状、检索类比排序、
三阶段演示文件可导入可运行的结构性断言。"""
from __future__ import annotations

import numpy as np

from examples.ch22_transformer.ex_22_01_dot_attention import EMB, TOKENS, attention, softmax
from examples.ch22_transformer.ex_22_02_retrieval_analogy import DOCS, cosine


def test_softmax_rows_sum_to_one_and_nonneg() -> None:
    x = np.array([[2.0, 1.0, 0.5, 0.1], [0.0, 0.0, 0.0, 0.0]])
    p = softmax(x)
    assert np.allclose(p.sum(axis=-1), 1.0)
    assert (p >= 0).all()
    # 均匀输入 → 均匀分布
    assert np.allclose(softmax(np.zeros(4)), [0.25, 0.25, 0.25, 0.25])


def test_attention_shapes_and_self_weight() -> None:
    out, weights = attention(EMB, EMB, EMB)
    assert out.shape == (4, 4) and weights.shape == (4, 4)
    assert np.allclose(weights.sum(axis=-1), 1.0)
    assert (weights >= 0).all()
    # '查询'与'订单'互相权重应当高于对'用户'（语义相关的词元互相吸引用）
    qi = TOKENS.index("查询")
    assert weights[qi, TOKENS.index("订单")] > weights[qi, TOKENS.index("用户")]


def test_attention_out_is_convex_combination() -> None:
    """每行输出必须是 V 行向量的凸组合（权重和 1 且非负 ⇒ 界于 min/max 之间）。"""
    out, weights = attention(EMB, EMB, EMB)
    for row in out:
        assert row.min() >= EMB.min() - 1e-9
        assert row.max() <= EMB.max() + 1e-9


def test_retrieval_analogy_ranking() -> None:
    """类比实验：query='查询' 对 '订单' 的相似度仅次于自己（EX-22-02 步骤 1）。"""
    q = np.array(DOCS["查询"], dtype=np.float64)
    s_self = cosine(q, np.array(DOCS["查询"], dtype=np.float64))
    s_order = cosine(q, np.array(DOCS["订单"], dtype=np.float64))
    s_user = cosine(q, np.array(DOCS["用户"], dtype=np.float64))
    assert s_self > s_order > s_user
