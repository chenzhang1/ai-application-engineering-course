"""ch06 函数与作用域：行为验证测试。

运行: python3 -m pytest 测试/test_ch06.py -q
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

EX_DIR = Path(__file__).resolve().parent.parent / "示例代码" / "ch06_functions"


def load_module(stem: str) -> ModuleType:
    """按文件名前缀加载示例模块（完整文件名含主题 slug）。"""
    matches = sorted(EX_DIR.glob(f"{stem}*.py"))
    assert len(matches) == 1, f"期望唯一示例文件，实际: {matches}"
    spec = importlib.util.spec_from_file_location(matches[0].stem, matches[0])
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_mutable_default_shared_across_calls() -> None:
    """可变默认参数在所有调用间共享同一个对象（陷阱的可执行证明）。"""
    mod = load_module("ex_06_01")
    r1 = mod.add_task_bad("a")
    r2 = mod.add_task_bad("b")
    assert r1 is r2
    assert r1 == ["a", "b"]
    # 默认值本体（__defaults__）就是那个被污染的列表
    assert mod.add_task_bad.__defaults__[0] is r1


def test_none_sentinel_fix() -> None:
    """哨兵 None 修复：每次调用新建列表，互不影响。"""
    mod = load_module("ex_06_01")
    ok1 = mod.add_task_ok("a")
    ok2 = mod.add_task_ok("b")
    assert ok1 == ["a"]
    assert ok2 == ["b"]
    assert ok1 is not ok2


def test_late_binding_lambdas() -> None:
    """闭包延迟绑定：循环里创建的 lambda 共享变量；默认参数可固定当时的值。"""
    mod = load_module("ex_06_04")
    bad = mod.make_functions_bad()
    assert [f() for f in bad] == [2, 2, 2]
    ok = mod.make_functions_ok()
    assert [f() for f in ok] == [0, 1, 2]


def test_nonlocal_accumulator() -> None:
    """nonlocal 让内层函数读写外层变量；每次调用工厂产生独立闭包。"""
    mod = load_module("ex_06_03")
    acc = mod.make_accumulator()
    assert acc(3) == 3
    assert acc(4) == 7
    other = mod.make_accumulator()
    assert other(10) == 10
    assert acc(1) == 8  # 与 other 互不影响


def test_keyword_only_reject_positional() -> None:
    """* 之后的参数只能按关键字传，按位置传抛 TypeError。"""
    mod = load_module("ex_06_02")
    assert mod.create_user("bob", is_admin=True, timeout=60) == "bob(admin, timeout=60)"
    with pytest.raises(TypeError):
        mod.create_user("carol", True)


def test_nested_scope_writes_need_declaration() -> None:
    """只读外层变量不需要声明；要写必须 nonlocal（或 global）。"""
    counter = 0

    def read() -> int:
        return counter

    def bump() -> None:
        nonlocal counter
        counter += 1

    assert read() == 0
    bump()
    assert read() == 1


def test_args_kwargs_shape() -> None:
    """*args 收集成 tuple，**kwargs 收集成 dict；调用处可解包。"""
    captured: dict[str, object] = {}

    def probe(*args: object, **kwargs: object) -> None:
        captured["args"] = args
        captured["kwargs"] = kwargs

    probe(1, 2, flag=True, extra="x")
    assert captured["args"] == (1, 2)
    assert captured["kwargs"] == {"flag": True, "extra": "x"}
