# EX-08-04 | 上下文管理器：类实现 + contextlib | 运行: python3 示例代码/ch08_exceptions/ex_08_04_context_manager.py
import time
from collections.abc import Iterator
from contextlib import contextmanager


class Timer:
    """类实现的上下文管理器：__enter__ / __exit__。"""

    def __enter__(self) -> "Timer":
        self._start: float = time.perf_counter()
        print("计时开始")
        return self                    # as 后面拿到的就是 __enter__ 的返回值

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        elapsed = time.perf_counter() - self._start
        print(f"计时结束: {elapsed * 1000:.1f} ms")
        return False                   # False = 不吞异常（返回 True 会吞掉，慎用）


@contextmanager
def timer(label: str) -> Iterator[str]:
    """生成器实现的等价物：yield 前是 __enter__，yield 后是 __exit__。"""
    start = time.perf_counter()
    print(f"[{label}] 开始")
    try:
        yield label                    # yield 的值交给 as
    finally:
        elapsed = time.perf_counter() - start
        print(f"[{label}] 结束: {elapsed * 1000:.1f} ms（即使中途抛异常也保证执行）")


def main() -> None:
    with Timer() as t:
        sum(range(100_000))
    print("-" * 40)

    with timer("清洗") as label:
        print(f"as 拿到: {label}")
        data = [x * 2 for x in range(1000)]
        print(f"处理了 {len(data)} 条")
    print("-" * 40)

    # 异常路径：清理逻辑依然执行
    try:
        with timer("会出错的任务"):
            raise RuntimeError("模拟业务异常")
    except RuntimeError as exc:
        print(f"捕获到: {exc}")


if __name__ == "__main__":
    main()
