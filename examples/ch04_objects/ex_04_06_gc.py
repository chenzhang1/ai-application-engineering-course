# EX-04-06 | 引用计数与分代 GC（点到为止） | 运行: python3 examples/ch04_objects/ex_04_06_gc.py
import gc
import sys


class Node:
    """一个最小节点类，用于观察回收。"""

    def __init__(self, name: str) -> None:
        self.name = name
        self.partner: "Node | None" = None

    def __repr__(self) -> str:
        return f"Node({self.name!r})"


def main() -> None:
    # getrefcount 的绝对数值受解释器实现细节影响（含临时引用的处理），
    # 但"别名 +1、del -1"的趋势在 CPython 上是稳定的
    n: Node = Node("n")
    print(f"创建后引用计数: {sys.getrefcount(n)}")
    alias: Node = n
    print(f"别名绑定后引用计数: {sys.getrefcount(n)}")   # +1
    del alias
    print(f"del 别名后引用计数: {sys.getrefcount(n)}")   # -1（del 删的是名字，不是对象）

    # 引用计数处理不了"循环引用"，需要分代 GC 兜底
    a: Node = Node("a")
    b: Node = Node("b")
    a.partner = b
    b.partner = a
    del a, b                       # 外部引用消失，但两对象互相引用，计数都不为 0
    collected: int = gc.collect()  # 手动触发一次回收，返回收集到的不可达对象数
    print(f"gc.collect() 回收的不可达对象数: {collected}")


if __name__ == "__main__":
    main()
