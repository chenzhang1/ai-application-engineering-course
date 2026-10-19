"""ch04 变量与对象模型：行为验证测试。

运行: python3 -m pytest 测试/test_ch04.py -q
"""
from __future__ import annotations

import copy
import gc
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

EX_DIR = Path(__file__).resolve().parent.parent / "示例代码" / "ch04_objects"


def load_module(stem: str) -> ModuleType:
    """按文件名前缀加载示例模块（完整文件名含主题 slug）。"""
    matches = sorted(EX_DIR.glob(f"{stem}*.py"))
    assert len(matches) == 1, f"期望唯一示例文件，实际: {matches}"
    spec = importlib.util.spec_from_file_location(matches[0].stem, matches[0])
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_aliasing_is_reference_not_copy() -> None:
    """名字绑定是引用：通过 b 修改，a 同步可见（同一对象）。"""
    a: list[int] = [1, 2]
    b = a
    assert b is a
    b.append(3)
    assert a == [1, 2, 3]


def test_function_mutation_visible_rebind_invisible() -> None:
    """传参只传对象引用：原地修改对调用者可见，重新绑定不可见。"""

    def append_one(lst: list[int]) -> None:
        lst.append(99)

    def rebind(lst: list[int]) -> None:
        lst = [0]

    data: list[int] = [1]
    append_one(data)
    assert data == [1, 99]
    rebind(data)
    assert data == [1, 99]


def test_eq_vs_is_on_runtime_created_ints() -> None:
    """运行时创建的大整数：== 相等但 is 不同（小整数缓存只覆盖 -5..256）。"""
    base = 250
    big1 = base + 7
    big2 = base + 7
    assert big1 == big2
    assert big1 is not big2
    small1 = 256
    small2 = 256
    assert small1 == small2
    assert small1 is small2  # CPython 小整数缓存（实现细节，见教材 ch04）


def test_shallow_copy_shares_inner_deep_copy_not() -> None:
    """浅拷贝共享内层对象，深拷贝完全独立。"""
    src: dict[str, list[int]] = {"scores": [1]}
    shallow = copy.copy(src)
    deep = copy.deepcopy(src)
    assert shallow["scores"] is src["scores"]
    assert deep["scores"] is not src["scores"]
    shallow["scores"].append(2)
    assert src["scores"] == [1, 2]
    deep["scores"].append(9)
    assert src["scores"] == [1, 2]
    assert deep["scores"] == [1, 9]


def test_tuple_slot_immutable_but_inner_list_mutable() -> None:
    """tuple 槽位不可赋值；槽位里的可变对象仍可原地修改。"""
    record: tuple[str, list[int]] = ("scores", [90])
    record[1].append(95)
    assert record == ("scores", [90, 95])
    with pytest.raises(TypeError):
        record[0] = "new"


def test_gc_collects_reference_cycle() -> None:
    """引用计数无法回收循环引用，gc.collect 可以（分代 GC 兜底）。"""
    mod = load_module("ex_04_06_gc")
    node_a = mod.Node("a")
    node_b = mod.Node("b")
    node_a.partner = node_b
    node_b.partner = node_a
    del node_a, node_b
    collected = gc.collect()
    assert collected >= 2  # 至少回收两个互相引用的 Node
