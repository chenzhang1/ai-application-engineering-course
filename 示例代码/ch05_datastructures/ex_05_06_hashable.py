# EX-05-06 | 可哈希性 | 运行: python3 示例代码/ch05_datastructures/ex_05_06_hashable.py
def main() -> None:
    # tuple 可哈希 -> 可以做 dict 的 key、放进 set
    locations: dict[tuple[str, int], str] = {
        ("beijing", 100000): "总部",
        ("shanghai", 200000): "分部",
    }
    print(f"tuple 作 key: {locations[('shanghai', 200000)]}")

    index: set[tuple[str, int]] = {("a", 1), ("b", 2)}
    print(f"tuple 集合: {sorted(index)}")

    # list 不可哈希 -> 不能作 key
    try:
        bad = {[1, 2]: "x"}
    except TypeError as exc:
        print(f"list 作 key -> TypeError: {exc}")

    # tuple 一旦内含 list，同样不可哈希：hash 基于内容，内容可变就无法保证稳定
    mixed: tuple[str, list[int]] = ("a", [1])
    try:
        hash(mixed)
    except TypeError as exc:
        print(f"含 list 的 tuple -> TypeError: {exc}")

    # hash 的含义：dict 内部按 hash 定位桶，因此 key 必须全程稳定
    print(f"hash('alice') 两次计算是否相等: {hash('alice') == hash('alice')}")


if __name__ == "__main__":
    main()
