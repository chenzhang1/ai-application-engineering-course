# EX-06-02 | *args/**kwargs 与 keyword-only | 运行: python3 示例代码/ch06_functions/ex_06_02_args_kwargs.py
def demo(a: int, b: int = 2, *args: int, flag: bool = False, **kwargs: object) -> None:
    print(f"a = {a}, b = {b}")
    print(f"args = {args}")
    print(f"flag = {flag}")
    print(f"kwargs = {kwargs}")


def create_user(name: str, *, is_admin: bool = False, timeout: int = 30) -> str:
    """* 之后的参数只能按关键字传递（keyword-only）。"""
    role = "admin" if is_admin else "user"
    return f"{name}({role}, timeout={timeout})"


def main() -> None:
    demo(1, 20, 30, 40, flag=True, extra="hello")
    print("-" * 40)

    seq = [10, 20, 30]
    mapping = {"flag": True, "extra": "解包传入"}
    demo(*seq, **mapping)          # 调用处解包
    print("-" * 40)

    print(create_user("alice"))
    print(create_user("bob", is_admin=True, timeout=60))

    # keyword-only 参数按位置传 -> TypeError
    try:
        create_user("carol", True)
    except TypeError as exc:
        print(f"按位置传 keyword-only 参数 -> TypeError: {exc}")


if __name__ == "__main__":
    main()
