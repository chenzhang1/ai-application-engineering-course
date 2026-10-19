# EX-04-01 | 一切皆对象 | 运行: python3 示例代码/ch04_objects/ex_04_01_everything_is_object.py
"""在 Python 里，整数、字符串、函数、类……全部都是对象（object）。"""
from typing import Any


def describe(value: Any, label: str) -> None:
    """打印一个值的类型与两个内省结果。"""
    print(f"{label}: 值={value!r:<14} 类型={type(value).__name__}  "
          f"是object的实例={isinstance(value, object)}")


def main() -> None:
    describe(42, "整数    ")
    describe("hello", "字符串  ")
    describe([1, 2], "列表    ")
    describe(3.14, "浮点数  ")
    describe(None, "None    ")
    describe(len, "内置函数")
    # 函数的 repr 里含内存地址（每次运行都不同），这里只看类型与归属
    print(f"自定义函数: 类型={type(describe).__name__}  "
          f"是object的实例={isinstance(describe, object)}")

    # 函数是对象：可以赋值、放进容器、当参数传
    registry: dict[str, Any] = {"求和": sum, "计数": len}
    print(f"把函数放进字典并调用: registry['求和']([1, 2, 3]) = {registry['求和']([1, 2, 3])}")

    # 类本身也是对象：类对象的类型是 type
    print(f"int 的类型是 {type(int).__name__}，type 的类型是 {type(type).__name__}")


if __name__ == "__main__":
    main()
