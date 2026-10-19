# EX-25-02 | Embedding 相似度直觉实验：手机 vs 电话 vs 披萨 | 运行: python3 示例代码/ch25_embeddings/ex_25_02_similarity_intuition.py
"""完整可运行（MockEmbedder，确定性本地向量）：验证"相似文本→相似向量"。

MockEmbedder 用小型概念词典+哈希词袋模拟语义：同概念词同方向，异概念词近似正交。
类比边界：真实 embedding 模型的语义来自大规模训练，相近但不重合；Mock 只有
"命中即相等"的粗粒度语义——教学够用，勿当真模型。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from 示例代码.公共.embeddings import cosine_similarity, get_embedder  # noqa: E402

WORDS = ["手机", "电话", "披萨", "手机支付", "天气"]


def main() -> None:
    emb = get_embedder()
    print(f"[向量器] {emb.kind}")
    vecs = {w: emb.embed_one(w) for w in WORDS}
    print(f"[维度] {len(vecs['手机'])}（已 L2 归一化）")

    print("\n[相似度矩阵]（cos ∈ [-1,1]，越接近 1 越相似）：")
    header = "        " + "".join(f"{w:>8}" for w in WORDS)
    print(header)
    for w1 in WORDS:
        row = "".join(f"{cosine_similarity(vecs[w1], vecs[w2]):>8.3f}" for w2 in WORDS)
        print(f"{w1:<8}{row}")

    s_phone_tel = cosine_similarity(vecs["手机"], vecs["电话"])
    s_phone_pizza = cosine_similarity(vecs["手机"], vecs["披萨"])
    s_phone_pay = cosine_similarity(vecs["手机"], vecs["手机支付"])
    print("\n[直觉结论]")
    print(f"    sim(手机, 电话)   = {s_phone_tel:.3f}  ← 同为通讯概念（Mock 中同方向）")
    print(f"    sim(手机, 披萨)   = {s_phone_pizza:.3f}  ← 无关概念，近似正交")
    print(f"    sim(手机, 手机支付) = {s_phone_pay:.3f}  ← 部分共享语义（通讯命中+哈希差异）")
    assert s_phone_tel > s_phone_pizza, "相似性排序应成立"
    print("    排序成立：电话 ≻ 手机支付 ≻ 披萨 —— 这正是'按语义距离检索'的基础。")

    print("\n[确定性] 同输入两次 embed 结果完全一致：",
          emb.embed_one("手机") == emb.embed_one("手机"))


if __name__ == "__main__":
    main()
