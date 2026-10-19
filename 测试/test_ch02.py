"""ch02 开发环境章节测试（EX-02-02 / EX-02-03）。

覆盖：正常路径、非法输入（缺密钥）、边界（优先级/打码/异常堆栈日志）。
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

# conftest.py 已把仓库根加入 sys.path，这里用命名空间包导入示例模块
from 示例代码.ch02_env.ex_02_02_settings_env import Settings
from 示例代码.ch02_env.ex_02_03_logging_basics import charge, configure_logging

# ---------- EX-02-02: pydantic-settings ----------


def _set_valid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_APP_NAME", "教材测试")
    monkeypatch.setenv("APP_LLM_MODE", "mock")
    monkeypatch.setenv("APP_API_KEY", "sk-demo-not-real")


def test_settings_from_env_normal(monkeypatch: pytest.MonkeyPatch) -> None:
    """正常路径：三个环境变量齐全，字段按前缀 APP_ 映射。"""
    _set_valid_env(monkeypatch)
    s = Settings(_env_file=None)
    assert s.app_name == "教材测试"
    assert s.llm_mode == "mock"
    assert s.api_key.get_secret_value() == "sk-demo-not-real"


def test_settings_missing_key_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """非法输入：必填密钥缺失时启动即失败（fail fast）。"""
    monkeypatch.delenv("APP_API_KEY", raising=False)
    monkeypatch.setenv("APP_LLM_MODE", "mock")
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)
    assert "api_key" in str(exc_info.value)


def test_settings_secretstr_masks_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """边界：SecretStr 的 repr/str 必须打码，防止日志泄漏。"""
    _set_valid_env(monkeypatch)
    s = Settings(_env_file=None)
    assert "sk-demo-not-real" not in repr(s.api_key)
    assert "sk-demo-not-real" not in str(s.api_key)


def test_settings_env_file_and_precedence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """边界：.env 文件可加载，且环境变量优先级高于 .env 文件。"""
    env_file = tmp_path / ".env"
    env_file.write_text(
        'APP_APP_NAME="来自文件"\nAPP_LLM_MODE=mock\nAPP_API_KEY=file-key-not-real\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("APP_APP_NAME", "来自环境变量")
    s = Settings(_env_file=env_file)
    assert s.app_name == "来自环境变量"  # 环境变量胜出

    monkeypatch.delenv("APP_APP_NAME")
    s2 = Settings(_env_file=env_file)
    assert s2.app_name == "来自文件"  # 回退到 .env 文件


# ---------- EX-02-03: logging ----------


def test_logging_levels_captured(caplog: pytest.LogCaptureFixture) -> None:
    """正常路径：configure_logging 后各级别日志可被捕获。"""
    configure_logging(logging.DEBUG)
    logger = logging.getLogger("demo.pay")
    with caplog.at_level(logging.DEBUG, logger="demo.pay"):
        logger.debug("调试 %s", "x")
        logger.info("信息")
        logger.warning("警告")
    levels = {r.levelname for r in caplog.records}
    assert {"DEBUG", "INFO", "WARNING"} <= levels


def test_charge_success_logs_info(caplog: pytest.LogCaptureFixture) -> None:
    """正常路径：正数金额扣款成功并记录 INFO 日志。"""
    configure_logging(logging.INFO)
    with caplog.at_level(logging.INFO, logger="demo.pay"):
        charge(100)
    assert any("扣款成功" in r.getMessage() and r.levelno == logging.INFO
               for r in caplog.records)


def test_charge_negative_logs_traceback_and_raises(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """边界：负数金额 -> logger.exception 记录堆栈并向调用方抛出。"""
    configure_logging(logging.ERROR)
    with caplog.at_level(logging.ERROR, logger="demo.pay"):
        with pytest.raises(ValueError):
            charge(-1)
    exc_records = [r for r in caplog.records if r.exc_info is not None]
    assert exc_records, "logger.exception 应记录异常堆栈"
    assert exc_records[0].exc_info[0] is ValueError


def test_logging_lazy_percent_formatting(caplog: pytest.LogCaptureFixture) -> None:
    """边界：惰性 %s 写法——记录消息时参数已合并，但原始 msg 不含拼接结果。"""
    configure_logging(logging.INFO)
    logger = logging.getLogger("demo.pay")
    with caplog.at_level(logging.INFO, logger="demo.pay"):
        logger.info("金额=%s", 42)
    record = next(r for r in caplog.records if r.getMessage() == "金额=42")
    assert record.msg == "金额=%s"  # msg 保持模板，参数惰性合并
    assert record.args == (42,)
