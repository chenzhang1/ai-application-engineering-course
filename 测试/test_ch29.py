# 测试/test_ch29.py | ch29 与 AI 协作开发
"""覆盖：5 信号清单结构、信号 1 的签名核查器（真实执行）、AI 生成代码的 pytest 护栏
（buggy 版红 / 修复版绿）、解释代码模板三要素。"""
from __future__ import annotations

import pytest

from 示例代码.ch29_ai_collab.ex_29_02_error_signals import SIGNALS, check_signal1
from 示例代码.ch29_ai_collab.ex_29_03_guard_generated import dedupe, dedupe_ai_buggy


def test_five_signals_catalog() -> None:
    """5 个信号齐备，每个都带样例与核查动作。"""
    assert len(SIGNALS) == 5
    for title, sample, action in SIGNALS:
        assert title.startswith("信号") and sample and action


def test_signal1_signature_check_catches_hallucinated_params() -> None:
    """真实执行：create 签名拒绝 api_version 与 max_retries（后者属客户端参数）。"""
    assert check_signal1("") == ["api_version", "max_retries"]


def test_guardrails_fail_on_ai_buggy_code() -> None:
    """AI 第一版：dict 列表直接 TypeError；字符串场景蒙对——护栏必须覆盖边界。"""
    with pytest.raises(TypeError):
        dedupe_ai_buggy([{"a": 1}, {"a": 1}])
    assert dedupe_ai_buggy(["b", "a", "b", "a"]) == ["b", "a"]


def test_dedupe_fixed_version_is_green() -> None:
    assert dedupe([{"a": 1}, {"a": 1}]) == [{"a": 1}]
    assert dedupe(["b", "a", "b", "a"]) == ["b", "a"]
    assert dedupe([{"x": 2}, {"x": 1}, {"x": 2}]) == [{"x": 2}, {"x": 1}]
    assert dedupe([]) == []


def test_explain_template_design() -> None:
    """好提问模板含 上下文/任务/输出格式 三要素（EX-29-01 的结构断言）。"""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from 示例代码.ch29_ai_collab.ex_29_01_explain_code import GOOD_TEMPLATE, NAIVE_QUESTION

    assert GOOD_TEMPLATE.index("## 上下文") < GOOD_TEMPLATE.index("## 任务") < \
        GOOD_TEMPLATE.index("## 输出格式") < GOOD_TEMPLATE.index("## 代码")
    assert "干嘛的" in NAIVE_QUESTION
