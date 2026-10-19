# EX-10-02 | 计时装饰器 + functools.wraps 的必要性
# 运行：python3 示例代码/ch10_decorators/ex_10_02_timer_decorator.py
"""完整可运行：对比"不加 wraps"与"加 wraps"后的函数元数据。"""
from __future__ import annotations

import functools
import time
from collections.abc import Callable
from typing import Any


def timed_naive(func: Callable[..., Any]) -> Callable[..., Any]:
    """不加 functools.wraps：元数据丢失。"""
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        result = func(*args, **kwargs)
        print(f"[timed_naive] {func.__name__} 耗时 {(time.perf_counter() - start) * 1000:.2f} ms")
        return result
    return wrapper


def timed(func: Callable[..., Any]) -> Callable[..., Any]:
    """生产写法：functools.wraps 把原函数的 __name__/__doc__ 等元数据拷回 wrapper。"""
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        result = func(*args, **kwargs)
        print(f"[timed] {func.__name__} 耗时 {(time.perf_counter() - start) * 1000:.2f} ms")
        return result
    return wrapper


@timed_naive
def fetch_order_naive(order_id: str) -> str:
    """查询订单（docstring 会被 timed_naive 弄丢）。"""
    time.sleep(0.02)
    return f"order:{order_id}"


@timed
def fetch_order(order_id: str) -> str:
    """查询订单（docstring 被 wraps 保留）。"""
    time.sleep(0.02)
    return f"order:{order_id}"


def main() -> None:
    print(fetch_order_naive("A001"))
    print(fetch_order("A002"))

    print("\n--- 元数据对比 ---")
    print("naive.__name__:", fetch_order_naive.__name__)          # wrapper
    print("naive.__doc__  :", fetch_order_naive.__doc__)          # None
    print("wraps.__name__:", fetch_order.__name__)                # fetch_order
    print("wraps.__doc__  :", fetch_order.__doc__)

    print("\n--- 为什么这很重要：help()/调试器/日志都会读元数据 ---")
    # debug 工具、traceback、API 文档生成器都依赖 __name__/__doc__/__qualname__
    print("带 wraps 后函数签名模块:", fetch_order.__module__)
    print("带 wraps 的 __wrapped__ 指回原函数:", fetch_order.__wrapped__.__name__)


if __name__ == "__main__":
    main()
