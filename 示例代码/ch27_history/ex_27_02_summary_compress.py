# EX-27-02 | 对话历史管理：摘要压缩（旧轮次 → 一条摘要）| 运行: python3 示例代码/ch27_history/ex_27_02_summary_compress.py
"""完整可运行：把老对话压成一条"事实摘要"消息（生产中用一次便宜的模型调用完成，
本例用规则模板模拟），对比截断 vs 摘要两种策略的 token 与信息保留。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from 示例代码.公共.llm_client import count_tokens  # noqa: E402


def total_tokens(messages: list[dict[str, str]]) -> int:
    return sum(count_tokens(m["content"])[0] for m in messages)


HISTORY: list[dict[str, str]] = [
    {"role": "system", "content": "你是电商客服助手。"},
    {"role": "user", "content": "我上周买的耳机没声音，订单 ORD-77821。"},
    {"role": "assistant", "content": "已查到订单，耳机（白色）10 月 12 日签收，需要换货吗？"},
    {"role": "user", "content": "换货吧，什么时候能到？"},
    {"role": "assistant", "content": "换货已提交，预计 3~5 天送达新耳机。"},
    {"role": "user", "content": "旧耳机要寄回去吗？"},
    {"role": "assistant", "content": "是的，快递员上门取件时会带走旧耳机。"},
    {"role": "user", "content": "取件师傅说今天没空，可以明天吗？"},
    {"role": "assistant", "content": "可以，取件单 48 小时内有效，明天上门没问题。"},
    {"role": "user", "content": "那我再问下，新耳机的保修从哪天开始算？"},
]

# 生产实现：用一次小模型调用生成摘要（成本≈几百 token，只在历史超阈值时做一次）
RULE_SUMMARY = (
    "【对话摘要】用户订单 ORD-77821（耳机，白色，10-12 签收）申请换货并已提交，"
    "预计 3~5 天送达；旧耳机由快递员上门取回，取件单 48 小时内有效，用户与师傅改约明天上门。"
)


def compress(messages: list[dict[str, str]], summary: str, keep_recent: int) -> list[dict[str, str]]:
    """摘要压缩：system + 摘要消息 + 最近 N 条。摘要放在 system 之后、近期消息之前。"""
    system = [m for m in messages if m["role"] == "system"][:1]
    rest = [m for m in messages if m["role"] != "system"]
    recent = rest[-keep_recent:]
    return system + [{"role": "user", "content": summary},
                     {"role": "assistant", "content": "（已知悉以上摘要，请继续。）"}] + recent


def main() -> None:
    keep_recent = 2
    truncated = [HISTORY[0]] + HISTORY[-keep_recent:]
    compressed = compress(HISTORY, RULE_SUMMARY, keep_recent)

    print(f"[原始] {len(HISTORY)} 条 / {total_tokens(HISTORY)} tokens")
    print(f"[纯截断] 保留 {len(truncated)} 条 / {total_tokens(truncated)} tokens"
          f"（换货上下文已丢失）")
    print(f"[摘要压缩] 保留 {len(compressed)} 条 / {total_tokens(compressed)} tokens"
          f"（换货进度仍在摘要里）")
    print(f"    摘要本身：{count_tokens(RULE_SUMMARY)[0]} tokens")
    print("\n    —— 摘要消息 ——")
    print(f"    {RULE_SUMMARY}")

    print("\n[保留的近期消息]：")
    for m in compressed[-keep_recent:]:
        print(f"    [{m['role']}] {m['content'][:40]}")

    print("\n[策略对照表]")
    print(f"    {'策略':<8} {'token':>6} {'保关键事实':>10} {'成本':>14}")
    print(f"    {'纯截断':<8} {total_tokens(truncated):>6} {'否':>10} {'0（不额外调用）':>14}")
    print(f"    {'摘要压缩':<8} {total_tokens(compressed):>6} {'是':>10} {'每轮一次小模型':>14}")
    print("\n[工程建议] 混合策略：system 常驻 + 关键事实摘要 + 最近 N 轮原文；")
    print("    摘要只在历史超过阈值时做一次，且摘要必须可回放（存库），别让模型'自由发挥'摘要口径。")


if __name__ == "__main__":
    main()
