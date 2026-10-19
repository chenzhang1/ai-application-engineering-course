# EX-11-04 | 注解不是运行时强制的：静态检查与运行时的边界
# 运行：python3 示例代码/ch11_modules_typing/ex_11_04_annotations_runtime.py
# 静态检查（另开终端，教材展示了真实输出）：
#   mypy 示例代码/ch11_modules_typing/ex_11_04_annotations_runtime.py
"""完整可运行：注解只是"元数据"，解释器默认不看它——运行时校验要靠 Pydantic（ch16）。"""
from __future__ import annotations


def double(x: int) -> int:
    """注解声称 x 是 int——但这只是给人和静态检查器看的说明。"""
    return x * 2


def price_with_tax(amount: float, rate: float) -> float:
    return amount + amount * rate


def main() -> None:
    # 1) 注解可以被内省：它们存进了函数的 __annotations__
    print("double.__annotations__ =", double.__annotations__)

    # 2) 运行时不校验：传 str 也不会立刻报错，str 自己定义了 * 的含义
    print("double('ab') =", double("ab"), " ← 注解说 int，实际 str 也'跑通了'")

    # 3) 真正的失败发生在"语义层面"：str + float 没有定义，运行到这行才崩
    try:
        price_with_tax("100", 0.13)  # 参数注解是 float，传入 str：运行时不拦
    except TypeError as exc:
        print(f"price_with_tax('100', 0.13) → 运行到运算处才崩: TypeError: {exc}")

    # 4) 同样这段代码，静态检查器（mypy/pyright）在"运行之前"就能标红——
    #    这就是"静态类型检查"与"运行时校验"的分界线：
    #    - 注解 + mypy：写代码/CI 时发现，运行时不执行、零开销
    #    - Pydantic（ch16）：运行时对真实数据（HTTP 请求体/JSON）做校验
    print("结论：注解 ≠ 运行时校验；mypy 管'源码层面'，Pydantic 管'数据层面'")


if __name__ == "__main__":
    main()
