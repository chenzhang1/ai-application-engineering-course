# EX-59-03 | 语义缓存误命中：语义相近 ≠ 意图相同 | 运行: python3 示例代码/ch59_stability/ex_59_03_semantic_cache_mishit.py
"""完整可运行（标准库 + 共享 MockEmbedder，离线）：10 行核心代码演示语义缓存
如何"好心办坏事"——把语义相近但意图不同的查询判为命中，返回错误答案。

对比精确缓存（哈希键：不同文本绝不互串）与语义缓存（相似度键：超过阈值就互串）。
教训与边界见 59.5.3：阈值要保守、键要带业务维度、高危意图绕过缓存、可一键回退。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from 示例代码.公共.embeddings import cosine_similarity, get_embedder  # noqa: E402

emb = get_embedder()
KB: dict[str, str] = {  # "模型"的标准答案（确定性知识库，演示与模型无关——错在缓存层）
    "病假有几天": "病假每年 10 天，需提供医院证明。",
    "年假有几天": "年假入职满一年 5 天。",
}
cache: dict[str, str] = {}   # 语义缓存：key=问题文本，value=答案


def semantic_lookup(question: str, threshold: float) -> tuple[str, str]:
    """核心 10 行：先找相似度最高的历史问题，超过阈值就当命中。
    返回 (答案, 来源)；来源为 'cache:<相似问题>' 或 'miss'。"""
    best_q, best_sim = "", 0.0
    for q in cache:
        sim = cosine_similarity(emb.embed_one(question), emb.embed_one(q))
        if sim > best_sim:
            best_q, best_sim = q, sim
    if best_sim >= threshold:
        return cache[best_q], f"cache:{best_q}(相似度{best_sim:.3f})"
    return "miss", "miss"


def main() -> None:
    print("── 先建立缓存：有人问过'病假有几天' ──")
    q1 = "病假有几天"
    cache[q1] = KB[q1]
    print(f"    写入缓存：{q1!r} → {cache[q1]}")

    for threshold in (0.80, 0.90):
        q2 = "年假有几天"
        true_answer = KB[q2]
        answer, source = semantic_lookup(q2, threshold)
        hit = source.startswith("cache")
        correct = answer == true_answer
        print(f"\n── 阈值 {threshold}：新查询 {q2!r} ──")
        print(f"    缓存返回：{answer}")
        print(f"    来源：{source}  命中={hit}  正确={correct}"
              + ("  ← 误命中！语义相近（都有'X假有几天'），意图与答案完全不同" if hit and not correct else ""))

    print("\n── 对照：精确缓存（哈希键）在这个场景零风险 ──")
    print("    '年假有几天' 的哈希 ≠ '病假有几天' 的哈希 → 永不互串；代价是同义改写全 miss（命中率低）。")
    print("\n── 语义缓存的生产边界（详见 59.5.3）──")
    print("  1) 阈值保守起步（如 0.95）并按业务抽检调整——阈值是准确率/命中率的旋钮；")
    print("  2) 缓存键必须带业务维度（feature/租户/模型版本），不同业务域不共享答案空间；")
    print("  3) 高危意图（退款/权限/金额类）绕过语义缓存，宁可多花钱不可答错话；")
    print("  4) 记录'命中了哪条历史问题'（本示例的 source 字段）——排障时它是唯一线索；")
    print("  5) 语义缓存要有总开关，误命中事故时一键回退到精确缓存。")


if __name__ == "__main__":
    main()
