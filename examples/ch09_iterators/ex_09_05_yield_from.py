# EX-09-05 | yield from 委托与无限生成器：多层流式管道的拼图
# 运行：python3 examples/ch09_iterators/ex_09_05_yield_from.py
"""完整可运行：子生成器委托（yield from）+ 无限序列 + islice 截断。
场景原型：Agent 的多轮工具调用流（外层循环每轮产生一段流式输出，
用 yield from 把子流的 token "透传"给最外层消费者——ch50 stream 模式的形态）。
"""
from __future__ import annotations

import itertools
from collections.abc import Iterator


def counter(step: int = 1) -> Iterator[int]:
    """无限生成器：只要没人喊停，就能一直生产（消息队列/传感器流的模型）。"""
    n = 0
    while True:
        yield n
        n += step


def stream_round(round_id: int) -> Iterator[str]:
    """子生成器：模拟"一轮"的流式输出。"""
    for token in (f"[r{round_id}]", "模型", "输出", "片段", "|"):
        yield token


def agent_stream(rounds: int) -> Iterator[str]:
    """外层生成器：yield from 把每一轮的子流原样透传给最终消费者。"""
    for r in range(1, rounds + 1):
        yield from stream_round(r)   # 委托：子生成器的每个值都"直通"外层消费者
    yield "DONE"


def main() -> None:
    print("[1] yield from 透传多轮流式输出:")
    print("".join(agent_stream(3)))

    print("\n[2] 无限生成器 + islice 安全截断（取前 5 个）:")
    head = list(itertools.islice(counter(2), 5))  # islice 是消费无限流的正确姿势
    print("前 5 个:", head, "← 无限生成器也没撑爆内存")

    print("\n[3] 危险示范：直接对无限生成器 list() 会永远卡住——所以永远别这么做")


if __name__ == "__main__":
    main()
