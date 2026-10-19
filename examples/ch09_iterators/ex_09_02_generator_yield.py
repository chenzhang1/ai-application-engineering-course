# EX-09-02 | 生成器函数与 yield：暂停/恢复语义（逐行观察执行轨迹）
# 运行：python3 examples/ch09_iterators/ex_09_02_generator_yield.py
"""完整可运行：用日志观察生成器在 yield 处"暂停→恢复"的全过程。"""
from __future__ import annotations

from collections.abc import Iterator


def trace_generator(steps: list[str], n: int) -> Iterator[int]:
    """生成器函数：只要函数体里出现 yield，它就不再是普通函数。"""
    steps.append("1. 生成器函数体开始执行（第一次 next 时才启动，调用时不执行！）")
    for i in range(1, n + 1):
        steps.append(f"2. 准备 yield {i}")
        steps.append(f"3. yield {i}：值交给调用方，函数在此【暂停】")
        yield i
        steps.append(f"4. 恢复执行：调用方又调了 next，i={i} 这一轮结束")
    steps.append("5. 函数体执行完毕，隐式抛出 StopIteration")


def main() -> None:
    steps: list[str] = []
    gen = trace_generator(steps, 3)

    # 关键事实：调用生成器函数不会执行任何函数体，只返回生成器对象
    print("刚创建生成器，steps =", steps)
    print("gen 是:", type(gen).__name__)

    first = next(gen)  # 执行到第一个 yield 暂停
    print(f"\nnext() -> {first}")
    print("\n".join(steps))
    steps.clear()

    second = next(gen)  # 从上次 yield 处恢复，执行到下一个 yield
    print(f"\nnext() -> {second}")
    print("\n".join(steps))
    steps.clear()

    third = next(gen)
    print(f"\nnext() -> {third}")
    print("\n".join(steps))
    steps.clear()

    try:
        next(gen)  # 函数体已走完，触发 StopIteration
    except StopIteration:
        print("\n第 4 次 next(): 抛出 StopIteration（生成器结束）")
    print("\n".join(steps))


if __name__ == "__main__":
    main()
