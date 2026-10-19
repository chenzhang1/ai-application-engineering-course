# tests/test_ch21.py | ch21 Token 与上下文窗口
"""覆盖：tiktoken 精确计数与近似回退、中文 vs 英文 token 密度、预算算术、Mock 确定性。"""
from __future__ import annotations

import math

import pytest

from examples.common.llm_client import MockLLM, count_tokens


def test_tiktoken_exact_vs_approx_divergence() -> None:
    """中文短句：len//4 严重低估，tiktoken 精确值远大于近似值（EX-21-01 的结论）。"""
    n_exact, method = count_tokens("您好，请问有什么可以帮您？")
    assert method == "tiktoken:cl100k_base"
    n_approx = max(1, len("您好，请问有什么可以帮您？") // 4)
    assert n_exact > n_approx  # 13 vs 3（真实运行数字）


def test_token_count_roundtrip_and_monotonic() -> None:
    """encode/decode 往返无损；文本变长 token 数不减。"""
    from examples.common.llm_client import _get_encoding

    enc = _get_encoding()
    text = "订单查询"
    ids = enc.encode(text)
    assert enc.decode(ids) == text
    longer = "订单查询与售后政策说明（2026 年版）"
    assert count_tokens(longer)[0] > count_tokens(text)[0]


def test_context_budget_arithmetic() -> None:
    """prompt 合计 + 回答预留 ≤ 窗口上限（EX-21-02 的预算不等式）。"""
    from examples.ch21_tokens.ex_21_02_context_budget import MAX_CONTEXT_TOKENS, MESSAGES, MAX_OUTPUT_TOKENS

    total = sum(count_tokens(m["content"])[0] for m in MESSAGES)
    assert total == 164  # 真实运行值，锁定教学数字
    assert total + MAX_OUTPUT_TOKENS <= MAX_CONTEXT_TOKENS


def test_billing_snowball_grows() -> None:
    """历史累积 prompt 单调递增（滚雪球计费直觉）。"""
    from examples.ch21_tokens.ex_21_02_context_budget import MESSAGES

    cum = 0
    cumulative: list[int] = []
    for m in MESSAGES:
        cum += count_tokens(m["content"])[0]
        cumulative.append(cum)
    assert cumulative == sorted(cumulative) and cumulative[-1] == 164


def test_mock_determinism_and_temperature_ignored() -> None:
    """同输入同输出；temperature/top_p/max_tokens 被 Mock 接受并忽略（EX-21-03）。"""
    msgs = [{"role": "system", "content": "你是一个客服助手"},
            {"role": "user", "content": "退货政策是什么？"}]
    llm = MockLLM()
    outs = {llm.chat(msgs).content for _ in range(3)}
    assert len(outs) == 1
    hot = llm.chat(msgs, temperature=1.5, top_p=0.5, max_tokens=5).content
    assert hot == next(iter(outs))


@pytest.mark.parametrize("text,at_least", [("a", 1), ("中文", 1), ("hello world", 1)])
def test_count_tokens_nonempty_positive(text: str, at_least: int) -> None:
    """边界：非空文本返回正整数；方式标注透明。"""
    n, method = count_tokens(text)
    assert n >= at_least
    assert method in {"tiktoken:cl100k_base", "approx:chars//4"}
    assert math.isfinite(n)


def test_count_tokens_empty_string_exact_zero() -> None:
    """诚实边界：tiktoken 精确路径下空串就是 0 个 token（近似路径才用 max(1,·) 兜底）。"""
    n, method = count_tokens("")
    assert n == 0 and method == "tiktoken:cl100k_base"
