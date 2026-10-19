# EX-06-05 | lambda 的适用与滥用 | 运行: python3 examples/ch06_functions/ex_06_05_lambda.py
from collections.abc import Callable


def main() -> None:
    users: list[dict[str, object]] = [
        {"name": "alice", "age": 32},
        {"name": "bob", "age": 25},
        {"name": "carol", "age": 29},
    ]

    # 适用场景 1：作为 key 函数传给 sorted / max / min
    by_age = sorted(users, key=lambda u: u["age"])
    ages = [u["age"] for u in by_age]
    print(f"按年龄排序后的年龄序列: {ages}")

    # 适用场景 2：作为一次性小函数传给 map / filter（多数时候推导式更清晰）
    squares: list[int] = list(map(lambda n: n * n, range(5)))
    evens: list[int] = list(filter(lambda n: n % 2 == 0, range(10)))
    print(f"map: {squares}，filter: {evens}")

    # 滥用 1：给 lambda 起名字（PEP 8 明确不推荐）——需要复用就用 def
    # increment = lambda x: x + 1   <- 反例，不这么写
    def increment(x: int) -> int:
        return x + 1

    print(f"需要复用的函数用 def: increment(1) = {increment(1)}")

    # 滥用 2：把复杂逻辑塞进 lambda（只能写单表达式，可读性差）
    classify: Callable[[int], str] = (
        lambda s: "通过" if s >= 60 else ("补考" if s >= 40 else "重修")
    )
    print(f"嵌套三元 lambda: classify(50) = {classify(50)}   # 能看懂，但别这么写")


if __name__ == "__main__":
    main()
