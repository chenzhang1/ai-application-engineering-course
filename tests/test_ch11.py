# ch11 模块与类型系统：正常 / 边界 / 非法输入
import importlib
import subprocess
import sys
from pathlib import Path

CH11 = Path(__file__).resolve().parent.parent / "examples" / "ch11_modules_typing"
sys.path.insert(0, str(CH11))

import pytest

import demo_shop  # noqa: E402
import ex_11_01_module_main as m01  # noqa: E402
import ex_11_03_typing_modern as m03  # noqa: E402
import ex_11_04_annotations_runtime as m04  # noqa: E402
from demo_shop import Order, calc_total  # noqa: E402
from demo_shop.core import CURRENCY  # noqa: E402


def test_main_guard_two_identities(tmp_path: Path) -> None:
    """__name__ 机制：直接运行是 __main__；被导入是模块名。"""
    proc = subprocess.run([sys.executable, str(CH11 / "ex_11_01_module_main.py")],
                          capture_output=True, text=True, check=True)
    assert "__name__ = '__main__'" in proc.stdout
    assert "身份是 __main__" in proc.stdout
    # 被导入时走 else 分支
    importlib.reload(m01)
    assert m01.__name__ == "ex_11_01_module_main"


def test_package_facade_and_pricing() -> None:
    """包门面：不必关心实现模块；定价计算正常。"""
    order = Order(order_id="SO-T", customer="测试", items=["a"], amount=100.0)
    assert calc_total(order) == 100.0
    assert calc_total(order, tax_rate=0.13) == 113.0
    assert CURRENCY == "CNY"
    assert "calc_total" in demo_shop.__all__


def test_subpackage_relative_import() -> None:
    """两级相对导入（..）可正常工作。"""
    from demo_shop.textfmt import format_receipt

    receipt = format_receipt(Order(order_id="SO-R", customer="李工",
                                   items=["键盘"], amount=99.0))
    assert "CNY 99.00" in receipt and "SO-R" in receipt


def test_import_missing_module_fails() -> None:
    """非法导入：ModuleNotFoundError 而非静默。"""
    with pytest.raises(ModuleNotFoundError):
        import demo_shop.nonexistent  # type: ignore[import-not-found]  # noqa: F401


def test_annotations_not_runtime_enforced() -> None:
    """注解≠运行时校验：str 传给 int 注解不报错；语义错误运行到才崩。"""
    assert m04.double("ab") == "abab"
    assert m04.double.__annotations__["x"] == "int"  # 注解确实存在
    with pytest.raises(TypeError):
        m04.price_with_tax("100", 0.13)


def test_typing_modern_behaviors() -> None:
    """TypedDict/Protocol/TypeVar/Callable 的运行时表现。"""
    order: m03.OrderDict = {"order_id": "SO-1", "amount": 9.9, "status": "PAID"}
    assert m03.describe(order) == "SO-1（PAID）: 9.90 元"
    assert m03.find_order("SO-404") is None                     # Optional 现代写法
    assert m03.first_or_default([], default="空") == "空"        # TypeVar 泛型
    assert m03.make_adder(100)(23) == 123                       # Callable
    assert isinstance(m03.Robot(), m03.Greeter)                 # Protocol 结构化
    assert not isinstance(m03.Stone(), m03.Greeter)


def test_circular_good_package_works() -> None:
    """循环导入的修复版可正常调用。"""
    from circular_good.a import greet_a

    assert greet_a() == "a 调用 b → b 使用 A"
