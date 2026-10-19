# EX-25-03 | 语义检索 mini demo：为第六部分 RAG 铺垫 | 运行: python3 示例代码/ch25_embeddings/ex_25_03_mini_search.py
"""完整可运行（MockEmbedder）：5 句"知识库"，对 query 做 top-k 余弦检索，
打印每句得分并解释为什么关键词搜索会错、语义搜索会对（以及 Mock 的局限）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from 示例代码.公共.embeddings import cosine_similarity, get_embedder  # noqa: E402

KB = [
    "手机的保修期为 12 个月，人为损坏不在范围内。",
    "订单签收后 7 天内可无理由退货，需保持包装完好。",
    "会员积分在每年 12 月 31 日 24 点清零。",
    "配送范围覆盖全国，偏远地区运费另计。",
    "发票在订单完成后的次月统一开具。",
]
QUERY = "手机 SIM 卡坏了怎么办"  # "SIM 卡"在库里没有字面出现，语义近"手机保修"

TOP_K = 2


def main() -> None:
    emb = get_embedder()
    kb_vecs = emb.embed(KB)
    q_vec = emb.embed_one(QUERY)

    scored = sorted(
        ((cosine_similarity(q_vec, v), text) for v, text in zip(kb_vecs, KB)),
        key=lambda x: x[0], reverse=True,
    )
    print(f"Query：{QUERY!r}\n")
    print(f"{'排名':<4} {'余弦相似度':>10}  句子")
    print("-" * 64)
    for rank, (score, text) in enumerate(scored, 1):
        mark = " ← " + ("命中 top-1" if rank == 1 else f"top-{TOP_K}") if rank <= TOP_K else ""
        print(f"{rank:<4} {score:>10.3f}  {text}{mark}")

    print("\n[解读]")
    print("    1) 'SIM 卡'三个字在库里从未出现，字面匹配帮不上忙；")
    print("    2) 语义检索按向量方向找'意思最近'的句子，把保修条款排到了最前；")
    print("    3) 分数绝对值不代表'正确率'，排序与阈值（第六部分 ch33 的 Top-k 与过滤）才是工程抓手；")
    print("    4) Mock 语义是概念级的：换成词典外表述（如'摔碎了'）相似度会塌掉——")
    print("       真实 RAG 必须换真 embedding 模型，这正是第六部分的起点。")


if __name__ == "__main__":
    main()
