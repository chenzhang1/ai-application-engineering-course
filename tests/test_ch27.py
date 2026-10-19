# tests/test_ch27.py | ch27 对话历史管理
"""覆盖：窗口截断保留规则、摘要压缩保事实、token 预算表守恒、截断的 pair 完整性讨论。"""
from __future__ import annotations

from examples.ch27_history.ex_27_01_window_truncate import (
    HISTORY,
    KEEP_RECENT,
    KEEP_SYSTEM,
    total_tokens,
    truncate,
)
from examples.ch27_history.ex_27_02_summary_compress import compress
from examples.ch27_history.ex_27_03_token_budget import MAX_CONTEXT, RATIOS


def test_truncate_keeps_system_and_recent() -> None:
    truncated = truncate(HISTORY, KEEP_RECENT)
    assert truncated[0]["role"] == "system"                       # system 永远在
    assert truncated[1:] == HISTORY[-KEEP_RECENT:]                # 之后是最近 N 条
    assert len(truncated) == 1 + KEEP_RECENT


def test_truncate_saves_tokens_and_losses_exist() -> None:
    before, after = total_tokens(HISTORY), total_tokens(truncate(HISTORY, KEEP_RECENT))
    assert after < before
    dropped = HISTORY[KEEP_SYSTEM:-KEEP_RECENT]
    assert any("换货" in m["content"] for m in dropped)  # 被丢内容里有关键事实（教学的教训）


def test_summary_keeps_key_facts() -> None:
    compressed = compress(HISTORY, "【对话摘要】换货已提交，明天上门取件。", keep_recent=2)
    texts = " ".join(m["content"] for m in compressed)
    assert "换货已提交" in texts and "明天上门取件" in texts       # 摘要保住关键事实
    assert compressed[0]["role"] == "system"
    assert total_tokens(compressed) < total_tokens(HISTORY)


def test_budget_table_sums_to_window() -> None:
    assert sum(RATIOS.values()) == 1.0
    allocated = int(MAX_CONTEXT * 0.10) + int(MAX_CONTEXT * 0.45) \
        + int(MAX_CONTEXT * 0.30) + int(MAX_CONTEXT * 0.15)
    assert allocated <= MAX_CONTEXT  # 分配不超过窗口（取整损耗允许）
