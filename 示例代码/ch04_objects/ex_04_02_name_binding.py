# EX-04-02 | 名字绑定与引用语义 | 运行: python3 示例代码/ch04_objects/ex_04_02_name_binding.py
"""Python 变量是"名字贴在对象上"，不是"装值的盒子"。"""


def main() -> None:
    a: list[int] = [1, 2, 3]
    b = a                      # 不复制列表，只是给同一个对象贴了第二个名字
    b.append(4)
    print(f"b 追加元素后 a = {a}")   # a 也"变"了：a、b 指向同一个对象
    print(f"a is b: {a is b}")       # 身份相同

    x: int = 1000
    y = x                    # 名字 y 绑定到 x 所指的对象
    y = y + 1                # int 不可变：新建对象 1001，让 y 改贴到它上面
    print(f"x = {x}, y = {y}  （x 不受影响，因为 1000 这个对象从未被修改）")

    # 函数传参同样只传"对象引用"
    def append_one(lst: list[int]) -> None:
        lst.append(99)       # 原地修改：调用者可见

    def rebind(lst: list[int]) -> None:
        lst = [0]            # 只是让局部名字改贴到新对象：调用者不可见

    data = [1]
    append_one(data)
    print(f"append_one 后 data = {data}（原地修改可见）")
    rebind(data)
    print(f"rebind    后 data = {data}（重新绑定不可见）")


if __name__ == "__main__":
    main()
