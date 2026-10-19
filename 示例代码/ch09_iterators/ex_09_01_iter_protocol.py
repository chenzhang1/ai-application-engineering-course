# EX-09-01 | 手写迭代器：__iter__/__next 与 for 循环的真实机制
# 运行：python3 示例代码/ch09_iterators/ex_09_01_iter_protocol.py
"""完整可运行：自定义迭代器类 + for 循环的等价展开。"""
from __future__ import annotations

from collections.abc import Iterator


class Countdown:
    """一个从 start 倒数到 1 的可迭代对象（每次 for 都能重新倒数）。"""

    def __init__(self, start: int) -> None:
        self.start = start

    # 可迭代对象（Iterable）：返回一个全新的迭代器
    def __iter__(self) -> Iterator[int]:
        return CountdownIterator(self.start)


class CountdownIterator:
    """迭代器（Iterator）：真正负责"逐个吐出元素"的对象。"""

    def __init__(self, current: int) -> None:
        self.current = current

    # 迭代器的 __iter__ 返回自身（协议要求：迭代器必须可迭代）
    def __iter__(self) -> Iterator[int]:
        return self

    def __next__(self) -> int:
        if self.current <= 0:
            raise StopIteration  # 声明"没有下一个了"，for 循环靠它正常收尾
        value = self.current
        self.current -= 1
        return value


def main() -> None:
    # 1) for 循环消费可迭代对象
    for n in Countdown(3):
        print("for 循环拿到:", n)

    # 2) for 循环的等价展开：解释器实际做的事
    print("--- for 的等价展开 ---")
    it = iter(Countdown(3))       # 第一步：调用可迭代对象的 __iter__() 拿迭代器
    while True:
        try:
            n = next(it)          # 第二步：反复调用迭代器的 __next__()
        except StopIteration:     # 第三步：捕获 StopIteration 后正常退出循环
            break
        print("手动 next 拿到:", n)

    # 3) 每次 for 都拿到"新迭代器"，所以 Countdown 可重复遍历
    print("第一次:", list(Countdown(3)))
    print("第二次:", list(Countdown(3)))

    # 4) 直接对迭代器二次遍历：迭代器是一次性的（对比第 3 步）
    it2 = iter(Countdown(3))
    print("迭代器第一次消费:", list(it2))
    print("迭代器第二次消费:", list(it2))  # 已耗尽，为空


if __name__ == "__main__":
    main()
