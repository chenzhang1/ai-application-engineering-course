# EX-10-03 | 带参数装饰器（三层嵌套）：十行核心的重试装饰器
# 运行：python3 示例代码/ch10_decorators/ex_10_03_retry_decorator.py
"""完整可运行：@retry(times=3, base_delay=0.01) —— 失败自动重试。
这里是 ch15「HTTP 重试+指数退避」与 ch50 LangGraph RetryPolicy 的种子代码。
"""
from __future__ import annotations

import functools
import random
import time
from collections.abc import Callable
from typing import Any

# 装饰器工厂（decorator factory）：retry(3) 先执行，返回真正的装饰器
def retry(times: int, base_delay: float = 0.0) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """第一层：接收装饰器自己的参数（times/base_delay）。

    参数校验放在这一层，模块导入/装饰时立刻报错，而不是等到运行时。
    """
    if times < 1:
        raise ValueError(f"times 必须 >= 1，收到 {times}")

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        """第二层：接收被装饰函数，与普通装饰器一样。"""
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            """第三层：真正执行的包装逻辑——十行重试核心。"""
            for attempt in range(1, times + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:  # 教学示例从宽；生产应只捕获指定异常
                    if attempt == times:
                        raise  # 最后一次失败：把异常原样抛给调用方
                    delay = base_delay * (2 ** (attempt - 1))
                    print(f"  第 {attempt} 次失败: {type(exc).__name__}: {exc}，"
                          f"{delay:.2f}s 后重试（指数退避）")
                    time.sleep(delay)
        return wrapper
    return decorator


@retry(times=3, base_delay=0.01)
def flaky_fetch(url: str, fail_times: int) -> str:
    """模拟不稳定接口：前 fail_times 次抛异常，之后成功。"""
    if flaky_fetch.calls < fail_times:  # 用属性计数，保证输出可复现
        flaky_fetch.calls += 1
        raise ConnectionError(f"连接 {url} 超时")
    return f"200 OK from {url}"
flaky_fetch.calls = 0  # type: ignore[attr-defined]  # 教学用的可复现计数器


@retry(times=2, base_delay=0.01)
def always_fails() -> str:
    raise TimeoutError("服务端一直 503")


def main() -> None:
    random.seed(42)  # 本例不依赖随机，仅示范习惯
    print("[场景1] 前两次失败，第三次成功：")
    print("结果:", flaky_fetch("https://api.example.com/orders", fail_times=2))

    print("\n[场景2] 重试次数用尽，异常向上抛：")
    try:
        always_fails()
    except TimeoutError as exc:
        print(f"捕获到最终异常: {type(exc).__name__}: {exc}")

    print("\n[场景3] 参数非法，装饰时就报错（不用等运行）：")
    try:
        @retry(times=0)
        def _bad() -> None: ...
    except ValueError as exc:
        print(f"ValueError: {exc}")


if __name__ == "__main__":
    main()
