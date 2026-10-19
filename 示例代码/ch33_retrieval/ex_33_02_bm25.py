# EX-33-02 | BM25 纯 Python 实现：关键词检索为什么还没死 | 运行: python3 示例代码/ch33_retrieval/ex_33_02_bm25.py
"""完整可运行（确定性程序，真实运行输出）：手写 Okapi BM25（k1=1.5, b=0.75），
在 6 篇小语料上真实运行，与向量检索（MockEmbedder）对照两组查询：
A) 精确词查询（型号 K3、工单号）——词面精准命中，BM25 赢；
B) 同义改述查询（'电脑坏了' vs 文档写'笔记本故障'）——字面零重叠，向量赢。
结论不是谁取代谁，而是混合检索（下一示例 RRF 融合）。
Java 对照：BM25 就是 Lucene/Elasticsearch 的默认打分器（相似度相似度评分），你在 Java 世界用过它。
"""
from __future__ import annotations

import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402

from 示例代码.公共.embeddings import get_embedder  # noqa: E402

_ASCII_RE = re.compile(r"[a-z0-9]+")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]+")

CORPUS = {
    "doc_k3": "K3 采购审批：金额超过 5000 元的采购需走 K3 审批流，由采购总监复核。",
    "doc_laptop": "笔记本进水属于人为损坏，维修费用由个人承担三成，需先提交设备维修工单。",
    "doc_laptop_repair": "设备维修工单由 IT 服务台派单，上门检测通常在三个工作日内完成。",
    "doc_refund": "订单签收后 7 天内可无理由退货退款，需保持包装完好。",
    "doc_weather": "雨天可在前台领取共享雨伞，48 小时内归还。",
    "doc_canteen": "食堂午餐供应时间为 11:30 到 13:00。",
}


def tokenize(text: str) -> list[str]:
    """BM25 分词：ASCII 词 + 中文 2-gram（教学实现，生产用 jieba 等分词器更准）。"""
    lowered = text.lower()
    tokens = _ASCII_RE.findall(lowered)
    for run in _CJK_RE.findall(lowered):
        if len(run) == 1:
            tokens.append(run)
        else:
            tokens.extend(run[i:i + 2] for i in range(len(run) - 1))
    return tokens


class BM25:
    """Okapi BM25。score(q,d) = Σ_t IDF(t) · tf·(k1+1) / (tf + k1·(1-b+b·|d|/avgdl))"""

    def __init__(self, corpus: dict[str, str], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.doc_ids = list(corpus)
        self.doc_tfs = {did: tokenize(text) for did, text in corpus.items()}
        self.doc_len = {did: len(tf) for did, tf in self.doc_tfs.items()}
        self.avgdl = sum(self.doc_len.values()) / len(self.doc_len)
        df: dict[str, int] = {}
        for tf in self.doc_tfs.values():
            for t in set(tf):
                df[t] = df.get(t, 0) + 1
        n = len(self.doc_ids)
        # IDF：含此词的文档越少，区分度越高（+1 防负值，BM25+ 的常用写法）
        self.idf = {t: math.log((n - d + 0.5) / (d + 0.5) + 1.0) for t, d in df.items()}

    def score(self, query: str, doc_id: str) -> float:
        tf_list = self.doc_tfs[doc_id]
        dl = self.doc_len[doc_id]
        total = 0.0
        for term in set(tokenize(query)):
            tf = tf_list.count(term)
            if tf == 0:
                continue
            idf = self.idf.get(term, 0.0)
            denom = tf + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
            total += idf * tf * (self.k1 + 1) / denom
        return total

    def search(self, query: str, top_k: int = 3) -> list[tuple[str, float]]:
        scored = sorted(((self.score(query, d), d) for d in self.doc_ids), reverse=True)
        return [(d, s) for s, d in scored[:top_k] if s > 0]


def vector_search(emb, corpus: dict[str, str], query: str, top_k: int = 3) -> list[tuple[str, float]]:
    q = np.asarray(emb.embed_one(query))
    ranked = sorted(corpus, key=lambda d: -float(np.asarray(emb.embed_one(corpus[d])) @ q))
    return [(d, float(np.asarray(emb.embed_one(corpus[d])) @ q)) for d in ranked[:top_k]]


def show(title: str, query: str, bm25_hits: list[tuple[str, float]],
         vec_hits: list[tuple[str, float]]) -> None:
    print(f"\n[{title}] 查询：{query!r}")
    for name, hits in (("BM25 ", bm25_hits), ("向量 ", vec_hits)):
        line = "  ".join(f"{d}({s:.2f})" if name.strip() == "BM25" else f"{d}({s:.3f})"
                         for d, s in hits)
        print(f"    {name} top3：{line if line else '（无结果）'}")


def main() -> None:
    bm25 = BM25(CORPUS)
    emb = get_embedder()

    bm25_a = bm25.search("K3 审批流程怎么走")
    show("实验 A：精确词查询", "K3 审批流程怎么走", bm25_a,
         vector_search(emb, CORPUS, "K3 审批流程怎么走"))
    print(f"    → BM25 以 {bm25_a[0][1]:.2f} 分断层第一：'K3'只在 1/6 篇文档出现，IDF 把区分度拉满；")
    print("      Mock 向量也把它排到了第一——但机制是'同字符串→同哈希桶'，效果近似词面匹配，")
    print("      不是语义能力（真实 embedding 模型对词表外的编号同样没有稳定语义）。")
    print("      生产经验：型号/工单号/政策编号这类精确词查询，BM25 的 IDF 加权最可靠。")

    show("实验 B：同义改述查询", "电脑坏了修一下要自己掏钱吗",
         bm25.search("电脑坏了修一下要自己掏钱吗"),
         vector_search(emb, CORPUS, "电脑坏了修一下要自己掏钱吗"))
    print("    → 向量第一、BM25 无结果：文档写'笔记本进水'，查询说'电脑坏了'——")
    print("      字面零重叠（连'电脑'二字都没沾上），BM25 得分为 0；向量把'电脑/笔记本'")
    print("      映射到同一语义方向（Mock 里是'设备'概念簇），命中成功。真实模型上这一优势更大。")

    print("\n[BM25 三个可调旋钮]")
    print("    k1（1.2~2.0）：词频饱和度——词出现 10 次不等于重要 10 倍；")
    print("    b （0~1）   ：长度惩罚——b=0.75 表示长文档的 tf 要打折；")
    print("    分词       ：中文 2-gram 是教学实现，生产用真分词器，粒度决定召回。")
    print("[混合检索预告] A 类查询信 BM25，B 类查询信向量——所以工程答案是两路都跑、")
    print("    融合排序（EX-33-03 的 RRF）。Elasticsearch 8.x 已内建 kNN+BM25 混合查询，")
    print("    你在 Java 世界的 ES 经验可以直接迁移一半。")


if __name__ == "__main__":
    main()
