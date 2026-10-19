# EX-11-01 | __name__ == "__main__"：模块的"直接运行"与"被导入"双身份
# 运行：python3 examples/ch11_modules_typing/ex_11_01_module_main.py
# 再试被导入视角：python3 -c "import ex_11_01_module_main"（在 examples/ch11_modules_typing/ 目录下执行）
"""完整可运行：__name__ 是每个模块自带的"身份证"，直接运行时值为 "__main__"。"""
from __future__ import annotations


def total_price(unit_price: float, quantity: int) -> float:
    """本模块对外提供的功能。"""
    return unit_price * quantity


print(f"本模块正在被谁执行？__name__ = {__name__!r}")

if __name__ == "__main__":
    # 只有"直接运行本文件"时才执行：类似 Java 的 public static void main，
    # 但 Python 没有"入口方法"的强制约定，只是一个人人遵守的惯例（惯例是强制的工程约定）
    print("→ 身份是 __main__：作为脚本直接运行，执行自测逻辑")
    print(f"自测：total_price(3.5, 4) = {total_price(3.5, 4)}")
else:
    print("→ 身份是模块名：被别的代码 import，只定义功能，不执行自测")
