# EX-06-03 | LEGB 与 global/nonlocal | 运行: python3 examples/ch06_functions/ex_06_03_legb.py
from collections.abc import Callable

counter_global: int = 0


def demo_legb() -> None:
    x: str = "local"               # Local（对 demo_legb 而言）

    def enclosing_fn() -> str:
        y: str = "enclosing"       # Enclosing

        def inner() -> str:
            z: str = "inner"       # Local（对 inner 而言）
            return f"{x}/{y}/{z}"  # 查找顺序 L -> E -> G -> B

        return inner()

    print(f"内层函数读到的名字: {enclosing_fn()}")


def read_global() -> int:
    return counter_global          # 只读全局：不需要声明


def bump_global_wrong() -> None:
    try:
        counter_global = counter_global + 1   # 出现赋值 -> Python 把它当局部变量
    except UnboundLocalError as exc:
        print(f"未声明 global 就赋值 -> UnboundLocalError: {exc}")


def bump_global_right() -> None:
    global counter_global
    counter_global += 1


def make_accumulator() -> Callable[[int], int]:
    total = 0

    def add(n: int) -> int:
        nonlocal total             # 声明"我要改外层函数的 total"
        total += n
        return total

    return add


def main() -> None:
    demo_legb()
    print(f"read_global(): {read_global()}")
    bump_global_wrong()
    bump_global_right()
    bump_global_right()
    print(f"global 计数: {counter_global}")

    acc = make_accumulator()
    print(f"acc(3) = {acc(3)}，acc(4) = {acc(4)}（闭包记住同一个 total）")


if __name__ == "__main__":
    main()
