# EX-06-04 | 闭包与延迟绑定经典坑 | 运行: python3 示例代码/ch06_functions/ex_06_04_closure_late_binding.py
from collections.abc import Callable


def make_functions_bad() -> list[Callable[[], int]]:
    fns: list[Callable[[], int]] = []
    for i in range(3):
        fns.append(lambda: i)      # 闭包捕获的是变量 i 本身，不是"当时的值"
    return fns


def make_functions_ok() -> list[Callable[[], int]]:
    fns: list[Callable[[], int]] = []
    for i in range(3):
        fns.append(lambda i=i: i)  # 默认参数在 def 时求值：把"当时的值"固定下来
    return fns


def multiplier(factor: int) -> Callable[[int], int]:
    """闭包的基本形态：记住定义时所处作用域里的变量。"""
    return lambda n: n * factor


def main() -> None:
    bad = make_functions_bad()
    print(f"坏写法: {[f() for f in bad]}   # 循环结束后 i = 2，三个闭包共享同一个 i")

    ok = make_functions_ok()
    print(f"好写法: {[f() for f in ok]}   # 每个闭包固定住各自的 i")

    double = multiplier(2)
    triple = multiplier(3)
    print(f"double(5) = {double(5)}，triple(5) = {triple(5)}")

    cells = [c.cell_contents for c in double.__closure__]
    print(f"double.__closure__ 捕获的内容: {cells}")


if __name__ == "__main__":
    main()
