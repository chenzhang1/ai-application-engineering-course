"""ch05 内置数据结构：行为验证测试。

运行: python3 -m pytest 测试/test_ch05.py -q
"""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

import pytest

EX_DIR = Path(__file__).resolve().parent.parent / "示例代码" / "ch05_datastructures"


def load_module(name: str):
    import importlib.util
    from types import ModuleType

    spec = importlib.util.spec_from_file_location(name, EX_DIR / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module: ModuleType = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dict_insertion_order_and_overwrite_keeps_position() -> None:
    """dict 按插入顺序遍历（3.7+ 语言规范）；覆盖已有 key 不改变其位置。"""
    d: dict[str, int] = {}
    d["b"] = 1
    d["a"] = 2
    assert list(d) == ["b", "a"]
    d["b"] = 10
    assert list(d) == ["b", "a"]
    assert d["b"] == 10


def test_list_unhashable_tuple_hashable() -> None:
    """list 不可哈希（不能做 key）；tuple（及不含可变对象的 tuple）可以。"""
    with pytest.raises(TypeError):
        {[1, 2]: "x"}
    locations: dict[tuple[str, int], str] = {("a", 1): "ok"}
    assert locations[("a", 1)] == "ok"
    with pytest.raises(TypeError):
        hash(("a", [1]))


def test_slicing_out_of_range_safe_and_copy() -> None:
    """切片越界不报错并得到新列表；下标访问越界才报错。"""
    data = [0, 1, 2]
    assert data[5:100] == []
    sliced = data[:]
    assert sliced == data
    assert sliced is not data
    with pytest.raises(IndexError):
        _ = data[5]


def test_list_sort_returns_none() -> None:
    """sort 是原地排序返回 None（链式赋值是常见 bug）；sorted 返回新列表。"""
    nums = [2, 1]
    assert nums.sort() is None
    assert nums == [1, 2]
    assert sorted(nums, reverse=True) == [2, 1]
    assert nums == [1, 2]


def test_comprehensions_equivalent_to_filter() -> None:
    """推导式与手写循环等价。"""
    scores = {"alice": 92, "bob": 58, "carol": 77}
    passed = {n: s for n, s in scores.items() if s >= 60}
    assert passed == {"alice": 92, "carol": 77}
    names = [n for n in scores if scores[n] >= 60]
    assert names == ["alice", "carol"]
    assert [c for row in [[1, 2], [3]] for c in row] == [1, 2, 3]


def test_defaultdict_creates_on_access_counter_does_not() -> None:
    """defaultdict 访问缺失 key 会写入；Counter 访问缺失 key 返回 0 且不写入。"""
    grouped: defaultdict[int, list[str]] = defaultdict(list)
    grouped[4].append("java")
    _ = grouped[99]
    assert 99 in grouped

    counter: Counter[str] = Counter(["java", "java"])
    _ = counter["rust"]
    assert "rust" not in counter
    assert counter["java"] == 2
    assert counter.most_common(1) == [("java", 2)]


def test_star_unpacking_and_swap() -> None:
    """解包与交换语义。"""
    a, b = 1, 2
    a, b = b, a
    assert (a, b) == (2, 1)
    first, *rest = [10, 20, 30]
    assert first == 10 and rest == [20, 30]
    *init, last = [10, 20, 30]
    assert init == [10, 20] and last == 30
