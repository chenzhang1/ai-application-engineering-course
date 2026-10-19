# EX-33-03 | 混合检索：RRF 融合与查询改写 | 运行: python3 examples/ch33_retrieval/ex_33_03_hybrid_rrf.py
"""完整可运行（真实运行输出）：把 BM25 与向量检索两路结果用 Reciprocal Rank Fusion
（RRF）融合排序——score(d) = Σ 1/(k + rank_i(d))，k=60（论文常用值）。
再用一个规则改写器演示"查询改写"对召回的影响（LLM 改写为脚本模拟，已标注）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402

from examples.ch33_retrieval.ex_33_02_bm25 import BM25  # noqa: E402
from examples.common.embeddings import get_embedder  # noqa: E402

CORPUS = {
    "doc_phone_warranty": "手机的保修期为 12 个月，人为损坏不在保修范围内。",
    "doc_phone_plan": "电话卡月租套餐 59 元起，流量超出部分按 0.29 元/MB 计费。",
    "doc_refund": "订单签收后 7 天内可无理由退货退款，需保持包装完好。",
    "doc_pizza": "披萨外卖满 30 元减 5 元，配送范围 3 公里。",
    "doc_rain": "雨天可在前台领取共享雨伞，48 小时内归还。",
}
RRF_K = 60


def vector_ranking(emb, query: str, top_n: int = 5) -> list[str]:
    q = np.asarray(emb.embed_one(query))
    ranked = sorted(CORPUS, key=lambda d: -float(np.asarray(emb.embed_one(CORPUS[d])) @ q))
    return ranked[:top_n]


def rrf_fuse(rankings: list[list[str]]) -> list[tuple[str, float]]:
    """RRF：每路排名给 1/(k+rank)，多路累加。只用'名次'不用原始分——两路分数量纲不同，不可直接相加。"""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (RRF_K + rank)
    return sorted(scores.items(), key=lambda kv: -kv[1])


def show(title: str, rankings: dict[str, list[str]], fused: list[tuple[str, float]]) -> None:
    print(f"\n[{title}]")
    for name, ranking in rankings.items():
        print(f"    {name}：{ranking}")
    print("    RRF 融合：" + "  ".join(f"{d}({s:.4f})" for d, s in fused))


def main() -> None:
    bm25 = BM25(CORPUS)
    emb = get_embedder()

    # ---- 场景 1：BM25 与向量各执一词，RRF 折中 ----
    query = "电话卡月租多少钱"
    bm25_hits = [d for d, s in bm25.search(query, top_k=5)]
    vec_hits = vector_ranking(emb, query)
    show(f"场景 1：{query!r}", {"BM25": bm25_hits, "向量": vec_hits},
         rrf_fuse([bm25_hits, vec_hits]))
    print("    → BM25 靠'电话卡/月租'精确命中；向量靠'电话'概念把保修页也排前面；")
    print("      融合只用名次累加，谁也不劫持谁——两路都认可的文档沉底到顶部。")

    # ---- 场景 2：查询改写 ----
    raw_query = "手机卡坏了"
    rewritten = "手机 电话卡 SIM 卡 故障 报修"  # 规则改写：同义词表展开
    print(f"\n[场景 2：查询改写] 原始查询 {raw_query!r}")
    print(f"    改写后查询：{rewritten!r}（规则同义词表：手机卡→电话卡/SIM 卡；坏了→故障/报修）")
    for tag, q in (("改写前", raw_query), ("改写后", rewritten)):
        fused = rrf_fuse([[d for d, _ in bm25.search(q, top_k=5)], vector_ranking(emb, q)])
        print(f"    {tag} top1：{fused[0][0]}（RRF {fused[0][1]:.4f}）  {CORPUS[fused[0][0]][:22]}…")
    print("    → 原始查询的'手机卡'在两路里都只沾到'手机'的边；改写把口语映射到文档词表，")
    print("      命中从'碰巧相关'变成'正中靶心'。生产改写用 LLM 做同义扩展/纠错/拆分，")
    print("      改写本身也要进评估集回归（ch35），别让它改走味。")
    print("      [Mock 边界] 本例改写是规则表演示；LLM 改写的真实效果需真实模型实测（脚本模拟见教材标注）。")

    print("\n[何时不上混合] 语料全是自由文本、无编号/型号 → BM25 增益有限，向量单路+重排即可；")
    print("    语料含大量精确词（工单号、政策编号、人名）→ 混合是免费午餐。")
    print("[Java 对照] ES 的 hybrid query（BM25+kNN+rrf）就是本例的生产形态——")
    print("    概念相同，量级不同：ES 帮你做了索引、分片与 HNSW。")


if __name__ == "__main__":
    main()
