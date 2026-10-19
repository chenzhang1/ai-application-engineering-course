# EX-22-02 | 注意力="全文检索+加权拼接"类比演示 + 预训练/SFT/对齐三阶段 | 运行: python3 示例代码/ch22_transformer/ex_22_02_retrieval_analogy.py
"""完整可运行：把注意力拆成"检索打分"与"加权取货"两步，与搜索引擎类比对齐；
再用一张文字流水线图串起 预训练 → SFT → 对齐 三个阶段各自做什么（不深入数学）。
"""
from __future__ import annotations

import numpy as np

DOCS = {"用户": [1, 0, 0, 0], "查询": [0, 1, 0.9, 0], "订单": [0, 0.9, 1, 0], "状态": [0, 0, 0, 1]}


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    return float(a @ b / (na * nb)) if na and nb else 0.0


def main() -> None:
    query_word = "查询"
    q = np.array(DOCS[query_word])
    print(f"[步骤 1] 把'{query_word}'当搜索词（Query），对所有词元（Key）打相似度分：")
    scores: dict[str, float] = {}
    for word, vec in DOCS.items():
        scores[word] = cosine(q, np.array(vec, dtype=np.float64)) * np.sqrt(4)  # 模拟 √d 缩放前分值
        print(f"    score('{query_word}' → '{word}') = {scores[word]:.3f}")

    print("\n[步骤 2] softmax 把分数变成'按比例取货'的权重（和为 1）：")
    arr = np.array(list(scores.values()))
    w = np.exp(arr - arr.max())
    w = w / w.sum()
    for (word, _), weight in zip(scores.items(), w):
        print(f"    weight('{word}') = {weight:.3f}")

    print("\n[步骤 3] 加权拼接：新表示 = Σ 权重×词元向量（Value）——混合了上下文信息：")
    blended = sum(weight * np.array(DOCS[word], dtype=np.float64)
                  for (word, _), weight in zip(scores.items(), w))
    print("    '" + query_word + "' 的新向量 = [" + ", ".join(f"{x:.3f}" for x in blended) + "]")
    print("    注意：它不再是孤立词向量，而带上了'订单/状态'的语义成分——这就是上下文。")

    print("\n" + "=" * 62)
    print("三阶段流水线（各一句话，详见教材 22.3）：")
    print("""
  海量互联网文本 ──▶ [预训练] 学"接话"：给前文预测下一个词
                          │  产物：会说话但不听话、知识停留在训练截止日
                          ▼
       问答示例数据 ──▶ [SFT 监督微调] 学"按指令的格式回答"
                          │  产物：像助手了，但偏好不稳定、可能输出有害内容
                          ▼
       人类偏好数据 ──▶ [对齐(RLHF/偏好优化)] 学"人类更喜欢的那种回答"
                          │  产物：更礼貌、更安全、更"助手化"（也更会客套与拒答）
                          ▼
                    部署成你在 API 里调到的 chat 模型""")
    print("类比边界：预训练=读书识字，SFT=岗前培训话术，对齐=服务规范；")
    print("应用工程师通常只做'把知识塞进上下文'（RAG）与'把要求写进指令'（Prompt），不改这三步。")


if __name__ == "__main__":
    main()
