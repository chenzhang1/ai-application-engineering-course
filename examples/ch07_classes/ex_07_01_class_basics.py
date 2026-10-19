# EX-07-01 | 类与实例、实例属性 vs 类属性 | 运行: python3 examples/ch07_classes/ex_07_01_class_basics.py
class Order:
    """订单示例：演示实例属性与类属性。"""

    tax_rate: float = 0.06          # 类属性：所有实例共享（类似 Java 的 static 字段）
    _seq: int = 0

    def __init__(self, item: str, amount: float) -> None:
        self.item = item            # 实例属性：每个对象一份（在 __init__ 里绑定到 self）
        self.amount = amount
        Order._seq += 1
        self.seq = Order._seq

    def with_tax(self) -> float:
        return self.amount * (1 + self.tax_rate)


def main() -> None:
    o1 = Order("键盘", 300.0)
    o2 = Order("鼠标", 150.0)
    print(f"o1 应付 {o1.with_tax():.2f}，o2 应付 {o2.with_tax():.2f}")

    # 类属性通过类或实例都可读
    print(f"Order.tax_rate = {Order.tax_rate}，o1.tax_rate = {o1.tax_rate}")

    # 通过实例赋值只是"新建实例属性遮住类属性"，不改类本身
    o1.tax_rate = 0.0               # o1 从此有了自己的 tax_rate
    print(f"遮蔽后: o1.tax_rate = {o1.tax_rate}，o2.tax_rate = {o2.tax_rate}，Order.tax_rate = {Order.tax_rate}")
    del o1.tax_rate                 # 删掉遮蔽，重新看到类属性
    print(f"删除遮蔽后 o1.tax_rate = {o1.tax_rate}")

    # 可变类属性的共享坑（对照 ch04 的引用语义）
    class Cart:
        items: list[str] = []       # 反例：所有购物车共享同一个列表

    c1, c2 = Cart(), Cart()
    c1.items.append("书")
    print(f"可变类属性被共享: c2.items = {c2.items}")


if __name__ == "__main__":
    main()
