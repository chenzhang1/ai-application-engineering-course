# EX-04-03 | is 与 == 的区别 | 运行: python3 示例代码/ch04_objects/ex_04_03_is_vs_eq.py
def main() -> None:
    # 1) == 比较"值相等"，is 比较"是否同一个对象"（身份）
    list_a: list[int] = [1, 2, 3]
    list_b: list[int] = [1, 2, 3]
    print(f"list_a == list_b: {list_a == list_b}")   # True：内容相等
    print(f"list_a is list_b: {list_a is list_b}")   # False：两个不同对象

    # 2) 小整数缓存（CPython 缓存 -5..256）：两次拿到同一个对象
    small1: int = 256
    small2: int = 256
    print(f"small1 is small2 (256): {small1 is small2}")

    # 3) 运行时计算出来的 257：各自新建，值相等但不是同一个对象
    base = 250
    big1: int = base + 7     # 257，运行时创建
    big2: int = base + 7
    print(f"big1 == big2: {big1 == big2}")
    print(f"big1 is big2: {big1 is big2}")

    # 4) 字符串同理：运行时拼接得到的是新对象
    s1: str = "".join(["hel", "lo"])
    s2: str = "".join(["hel", "lo"])
    print(f"s1 == s2: {s1 == s2}, s1 is s2: {s1 is s2}")

    # 5) is 的正确用法：与 None 等哨兵对象比较
    value: str | None = None
    print(f"value is None: {value is None}")


if __name__ == "__main__":
    main()
