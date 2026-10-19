# circular_good/a.py | EX-11-05 支撑文件：好写法之一——先定义常量，再导入"模块"而不是"名字"
"""a 模块：调整语句顺序 + 只 import 模块对象，环就解开了。"""
A_VALUE = "A"  # 先定义！b 来取 A_VALUE 时它已经存在

from circular_good import b  # 导入模块对象本身（b.greet_b 在调用时才解析）


def greet_a() -> str:
    return f"a 调用 b → {b.greet_b()}"
