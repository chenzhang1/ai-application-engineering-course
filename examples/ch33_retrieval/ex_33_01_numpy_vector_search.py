# EX-33-01 | numpy 自实现余弦检索：向量检索不是 B-tree 等值索引 | 运行: python3 examples/ch33_retrieval/ex_33_01_numpy_vector_search.py
"""完整可运行（MockEmbedder，真实运行输出）：60 行实现一个可用的向量检索器——
入库（embed+L2 归一化）→ 查询（矩阵点积）→ top-k。所有向量归一化后，
点积 = 余弦相似度，一次 matmul 算完全库。重点讲清 Java 工程师最容易误解的一点：
向量检索是"相似度排序"，不是"B-tree 等值查找"——它返回的是'谁最像'，不是'谁相等'。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402

from examples.common.embeddings import get_embedder  # noqa: E402

KB_DOCS = [
    ("doc_phone", "手机的保修期为 12 个月，人为损坏不在保修范围内。"),
    ("doc_invoice", "发票在订单完成后次月统一开具，需提供订单号。"),
    ("doc_refund", "订单签收后 7 天内可无理由退货退款，需保持包装完好。"),
    ("doc_laptop", "笔记本电脑电池故障可申请售后检测，维修周期约 7 天。"),
    ("doc_weather", "雨天可在前台领取共享雨伞，48 小时内归还。"),
    ("doc_canteen", "食堂午餐供应时间为 11:30 到 13:00。"),
]


class NumpyVectorStore:
    """最小向量库：行矩阵 + 点积排序。生产换 FAISS/云向量库时替换的就是这几个方法。"""

    def __init__(self, dim: int) -> None:
        self._matrix = np.zeros((0, dim), dtype=np.float64)
        self._doc_ids: list[str] = []
        self._texts: list[str] = []

    def add(self, doc_ids: list[str], texts: list[str],
            vectors: list[list[float]]) -> None:
        """入库：向量必须 L2 归一化，归一化后点积即余弦，省去查询时重复算分母。"""
        mat = np.asarray(vectors, dtype=np.float64)
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0.0] = 1.0
        self._matrix = np.vstack([self._matrix, mat / norms])
        self._doc_ids.extend(doc_ids)
        self._texts.extend(texts)

    def search(self, query_vec: list[float], top_k: int = 3) -> list[tuple[str, str, float]]:
        q = np.asarray(query_vec, dtype=np.float64)
        norm = np.linalg.norm(q)
        if norm == 0.0:
            return []
        scores = self._matrix @ (q / norm)          # 一次 matmul：全库余弦相似度
        order = np.argsort(-scores)[:top_k]         # 按分数降序取 top-k
        return [(self._doc_ids[i], self._texts[i], float(scores[i])) for i in order]


def main() -> None:
    emb = get_embedder()
    store = NumpyVectorStore(dim=emb.dim)
    store.add([d for d, _ in KB_DOCS], [t for _, t in KB_DOCS],
              emb.embed([t for _, t in KB_DOCS]))
    print(f"[入库] {len(KB_DOCS)} 篇 → 矩阵形状 {store._matrix.shape}"
          f"（行=文档，列=向量维度）\n")

    for query in ("话费发票怎么开", "笔记本键盘坏了找谁修", "今天下班会不会下雨"):
        results = store.search(emb.embed_one(query), top_k=3)
        print(f"查询：{query!r}")
        for rank, (doc_id, text, score) in enumerate(results, 1):
            print(f"    {rank}. {score:>7.3f}  [{doc_id}] {text}")
        print()

    print("[为什么不是 B-tree] B-tree/哈希索引回答'键等于什么'，是精确匹配、O(log n)；")
    print("    向量检索回答'谁和查询最像'，没有'相等'只有排序——本质是全库相似度打分，")
    print("    本实现 O(n·d)。数据量大时用 ANN 索引（如 FAISS 的 HNSW/IVF）拿")
    print("    '近似 top-k 换亚线性延迟'——近似是特性不是缺陷，但要明白排序不再保证全局精确。")
    print("[为什么余弦] 余弦消掉向量长度只留方向：一句话和它的缩写版同向，长度不惩罚；")
    print("    归一化后点积=余弦，工程上就是把'除法'预付到入库时。")


if __name__ == "__main__":
    main()
