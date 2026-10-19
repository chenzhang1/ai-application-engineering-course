"""ch08 异常体系：行为验证测试。

运行: python3 -m pytest tests/test_ch08.py -q
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

EX_DIR = Path(__file__).resolve().parent.parent / "examples" / "ch08_exceptions"


def load_module(stem: str) -> ModuleType:
    """按文件名前缀加载示例模块（完整文件名含主题 slug）。"""
    matches = sorted(EX_DIR.glob(f"{stem}*.py"))
    assert len(matches) == 1, f"期望唯一示例文件，实际: {matches}"
    spec = importlib.util.spec_from_file_location(matches[0].stem, matches[0])
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_custom_exception_hierarchy() -> None:
    """业务异常都继承 AppError：捕获基类即可处理全部业务异常。"""
    mod = load_module("ex_08_02")
    assert issubclass(mod.NotFoundError, mod.AppError)
    assert issubclass(mod.ValidationError, mod.AppError)
    assert issubclass(mod.AppError, Exception)
    try:
        mod.find_order("A4040")
        pytest.fail("应当抛出 NotFoundError")
    except mod.AppError as exc:
        assert exc.code == "NOT_FOUND"
        assert exc.detail == {"order_id": "A4040"}


def test_validation_error_carries_detail() -> None:
    """自定义异常携带结构化 detail，便于上层生成响应。"""
    mod = load_module("ex_08_02")
    try:
        mod.find_order("B2002")
        pytest.fail("应当抛出 ValidationError")
    except mod.ValidationError as exc:
        assert exc.code == "VALIDATION_ERROR"
        assert exc.detail == {"field": "order_id"}


def test_exception_chain_preserves_cause() -> None:
    """raise ... from exc 把原始异常挂到 __cause__，排查链路不丢。"""
    mod = load_module("ex_08_03")
    with pytest.raises(mod.DataLoadError) as excinfo:
        mod.load_records("/definitely/missing.json")
    assert isinstance(excinfo.value.__cause__, FileNotFoundError)


def test_from_none_suppresses_cause() -> None:
    """raise ... from None 抑制内部细节（__cause__ 为 None）。"""
    mod = load_module("ex_08_03")
    with pytest.raises(mod.DataLoadError) as excinfo:
        mod.load_records_quiet("/definitely/missing.json")
    assert excinfo.value.__cause__ is None


def test_eafp_and_lbyl_equivalent_for_missing_key() -> None:
    """EAFP 与 LBYL 对缺失 key 行为等价，风格不同。"""
    mod = load_module("ex_08_01")
    scores = {"alice": 90}
    assert mod.lbyl_get(scores, "alice") == 90
    assert mod.lbyl_get(scores, "bob") is None
    assert mod.eafp_get(scores, "alice") == 90
    assert mod.eafp_get(scores, "bob") is None


def test_contextmanager_cleanup_on_error(capsys: pytest.CaptureFixture[str]) -> None:
    """@contextmanager 的清理逻辑在异常路径下依然执行。"""
    mod = load_module("ex_08_04")
    with pytest.raises(RuntimeError):
        with mod.timer("任务"):
            raise RuntimeError("boom")
    out = capsys.readouterr().out
    assert "[任务] 开始" in out
    assert "[任务] 结束" in out  # finally 保证清理执行
