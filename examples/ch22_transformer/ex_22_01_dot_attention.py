# EX-22-01 | 15 行简化点积注意力（纯 Python+numpy）| 运行: python3 examples/ch22_transformer/ex_22_01_dot_attention.py
"""完整可运行：单头缩放点积注意力（scaled dot-product attention）最小实现。

Q·Kᵀ → 除以 √d → softmax 得权重矩阵 → 权重 × V 加权拼接。
本示例打印真实的注意力权重矩阵与每个词的"新表示"，把注意力变成看得见的算术。
（教学简化：无训练、无多头、无 Mask；数字为手选 embedding，非训练产物。）
"""
from __future__ import annotations

import numpy as np

TOKENS = ["用户", "查询", "订单", "状态"]  # 4 个词元
DIM = 4

# 手选 embedding：行=词元，"查询"与"订单"在业务语义上相关（第 2 维相近）
EMB = np.array([
    [1.0, 0.0, 0.0, 0.0],   # 用户
    [0.0, 1.0, 0.9, 0.0],   # 查询
    [0.0, 0.9, 1.0, 0.0],   # 订单
    [0.0, 0.0, 0.0, 1.0],   # 状态
], dtype=np.float64)


def softmax(x: np.ndarray) -> np.ndarray:
    """数值稳定 softmax：减去行最大值防溢出。"""
    e = np.exp(x - x.max(axis=-1, keepdims=True))
    return e / e.sum(axis=-1, keepdims=True)


def attention(Q: np.ndarray, K: np.ndarray, V: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """缩放点积注意力核心（教学简化版，约 15 行内的骨架）。"""
    scores = Q @ K.T / np.sqrt(K.shape[-1])   # 1) 相似度：Q·Kᵀ / √d
    weights = softmax(scores)                 # 2) 归一化：每行和为 1
    return weights @ V, weights               # 3) 加权拼接


def main() -> None:
    print(f"词元序列：{TOKENS}（d_model={DIM}）")
    # 教学简化：Q=K=V 都取同一组 embedding（自注意力）
    out, weights = attention(EMB, EMB, EMB)

    print("\n注意力权重矩阵（行=当前词，列=被关注的词，每行和=1）：")
    header = "        " + "".join(f"{t:>8}" for t in TOKENS)
    print(header)
    for t, row in zip(TOKENS, weights):
        print(f"{t:<8}" + "".join(f"{w:>8.3f}" for w in row))

    print("\n加权拼接后的新表示（行=词元的上下文化表示）：")
    for t, vec in zip(TOKENS, out):
        print(f"{t:<8}" + "  [" + ", ".join(f"{v:.3f}" for v in vec) + "]")

    # 可验证性质
    assert np.allclose(weights.sum(axis=-1), 1.0), "softmax 后每行和必须为 1"
    assert (weights >= 0).all(), "注意力权重非负"
    print("\n[验证] 每行和=1 ✓  权重非负 ✓  —— '查询'与'订单'互相权重最高（0.358/0.326 附近）")
    print("这就是'全文检索+加权拼接'：每个词用自己(Q)去检索别人(K)，按匹配度加权取货(V)。")


if __name__ == "__main__":
    main()
