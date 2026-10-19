# EX-27-03 | 上下文预算表：把窗口 token 分配到 system/历史/输入/回答 | 运行: python3 examples/ch27_history/ex_27_03_token_budget.py
"""完整可运行（真实 tiktoken 计数）：给定模型窗口上限，做一张预算分配表；
再演算"当前对话"对每项预算的占用，判断是否需要截断/摘要。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from examples.common.llm_client import count_tokens  # noqa: E402

# 教学基准数字（虚构模型 demo-16k，不代表任何真实产品；真实模型查官方文档）
MAX_CONTEXT = 16384
RATIOS = {"system 提示+工具声明": 0.10, "对话历史": 0.45,
          "本次输入（RAG 检索块/用户消息）": 0.30, "回答预留": 0.15}

SYSTEM_TEXT = "你是售后审核助手。" * 8
TOOLS_TEXT = '{"type":"function","function":{"name":"query_order","description":"查询订单","parameters":{"type":"object","properties":{"order_id":{"type":"string"}},"required":["order_id"]}}}'
HISTORY_TEXT = ["用户：耳机没声音，订单 ORD-77821。", "客服：已登记换货，3~5 天送达。",
                "用户：旧耳机明天取件可以吗？", "客服：取件单 48 小时内有效，可以。"]
INPUT_TEXT = "新留言：顺便问下发票什么时候开？"


def t(text: str) -> int:
    n, method = count_tokens(text)
    assert method == "tiktoken:cl100k_base"
    return n


def main() -> None:
    print(f"[预算分配表] 模型窗口 = {MAX_CONTEXT} tokens（虚构 demo-16k，用于算术演示）\n")
    print(f"{'预算项':<28} {'占比':>6} {'tokens':>8}")
    print("-" * 46)
    budgets: dict[str, int] = {}
    for name, ratio in RATIOS.items():
        budgets[name] = int(MAX_CONTEXT * ratio)
        print(f"{name:<28} {ratio:>6.0%} {budgets[name]:>8}")

    print("\n[当前占用演算]")
    usage = {
        "system 提示+工具声明": t(SYSTEM_TEXT) + t(TOOLS_TEXT),
        "对话历史": sum(t(x) for x in HISTORY_TEXT),
        "本次输入（RAG 检索块/用户消息）": t(INPUT_TEXT),
        "回答预留": 0,
    }
    ok = True
    for name, used in usage.items():
        budget = budgets[name]
        if name == "回答预留":
            print(f"    {name:<28} 占用 {used:>5} / 预算 {budget:>5}（此表计算输入侧）")
            continue
        bar = "█" * int(20 * used / budget) or "·"
        status = "OK" if used <= budget else "超支!"
        ok = ok and used <= budget
        print(f"    {name:<28} 占用 {used:>5} / 预算 {budget:>5}  {bar} {status}")

    total_used = t(SYSTEM_TEXT) + t(TOOLS_TEXT) + sum(t(x) for x in HISTORY_TEXT) + t(INPUT_TEXT)
    print(f"\n    输入侧合计 {total_used} tokens，回答预留 {budgets['回答预留']} tokens，"
          f"总计 {total_used + budgets['回答预留']} / {MAX_CONTEXT}")
    verdict = "无需处理" if ok else "需要截断/摘要（见 ex_27_01、ex_27_02）"
    print(f"    结论：{verdict}")

    print("\n[预算思维] 预算表在需求评审时就要画：工具声明 8 项、历史 50 轮、RAG 5 块×500 字——")
    print("    加起来爆没爆窗口，上线前算一遍，比线上 400 报错便宜得多。")


if __name__ == "__main__":
    main()
