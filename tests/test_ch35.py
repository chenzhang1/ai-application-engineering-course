# tests/test_ch35.py | ch35 评估：hit@k/MRR 计算、忠实性/引用有效性、自动评估局限
"""覆盖：指标计算的正确值（MockEmbedder 确定性）、边界（未命中/无引用/数字编造）、
自动判分与人工判分的分歧形态。"""
from __future__ import annotations

import pytest

from examples.ch35_evaluation.ex_35_01_evalset_hitrate import (EVALSET, KB_DOCS,
                                                               hit_and_mrr)
from examples.ch35_evaluation.ex_35_02_faithfulness_citation import (BLOCKS,
                                                                     citation_validity,
                                                                     faithfulness_numbers)
from examples.ch35_evaluation.ex_35_03_eval_limits import (BLOCK_SICK, KEYWORDS,
                                                           keyword_metric,
                                                           number_anchor_metric)
from examples.common.embeddings import get_embedder


def test_hit_and_mrr_deterministic_values() -> None:
    hit2, hit3, mrr, rows = hit_and_mrr(get_embedder(), top_k=3)
    assert len(rows) == len(EVALSET)
    assert hit2 == 1.0 and hit3 == 1.0  # 教材输出的 100%
    assert abs(mrr - 5 / 6) < 1e-9      # 4 个 1.0 + 2 个 0.5 → 5/6 ≈ 0.833
    rr_values = [r["rr"] for r in rows]
    assert sorted(rr_values) == [0.5, 0.5, 1.0, 1.0, 1.0, 1.0]


def test_evalset_targets_are_valid_docs() -> None:
    for _qid, _query, expect in EVALSET:
        assert expect in KB_DOCS, f"评估集引用了不存在的文档：{expect}"


def test_citation_and_faithfulness_metrics() -> None:
    # 答案 A：引用与数字都有据
    ok_c, _ = citation_validity("年假当年 12 月 31 日 24 点清零 [1]；病假超过 3 天要补医院证明 [2]。",
                                len(BLOCKS))
    ok_f, _ = faithfulness_numbers("年假当年 12 月 31 日 24 点清零 [1]；病假超过 3 天要补医院证明 [2]。",
                                   BLOCKS)
    assert ok_c and ok_f
    # 答案 B：幻觉引用 [5] + 编造数字 300
    ok_c, problems_c = citation_validity("年假 12 月 31 日清零 [1]，离职折算按 300% [5]。",
                                         len(BLOCKS))
    assert not ok_c and any("[5]" in p for p in problems_c)
    ok_f, problems_f = faithfulness_numbers("年假 12 月 31 日清零 [1]，离职折算按 300% [5]。",
                                            BLOCKS)
    assert not ok_f and any("300" in p for p in problems_f)
    # 答案 C：引用有效但数字编造（3 → 15）
    ok_f, problems_f = faithfulness_numbers("报销款 15 个工作日内到账 [3]。", BLOCKS)
    assert not ok_f and any("15" in p for p in problems_f)
    # 答案 D：无引用 → 引用有效性拦截
    ok_c, problems_c = citation_validity("年假年底清零，病假要医院证明。", len(BLOCKS))
    assert not ok_c


def test_eval_limits_spurious_pass_and_fail() -> None:
    # 案例 A：关键词全中但张冠李戴——词面指标通过、锚点拦截；人工判错
    answer_a = "病假需要证明，年假也会清零 [1]。"
    assert keyword_metric(answer_a, KEYWORDS) is True          # 自动"通过"的一半
    assert number_anchor_metric(answer_a, BLOCK_SICK) is False  # 数字锚点抓住了错位
    # 案例 B：正确转述但换词——关键词指标误报失败
    answer_b = "超过 3 天的病假，记得回公司两个工作日内把医生开的单子交上去。"
    assert keyword_metric(answer_b, KEYWORDS) is False  # '证明'被改写成'单子'
    assert number_anchor_metric(answer_b, BLOCK_SICK) is True  # 数字与证据一致
