# circular_bad/b.py | EX-11-05 支撑文件：循环导入的坏写法（另一头）
"""b 模块：顶层 from-import a.A_VALUE，与 a 互相等待，形成环。"""
from circular_bad.a import A_VALUE  # ← a 还没执行到 A_VALUE = "A"，这里拿不到


def greet_b() -> str:
    return f"b 使用 {A_VALUE}"
