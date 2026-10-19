# EX-10-05 | 类装饰器简介：实例状态 + 注册表
# 运行：python3 示例代码/ch10_decorators/ex_10_05_class_decorator.py
"""完整可运行：当装饰逻辑需要"跨调用状态"时，用带 __call__ 的类更自然。"""
from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any


class CountCalls:
    """类装饰器：统计每个函数被调用的次数（状态存在实例上）。"""

    def __init__(self, func: Callable[..., Any]) -> None:
        functools.update_wrapper(self, func)  # 类装饰器同样要把元数据拷回来
        self.func = func
        self.calls = 0

    def __call__(self, *args: Any, **kwargs: Any) -> Any:  # 实例变可调用对象
        self.calls += 1
        print(f"  [CountCalls] {self.func.__name__} 第 {self.calls} 次调用")
        return self.func(*args, **kwargs)


@CountCalls
def ping(endpoint: str) -> str:
    return f"pong {endpoint}"


# 注册表装饰器：LangChain 的 @tool、FastAPI 的路由注册都是这个思想
TOOL_REGISTRY: dict[str, Callable[..., Any]] = {}


def register(name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """带参装饰器：把函数登记进注册表，函数本体原样返回。"""
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        TOOL_REGISTRY[name] = func
        return func  # 注意：注册器不替换函数，只做登记
    return decorator


@register("query_weather")
def query_weather(city: str) -> str:
    return f"{city}：晴，26℃"


@register("query_order")
def query_order(order_id: str) -> str:
    return f"订单 {order_id}：已发货"


def main() -> None:
    print("[1] 类装饰器跨调用计数：")
    ping("order-svc")
    ping("user-svc")
    ping("payment-svc")
    print(f"  ping 一共被调用 {ping.calls} 次（状态在实例上，函数自身做不到）")

    print("\n[2] 注册表装饰器（工具注册，LangChain @tool 同思想）：")
    for name, fn in TOOL_REGISTRY.items():
        print(f"  注册工具 {name!r}")
    print("  按名调用:", TOOL_REGISTRY["query_weather"]("上海"))
    print("  按名调用:", TOOL_REGISTRY["query_order"]("SO-2002"))


if __name__ == "__main__":
    main()
