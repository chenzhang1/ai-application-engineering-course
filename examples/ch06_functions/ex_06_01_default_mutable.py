# EX-06-01 | 可变默认参数陷阱 | 运行: python3 examples/ch06_functions/ex_06_01_default_mutable.py
def add_task_bad(task: str, tasks: list[str] = []) -> list[str]:
    tasks.append(task)      # 默认列表在 def 执行时创建一次，之后所有调用共享
    return tasks


def add_task_ok(task: str, tasks: list[str] | None = None) -> list[str]:
    if tasks is None:
        tasks = []          # 标准修复写法：哨兵 None，每次调用新建
    tasks.append(task)
    return tasks


def main() -> None:
    r1 = add_task_bad("a")
    r2 = add_task_bad("b")
    print(f"坏写法: r1 = {r1}")
    print(f"坏写法: r2 = {r2}（r1 也被改了）")
    print(f"两次返回同一个对象: {r1 is r2}")
    print(f"默认值本体被污染: {add_task_bad.__defaults__}")

    ok1 = add_task_ok("a")
    ok2 = add_task_ok("b")
    print(f"好写法: ok1 = {ok1}, ok2 = {ok2}")
    print(f"两次返回不同对象: {ok1 is not ok2}")


if __name__ == "__main__":
    main()
