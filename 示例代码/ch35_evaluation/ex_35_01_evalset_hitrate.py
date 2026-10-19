# EX-35-01 | 自建评估集：检索命中率 hit@k 与 MRR 的可计算实现 | 运行: python3 示例代码/ch35_evaluation/ex_35_01_evalset_hitrate.py
"""完整可运行（MockEmbedder，真实运行输出）：RAG 改进的第一步不是改代码，
是把"好不好"变成数字。本例自建 6 条评估用例（query → 应命中的文档），
在真实检索器上计算 hit@2 与 MRR（平均倒数排名）。评估集是资产：
改切分参数、换 embedding、调阈值之后重跑，指标回退就是红线。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402

from 示例代码.公共.embeddings import get_embedder  # noqa: E402

KB_DOCS = {
    "doc_leave": "公司年假当年 12 月 31 日 24 点清零，不可结转到次年。",
    "doc_reimburse": "报销需在每月 25 日前提交，审核通过后 3 个工作日内到账。",
    "doc_vpn": "VPN 启用双因素认证，验证码收不到先检查手机时间同步。",
    "doc_meeting": "会议室开始后 15 分钟未签到自动释放。",
    "doc_travel": "一线城市住宿报销上限每晚 600 元，其他城市 400 元。",
    "doc_pizza": "披萨外卖满 30 元减 5 元。",
}

# 评估集：每行 = (qid, query, 应命中的 doc_id)。真实项目放 jsonl（见 P1 eval/evalset.jsonl）
EVALSET = [
    ("q1", "年假年底会清零吗", "doc_leave"),
    ("q2", "报销单什么时候提交", "doc_reimburse"),
    ("q3", "VPN 验证码收不到", "doc_vpn"),
    ("q4", "会议室不去会怎么样", "doc_meeting"),
    ("q5", "出差住北京酒店能报多少", "doc_travel"),
    ("q6", "出差住宿补贴上限", "doc_travel"),
]


def hit_and_mrr(emb, top_k: int = 3) -> tuple[float, float, float, list[dict[str, object]]]:
    """返回 (hit@2, hit@top_k, MRR, 明细行)。hit@k = 期望文档出现在前 k 名的比例。"""
    doc_ids = list(KB_DOCS)
    doc_vecs = np.array([emb.embed_one(KB_DOCS[d]) for d in doc_ids])
    doc_vecs = doc_vecs / np.linalg.norm(doc_vecs, axis=1, keepdims=True)
    rows: list[dict[str, object]] = []
    hits2 = 0
    hits_k = 0
    reciprocal_ranks: list[float] = []
    for qid, query, expect in EVALSET:
        q = np.asarray(emb.embed_one(query))
        q = q / np.linalg.norm(q)
        order = np.argsort(-(doc_vecs @ q))[:top_k]
        ranked = [doc_ids[i] for i in order]
        rr = 1.0 / (ranked.index(expect) + 1) if expect in ranked else 0.0
        hit2 = expect in ranked[:2]
        hits2 += hit2
        hits_k += expect in ranked
        reciprocal_ranks.append(rr)
        rows.append({"qid": qid, "query": query, "expect": expect,
                     "ranked": ranked, "hit2": hit2, "rr": rr})
    n = len(EVALSET)
    return hits2 / n, hits_k / n, sum(reciprocal_ranks) / n, rows


def main() -> None:
    emb = get_embedder()
    hit2, hit3, mrr, rows = hit_and_mrr(emb, top_k=3)
    print(f"{'qid':<4} {'query':<14} {'期望':<14} {'检索 top3（顺序即名次）':<34} hit@2  RR")
    print("-" * 92)
    for r in rows:
        ranked_str = " > ".join(str(x) for x in r["ranked"])  # type: ignore[arg-type]
        print(f"{r['qid']:<4} {str(r['query']):<14} {str(r['expect']):<14} "
              f"{ranked_str:<36} {'✓' if r['hit2'] else '✗'}    {r['rr']:.2f}")
    print("-" * 92)
    print(f"hit@2 = {hit2:.2%}（期望文档出现在前 2 名——用户点开前两条的概率视角）；"
          f"hit@3 = {hit3:.2%}；MRR = {mrr:.3f}")
    print("MRR（平均倒数排名）：命中第 1 名记 1.0，第 2 名记 0.5，第 3 名记 0.33，没命中记 0；")
    print("    它惩罚'命中但排很后'——q1 就是例子（命中在第 2 名，RR=0.50），比 hit@k 更贴近真实体验。")
    print("\n[为什么自建而不是用公开基准] 公开基准测的是通用知识；你的语料、你的分词、你的用户问法，")
    print("    只有自建评估集说了算。起步 20~50 条（覆盖高频问题+边界+应拒答），badcase 持续回填（ch28）。")
    print("[Java 对照] 这就是检索质量的集成测试：expected = 固定输入，ranked = 实现输出，")
    print("    指标 = 断言。改切分参数不改评估，等于改 SQL 不跑回归。")


if __name__ == "__main__":
    main()
