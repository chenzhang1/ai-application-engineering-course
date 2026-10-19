"""ch07 面向对象：行为验证测试。

运行: python3 -m pytest 测试/test_ch07.py -q
"""
from __future__ import annotations

import importlib.util
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import ModuleType

import pytest

EX_DIR = Path(__file__).resolve().parent.parent / "示例代码" / "ch07_classes"


def load_module(stem: str) -> ModuleType:
    """按文件名前缀加载示例模块（完整文件名含主题 slug）。"""
    matches = sorted(EX_DIR.glob(f"{stem}*.py"))
    assert len(matches) == 1, f"期望唯一示例文件，实际: {matches}"
    spec = importlib.util.spec_from_file_location(matches[0].stem, matches[0])
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_class_attribute_shadowing_not_modifying() -> None:
    """实例赋值只是"遮蔽"类属性；del 后重新看到类属性，类本身未被修改。"""
    mod = load_module("ex_07_01")
    Order = mod.Order
    o1 = Order("键盘", 300.0)
    o2 = Order("鼠标", 150.0)
    assert Order.tax_rate == pytest.approx(0.06)
    o1.tax_rate = 0.0
    assert o1.tax_rate == 0.0
    assert o2.tax_rate == pytest.approx(0.06)
    assert Order.tax_rate == pytest.approx(0.06)
    del o1.tax_rate
    assert o1.tax_rate == pytest.approx(0.06)


def test_mutable_class_attribute_shared_between_instances() -> None:
    """可变类属性被所有实例共享（反例行为，教材 ch07 有说明）。"""

    class Cart:
        items: list[str] = []

    c1, c2 = Cart(), Cart()
    c1.items.append("书")
    assert c2.items == ["书"]


def test_magic_methods_playlist() -> None:
    """魔术方法让自定义对象支持 len/下标/迭代/相等性/哈希。"""
    mod = load_module("ex_07_02")
    p = mod.Playlist("g", ["a", "b"])
    q = mod.Playlist("g", ["a", "b"])
    assert len(p) == 2
    assert p[0] == "a" and p[-1] == "b"
    assert [s for s in p] == ["a", "b"]
    assert p == q
    assert p is not q
    assert hash(p) == hash(q)
    assert len({p, q}) == 1  # 可哈希且相等 -> set 去重
    assert repr(p).startswith("Playlist(")


def test_property_validation_and_readonly() -> None:
    """property setter 校验非法值；只有 getter 的派生属性只读。"""
    mod = load_module("ex_07_03")
    t = mod.Temperature(25.0)
    assert t.fahrenheit == pytest.approx(77.0)
    t.celsius = 100
    assert t.fahrenheit == pytest.approx(212.0)
    with pytest.raises(ValueError):
        t.celsius = -300
    with pytest.raises(AttributeError):
        t.fahrenheit = 32.0


def test_dataclass_default_factory_and_post_init() -> None:
    """default_factory 每实例新建可变默认值；__post_init__ 做统一校验。"""
    mod = load_module("ex_07_04")
    conv1 = mod.Conversation(title="t1")
    conv2 = mod.Conversation(title="t2")
    assert conv1.tags is not conv2.tags
    conv1.append(mod.ChatMessage("user", "hi"))
    assert conv1.turn == 1
    with pytest.raises(ValueError):
        mod.Conversation(title="   ")


def test_frozen_dataclass_immutable_and_hashable() -> None:
    """frozen=True 的 dataclass 不可变且可哈希。"""
    mod = load_module("ex_07_04")
    c1 = mod.ModelConfig(model="m", temperature=0.2)
    c2 = mod.ModelConfig(model="m", temperature=0.2)
    assert c1 == c2
    assert hash(c1) == hash(c2)
    with pytest.raises(FrozenInstanceError):
        c1.temperature = 0.9


def test_protocol_structural_typing() -> None:
    """Protocol 结构化子类型：有该方法即满足协议，无需继承。"""
    mod = load_module("ex_07_06")

    class Quick:
        def summarize(self) -> str:
            return "s"

    assert mod.render(Quick()) == "[摘要] s"
    assert mod.render(mod.Article("T", "b")) == "[摘要] T"

    class Missing:
        pass

    assert not isinstance(Missing(), mod.Summarizable)
    with pytest.raises(AttributeError):
        mod.render(Missing())
