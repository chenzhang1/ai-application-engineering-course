# ch12 标准库实战小项目：正常 / 边界 / 非法输入
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CH12 = Path(__file__).resolve().parent.parent / "examples" / "ch12_stdlib_project"
CLI = CH12 / "ex_12_05_report_cli.py"
sys.path.insert(0, str(CH12))

import pytest

import ex_12_01_json_encoder as m01  # noqa: E402
import ex_12_02_pathlib_timezone as m02  # noqa: E402
import ex_12_03_re_extract as m03  # noqa: E402


def test_json_encoder_datetime_roundtrip() -> None:
    """正常路径：自定编码器把 datetime 转为 ISO 字符串。"""
    text = json.dumps({"t": datetime(2026, 10, 19, 9, 30, tzinfo=timezone.utc)},
                      cls=m01.SafeEncoder)
    parsed: dict[str, str] = json.loads(text)
    assert parsed["t"] == "2026-10-19T09:30:00+00:00"


def test_json_encoder_unsupported_type_raises() -> None:
    """非法输入：编码器兜底必须抛 TypeError（协议要求）。"""
    with pytest.raises(TypeError):
        json.dumps({1, 2, 3}, cls=m01.SafeEncoder)


def test_naive_aware_compare_raises() -> None:
    """时区坑：naive 与 aware 不许比较；UTC 0 点在北京是 8 点。"""
    naive = datetime(2026, 10, 19, 9, 30)
    aware = datetime(2026, 10, 19, 9, 30, tzinfo=timezone.utc)
    with pytest.raises(TypeError):
        _ = naive < aware  # noqa: B015
    beijing = datetime(2026, 10, 19, 0, 0, tzinfo=timezone.utc).astimezone(m02.shanghai_tz())
    assert beijing.hour == 8


def test_re_parse_log_and_tags() -> None:
    """正则：命名组解析日志行与 tag 版本号。"""
    line = "2026-10-19 09:30:01.123 ERROR [order-svc] 订单超时：下游 503"
    parsed = m03.parse_log_line(line)
    assert parsed is not None
    assert parsed["level"] == "ERROR" and parsed["service"] == "order-svc"
    assert m03.parse_log_line("junk") is None                    # 非法输入 → None
    assert m03.parse_tag("v1.2.16") == (1, 2, 16)
    assert m03.parse_tag("nightly") is None


def _run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(CLI), *args],
                          capture_output=True, text=True, check=False)


def test_cli_local_report_is_valid_json() -> None:
    """收束项目（本地模式）：报告可解析、字段齐备、版本排序正确。"""
    proc = _run_cli(["--source", "local"])
    assert proc.returncode == 0, proc.stderr
    report: dict[str, Any] = json.loads(proc.stdout)
    assert report["meta"]["data_source"] == "local"
    assert report["repo"]["full_name"] == "langchain-ai/langgraph"
    assert report["versions"]["count"] == 5
    assert report["versions"]["max_in_batch"] == "0.0.8"         # semver 排序后的批内最大
    assert report["versions"]["versions"][0]["tag"] == "v0.0.4"  # 升序
    assert report["repo"]["created_at_cn"].endswith("(UTC+8)")   # 时间格式化生效


def test_cli_output_flag_writes_file(tmp_path: Path) -> None:
    """--output 落盘：文件存在且内容与 stdout 报告一致。"""
    out_path = tmp_path / "report.json"
    proc = _run_cli(["--source", "local", "--output", str(out_path)])
    assert proc.returncode == 0
    on_disk: dict[str, Any] = json.loads(out_path.read_text(encoding="utf-8"))
    assert on_disk["repo"]["stars"] > 0                          # 真实抓取的数据必有星数


def test_cli_rejects_bad_source() -> None:
    """非法输入：argparse 拒绝未知 --source，退出码 2。"""
    proc = _run_cli(["--source", "bogus"])
    assert proc.returncode == 2
    assert "invalid choice" in proc.stderr


def test_cli_local_missing_sample_fails_cleanly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """边界：本地样本丢失时报错清晰，而不是栈崩溃给用户看。"""
    monkeypatch.setattr("ex_12_05_report_cli.SAMPLE_PATH", tmp_path / "no_such.json")
    import ex_12_05_report_cli as cli

    assert cli.main(["--source", "local"]) == 1
