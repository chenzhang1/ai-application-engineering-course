# tests/test_ch37.py | ch37 LangChain 定位与边界
"""覆盖：决策表全部路径（正常）、特征组合完备性（边界）、裸 SDK/LangChain 对照输出形状、
Mock 模式不联网（非法环境兜底）。"""
from __future__ import annotations

import itertools

from examples.ch37_lc_boundary.ex_37_01_decision_table import ADVICE_CN, advise
from examples.ch37_lc_boundary.ex_37_02_side_by_side import (
    QUESTION,
    bare_sdk_version,
    langchain_version,
)


def test_decision_table_five_cases() -> None:
    """五个判断案例各自命中预期建议（教材 37.1/37.4 的表）。"""
    assert advise(single_turn=True, steps=1, needs_tools=False, needs_model_switch=False,
                  needs_retrieval=False, needs_hitl_or_resume=False) == "bare_sdk"
    assert advise(single_turn=True, steps=2, needs_tools=False, needs_model_switch=False,
                  needs_retrieval=True, needs_hitl_or_resume=False) == "components_only"
    assert advise(single_turn=True, steps=1, needs_tools=True, needs_model_switch=False,
                  needs_retrieval=False, needs_hitl_or_resume=False) == "full_langchain"
    assert advise(single_turn=False, steps=3, needs_tools=True, needs_model_switch=True,
                  needs_retrieval=False, needs_hitl_or_resume=True) == "langgraph"
    assert advise(single_turn=True, steps=2, needs_tools=False, needs_model_switch=True,
                  needs_retrieval=False, needs_hitl_or_resume=False) == "components_only"


def test_decision_table_exhaustive_and_valid() -> None:
    """边界：64 种布尔组合 × steps∈{0,1,3} 全部有结论且在四个建议之内（决策表无死角）。"""
    valid = set(ADVICE_CN)
    for combo in itertools.product([True, False], repeat=5):
        for steps in (0, 1, 3):
            advice = advise(single_turn=combo[0], steps=steps, needs_tools=combo[1],
                            needs_model_switch=combo[2], needs_retrieval=combo[3],
                            needs_hitl_or_resume=combo[4])
            assert advice in valid


def test_side_by_side_shapes() -> None:
    """同一任务两条实现线的输出契约：裸 SDK 有 usage，LangChain 链是 RunnableSequence。"""
    answer, usage = bare_sdk_version()
    assert QUESTION in answer and answer
    assert usage["prompt_tokens"] >= 1 and usage["completion_tokens"] >= 1
    lc_answer, chain_type = langchain_version()
    assert lc_answer == "（Fake）您好，7 天内可无理由退货，运费由商家承担。"
    assert chain_type == "RunnableSequence"


def test_mock_mode_is_offline(monkeypatch) -> None:
    """非法/默认环境下 get_llm 必须是 MockLLM（本部分示例绝不联网的兜底）。"""
    from examples.common.llm_client import MockLLM, get_llm

    monkeypatch.setenv("LLM_MODE", "mock")
    assert isinstance(get_llm(), MockLLM)
    monkeypatch.setenv("LLM_MODE", "bogus")
    import pytest

    with pytest.raises(ValueError, match="mock 或 real"):
        get_llm()
