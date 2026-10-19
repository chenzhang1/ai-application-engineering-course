# EX-27-01 | 对话历史管理：窗口截断（保留 system + 最近 N 轮）| 运行: python3 examples/ch27_history/ex_27_01_window_truncate.py
"""完整可运行（真实 tiktoken 计数）：把 10 条消息的历史按"保 system + 保最近 N 条"截断，
打印截断前后的 token 对比与被丢弃的内容；讨论截断的信息损失。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from examples.common.llm_client import count_tokens  # noqa: E402

HISTORY: list[dict[str, str]] = [
    {"role": "system", "content": "你是电商客服助手。用户 earlier 报过耳机故障，处理进度见历史。"},
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

KEEP_SYSTEM = 1   # system 永远保留
KEEP_RECENT = 4   # 最近 4 条消息保留


def truncate(messages: list[dict[str, str]], keep_recent: int) -> list[dict[str, str]]:
    """窗口截断：system（开头）+ 最近 keep_recent 条。

    注意 pair 完整性：assistant/tool 回答依赖它前面的提问，截断应以"轮"为单位，
    简化实现按条数截，生产实现要校验首条不是孤立的 tool/assistant 消息。
    """
    if len(messages) <= 1 + keep_recent:
        return list(messages)
    system = messages[:KEEP_SYSTEM]
    recent = messages[-keep_recent:]
    return system + recent


def total_tokens(messages: list[dict[str, str]]) -> int:
    return sum(count_tokens(m["content"])[0] for m in messages)


def main() -> None:
    print(f"[原始历史] {len(HISTORY)} 条消息，共 {total_tokens(HISTORY)} tokens")
    truncated = truncate(HISTORY, KEEP_RECENT)
    print(f"\n[截断后]   保留 system + 最近 {KEEP_RECENT} 条，共 {len(truncated)} 条，"
          f"{total_tokens(truncated)} tokens（省 {total_tokens(HISTORY) - total_tokens(truncated)}）")

    print("\n被丢弃的消息：")
    dropped = HISTORY[KEEP_SYSTEM:-KEEP_RECENT]
    for m in dropped:
        print(f"    [{m['role']}] {m['content'][:40]}")

    print("\n[保留的消息]：")
    for m in truncated:
        print(f"    [{m['role']}] {m['content'][:40]}")

    print("\n[信息损失] 最后的问题'保修从哪天开始算'需要知道'换货'这个上下文——")
    print("    恰好'换货'出现在被丢弃的第 4 条。纯截断解决成本，解决不了依赖：")
    print("    要么把关键事实固化进 system（下一条示例的摘要做法），要么牺牲预算保留更多轮。")


if __name__ == "__main__":
    main()
