# EX-18-01 | pytest fixture（含 yield 前后置）与参数化
# 运行：cd /workspace/ai_application_course && python3 -m pytest examples/ch18_testing/ex_18_01_fixture_parametrize.py -v
"""Java 对照：@BeforeEach/@AfterEach + @ParameterizedTest + @CsvSource 的合体，
但 fixture 是"按名注入"（测试函数声明形参即获得实例），不靠注解扫描。"""
from __future__ import annotations

import pytest


class Cart:
    """被测对象：购物车（合成的教学例子）。"""

    def __init__(self) -> None:
        self.items: list[tuple[str, int]] = []

    def add(self, sku: str, qty: int) -> None:
        if qty <= 0:
            raise ValueError("数量必须为正")
        self.items.append((sku, qty))

    def total_qty(self) -> int:
        return sum(q for _, q in self.items)


@pytest.fixture
def cart() -> Cart:
    """setup：每个测试拿到一个新 Cart（函数级作用域，互不污染）。"""
    c = Cart()
    c.add("SKU-A", 1)
    print("\n  [setup] 已建购物车并放入 1 件 SKU-A")
    yield c  # yield 之前是 setup，之后是 teardown（对照 @AfterEach）
    print("  [teardown] 清理完成")


@pytest.mark.parametrize(
    ("sku", "qty", "expected_total"),
    [
        ("SKU-B", 1, 2),
        ("SKU-B", 3, 4),
        ("SKU-C", 10, 11),
    ],
    ids=["加1件", "加3件", "加10件"],
)
def test_add_items(cart: Cart, sku: str, qty: int, expected_total: int) -> None:
    cart.add(sku, qty)
    assert cart.total_qty() == expected_total


@pytest.mark.parametrize("bad_qty", [0, -1], ids=["零件", "负数"])
def test_add_invalid_qty(cart: Cart, bad_qty: int) -> None:
    with pytest.raises(ValueError, match="数量必须为正"):
        cart.add("SKU-B", bad_qty)
