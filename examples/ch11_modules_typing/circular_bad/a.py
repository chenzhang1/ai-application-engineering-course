# circular_bad/a.py | EX-11-05 支撑文件：循环导入的坏写法
"""a 模块：顶层 from-import 了 b 的名字，而 b 又顶层 from-import a 的名字。"""
from circular_bad.b import greet_b  # ← 灾祸之源：此刻 b 也在等 a

A_VALUE = "A"  # 这行还没执行到，b 就来要 A_VALUE 了


def greet_a() -> str:
    return f"a 调用 b → {greet_b()}"
