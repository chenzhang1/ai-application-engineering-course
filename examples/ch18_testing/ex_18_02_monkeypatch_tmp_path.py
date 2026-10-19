# EX-18-02 | MonkeyPatch（替换环境变量/函数实现）与 tmp_path 临时目录
# 运行：cd /workspace/ai_application_course && python3 -m pytest examples/ch18_testing/ex_18_02_monkeypatch_tmp_path.py -v
"""MonkeyPatch 对照 Java：Mockito 的 when(...).thenReturn(...) + System.setProperty 的合体，
但 monkeypatch.setattr/delenv 会在测试结束时自动还原，不会污染其他测试。"""
from __future__ import annotations

import os

import pytest


def classify_by_env(score: int) -> str:
    """被测函数：依赖一个环境变量阈值（外部依赖，测试时需要隔离）。"""
    threshold = int(os.environ.get("VIP_THRESHOLD", "100"))
    return "vip" if score >= threshold else "normal"


def send_report(path) -> str:  # noqa: ANN001（教学示例省略注解以突出 monkeypatch 对象参数）
    """被测函数：把报告写进传入目录。"""
    file = path / "report.txt"
    file.write_text("ok", encoding="utf-8")
    return str(file)


def test_vip_threshold_default() -> None:
    assert classify_by_env(150) == "vip"
    assert classify_by_env(50) == "normal"


def test_vip_threshold_overridden(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIP_THRESHOLD", "200")  # 改环境变量，结束自动还原
    assert classify_by_env(150) == "normal"  # 默认实现下是 vip，阈值改高后变 normal
    assert classify_by_env(250) == "vip"


def test_with_fake_impl(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    def fake_classify(score: int) -> str:
        calls.append(score)
        return "fake"

    monkeypatch.setattr(f"{__name__}.classify_by_env", fake_classify)  # 换掉函数实现
    assert classify_by_env(1) == "fake"
    assert calls == [1]


def test_report_written_into_tmp_path(tmp_path) -> None:  # noqa: ANN001
    result = send_report(tmp_path)  # tmp_path 每个测试唯一，测试后自动清理
    assert result.endswith("report.txt")
    assert (tmp_path / "report.txt").read_text(encoding="utf-8") == "ok"
