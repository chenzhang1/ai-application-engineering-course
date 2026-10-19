# EX-21-02 | 上下文窗口预算：一次请求到底花了多少 token | 运行: python3 示例代码/ch21_tokens/ex_21_02_context_budget.py
"""完整可运行：把一次真实形态的对话消息列表逐条计数，算出 prompt 预算。

要点：上下文窗口 = 输入(prompt) + 输出(completion) 共享一个上限；
发出去的每一轮历史都会被完整重新计费——历史越长，每次请求越贵。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from 示例代码.公共.llm_client import count_tokens  # noqa: E402

# 教学基准数字（虚构模型 "demo-4k"，只用于算术演示，不代表任何真实产品）
MAX_CONTEXT_TOKENS = 4096
MAX_OUTPUT_TOKENS = 1024

MESSAGES: list[dict[str, str]] = [
    {"role": "system", "content": "你是电商客服助手，用简洁中文回答，一次不超过三句话。"},
    {"role": "user", "content": "我上周买的蓝牙耳机左耳没有声音，订单号 ORD-77821。"},
    {"role": "assistant", "content": "抱歉给您带来不便。我先帮您确认订单信息，请稍等。"},
    {"role": "user", "content": "好的，麻烦快一点，我下午要出门。"},
    {"role": "assistant", "content": "已查到订单：蓝牙耳机（白色），10 月 12 日签收。您要申请换货吗？"},
    {"role": "user", "content": "换货吧。另外我想知道新耳机多久能到？"},
]


def main() -> None:
    print(f"[假设模型] demo-4k：上下文窗口 {MAX_CONTEXT_TOKENS}，单次输出上限 {MAX_OUTPUT_TOKENS}")
    print(f"[当前对话] {len(MESSAGES)} 条消息，逐条计数：")
    total = 0
    for m in MESSAGES:
        n, method = count_tokens(m["content"])
        total += n
        print(f"    {m['role']:<9} {n:>4} tokens  （计数方式：{method}）")

    _, method = count_tokens("x")
    budget_left = MAX_CONTEXT_TOKENS - MAX_OUTPUT_TOKENS - total
    print("-" * 60)
    print(f"    prompt 合计        = {total:>4} tokens")
    print(f"    为回答预留(输出)   = {MAX_OUTPUT_TOKENS:>4} tokens")
    print(f"    窗口剩余(可再放历史/文档) = {budget_left:>4} tokens")
    print(f"    计数方式           = {method}")

    # 每轮对话都把完整历史重新计费：第 k 轮请求的费用 ≈ 前 k-1 轮累计 prompt
    print("\n[计费直觉] 对话越滚越长，每一轮都在为全部历史重新付费：")
    cum = 0
    for i, m in enumerate(MESSAGES, 1):
        n, _ = count_tokens(m["content"])
        cum += n
        print(f"    第 {i} 条消息加入后，下一次请求的 prompt ≈ {cum:>4} tokens"
              f"（{'滚雪球↑' if i > 1 else '起点'}）")

    assert total + MAX_OUTPUT_TOKENS <= MAX_CONTEXT_TOKENS, "预算爆了：需要截断或摘要（见 ch27）"
    print("\n结论：本对话可继续进行，但剩余预算有限——这正是 ch27 历史管理要解决的问题。")


if __name__ == "__main__":
    main()
