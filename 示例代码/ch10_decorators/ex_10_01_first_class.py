# EX-10-01 | 函数是一等公民：不借助 @ 语法，手动完成装饰
# 运行：python3 示例代码/ch10_decorators/ex_10_01_first_class.py
"""完整可运行：函数可以赋值、传参、返回——装饰器的全部原料。"""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any


def slow_double(x: int) -> int:
    """被装饰的目标函数（模拟一个耗时操作）。"""
    time.sleep(0.05)
    return x * 2


# 1) 函数是一等公民（first-class object）：能赋值给变量、放进容器
fn = slow_double          # 注意：slow_double 不带括号，是"函数对象本身"，不是调用
print("fn 是函数吗:", callable(fn), "| 调用结果:", fn(10))

# 2) 高阶函数（higher-order function）：接收函数 / 返回函数
def timed(func: Callable[..., Any]) -> Callable[..., Any]:
    """接收一个函数，返回一个"包了一层计时逻辑"的新函数。"""
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        result = func(*args, **kwargs)  # 调用原函数（此时才真正执行）
        elapsed_ms = (time.perf_counter() - start) * 1000
        print(f"[timed] {func.__name__} 耗时 {elapsed_ms:.2f} ms")
        return result
    return wrapper

# 3) 手动装饰（装饰器语法糖的真身）：timed(slow_double) 返回 wrapper
slow_double_timed = timed(slow_double)
print("手动装饰后调用:")
_ = slow_double_timed(21)

# 4) @deco 只是 f = deco(f) 的语法糖——以下两种写法完全等价
@timed
def slow_triple(x: int) -> int:
    time.sleep(0.05)
    return x * 3

slow_triple_manual = timed(slow_triple)  # 不写 @，自己调 timed 包一遍
print("\n@timed 版本:")
_ = slow_triple(7)
print("手动 timed(...) 版本:")
_ = slow_triple_manual(7)

# 5) 装饰的代价：名字还在，但身份已经换了（没有 functools.wraps 时）
print("\nwrapper 替换原函数后:")
print("slow_triple.__name__ =", slow_triple.__name__, "← 已不是 slow_triple！")
