# circular_good/b.py | EX-11-05 支撑文件：好写法之二——保持顶层 from-import 不变
"""b 模块：因为 a 已经把 A_VALUE 定义放在导入语句之前，这里能顺利拿到。"""
from circular_good.a import A_VALUE


def greet_b() -> str:
    return f"b 使用 {A_VALUE}"
