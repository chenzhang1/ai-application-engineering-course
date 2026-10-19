# EX-05-02 | tuple 与解包 | 运行: python3 examples/ch05_datastructures/ex_05_02_tuple_unpacking.py
def min_max(values: list[int]) -> tuple[int, int]:
    """返回多个值的惯用法：本质上就是返回一个 tuple。"""
    return min(values), max(values)


def main() -> None:
    point: tuple[float, float] = (3.0, 4.0)
    x, y = point                          # 按位置解包
    print(f"x = {x}, y = {y}")

    a, b = 1, 2
    a, b = b, a                           # 交换变量：右侧先打包成 tuple 再解包
    print(f"交换后 a = {a}, b = {b}")

    first, *rest = [10, 20, 30, 40]       # 星号解包：吃掉中间任意多个
    print(f"first = {first}, rest = {rest}")
    *init, last = [10, 20, 30, 40]
    print(f"init = {init}, last = {last}")

    low, high = min_max([5, 3, 9, 1])
    print(f"min = {low}, max = {high}")

    # 单元素 tuple 必须带逗号；括号本身不制造 tuple
    single: tuple[int] = (42,)
    not_tuple: int = (42)                 # 这只是带括号的 42
    print(f"single = {single}（类型 {type(single).__name__}）；(42) 的类型是 {type(not_tuple).__name__}")

    # 解包也用于调用与字面量
    args = [1, 2, 3]
    print(f"max(*args) = {max(*args)}")
    merged_list = [*[1, 2], *[3]]
    merged_dict = {**{"a": 1}, **{"b": 2}}
    print(f"列表解包合并 = {merged_list}，字典解包合并 = {merged_dict}")


if __name__ == "__main__":
    main()
