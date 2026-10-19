# EX-04-04 | 可变与不可变 | 运行: python3 示例代码/ch04_objects/ex_04_04_mutable_immutable.py
from typing import Any


def try_modify_str(s: str) -> str:
    s = s + "!"        # 不可变对象：只能新建，原对象不受影响
    return s


def try_modify_list(lst: list[Any]) -> None:
    lst.append("!")    # 可变对象：原地修改，调用者可见


def main() -> None:
    # 常见不可变类型：int/float/str/bool/tuple/frozenset/bytes
    # 常见可变类型：list/dict/set/自定义类实例（默认可变）
    greeting: str = "hello"
    modified: str = try_modify_str(greeting)
    print(f"原字符串: {greeting!r}，函数返回: {modified!r}")

    items: list[str] = ["a"]
    try_modify_list(items)
    print(f"原列表: {items}（被函数改掉了）")

    # 不可变对象内部引用可变对象：整体仍可能"变化"
    record: tuple[str, list[int]] = ("scores", [90])
    record[1].append(95)               # 合法：改的是 tuple 里的 list，不是 tuple 的槽位
    print(f"tuple 内部的 list 修改后: {record}")

    # 试图改 tuple 自己的槽位则报错
    try:
        record[0] = "new"
    except TypeError as exc:
        print(f"修改 tuple 槽位 -> TypeError: {exc}")


if __name__ == "__main__":
    main()
