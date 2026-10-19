"""ch03 第一个程序与排障章节测试（EX-03-01 / EX-03-02 / EX-03-03）。

覆盖：正常路径、边界（版本相等/越界窗口）、非法输入（坏 JSON/除零）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from 示例代码.ch03_first_program.ex_03_01_env_check import (
    REQUIRED_MIN,
    REQUIRED_PACKAGES,
    collect_env_info,
    is_compatible,
    main as env_check_main,
)
from 示例代码.ch03_first_program.ex_03_02_traceback_demo import (
    ConfigError,
    load_config,
    ratio,
)
from 示例代码.ch03_first_program.ex_03_03_import_probe import probe

# ---------- EX-03-01: 环境体检 ----------


def test_is_compatible_normal() -> None:
    """正常路径：新版本通过。"""
    assert is_compatible((3, 14), (3, 10)) is True


def test_is_compatible_boundary() -> None:
    """边界：恰好等于下限通过；小版本差一失败。"""
    assert is_compatible((3, 10), (3, 10)) is True
    assert is_compatible((3, 9), (3, 10)) is False


def test_is_compatible_major_jump() -> None:
    """边界：主版本更高也通过（元组逐位比较）。"""
    assert is_compatible((4, 0), (3, 10)) is True


def test_collect_env_info_normal() -> None:
    """正常路径：本环境已安装 REQUIRED_PACKAGES，版本号非空且不是"缺失"。"""
    info = collect_env_info(REQUIRED_PACKAGES)
    assert info["python"] == ".".join(str(n) for n in sys.version_info[:3])
    for name in REQUIRED_PACKAGES:
        assert info[name] != "缺失"
        assert info[name] != ""


def test_collect_env_info_missing_package() -> None:
    """非法输入：不存在的包记为"缺失"，而不是抛异常。"""
    info = collect_env_info(["no-such-package-xyz"])
    assert info["no-such-package-xyz"] == "缺失"


def test_env_check_main_returns_zero_in_project_env(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """正常路径：项目环境下体检应全绿并返回 0。"""
    assert env_check_main() == 0
    out = capsys.readouterr().out
    assert "体检通过" in out


# ---------- EX-03-02: 配置加载与异常 ----------


def test_load_config_ok(tmp_path: Path) -> None:
    """正常路径：合法 JSON 读出 timeout。"""
    good = tmp_path / "config.json"
    good.write_text('{"timeout": 30}', encoding="utf-8")
    assert load_config(str(good)) == {"timeout": 30}


def test_load_config_missing_file(tmp_path: Path) -> None:
    """非法输入：文件不存在 -> FileNotFoundError（ch03 正文逐行讲解）。"""
    with pytest.raises(FileNotFoundError):
        load_config(str(tmp_path / "nope.json"))


def test_load_config_bad_json_chained(tmp_path: Path) -> None:
    """边界：坏 JSON -> ConfigError，且原始 JSONDecodeError 挂在 __cause__。"""
    bad = tmp_path / "config.json"
    bad.write_text("{不是json", encoding="utf-8")
    with pytest.raises(ConfigError) as exc_info:
        load_config(str(bad))
    assert "不是合法 JSON" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, json.JSONDecodeError)


def test_ratio_zero_division() -> None:
    """非法输入：除零真实抛 ZeroDivisionError（不吞异常）。"""
    with pytest.raises(ZeroDivisionError):
        ratio(30, 0)


# ---------- EX-03-03: 导入探针 ----------


def test_probe_reports_ok_in_project_env() -> None:
    """正常路径：本环境两个关键包都能导入并报版本。"""
    lines = probe(["pydantic", "pydantic_settings"])
    assert all(line.startswith("[OK]") for line in lines)


def test_probe_reports_fail_for_broken_package() -> None:
    """非法输入：坏包名 -> [FAIL] 且带异常类型，探针自身不崩。"""
    lines = probe(["no-such-package-xyz"])
    assert len(lines) == 1
    assert lines[0].startswith("[FAIL]")
    assert "PackageNotFoundError" in lines[0] or "ModuleNotFoundError" in lines[0]
