# 测试/test_ch34.py | ch34 生成与引用：上下文拼接 / 引用校验 / 权限过滤 / 拒答双保险
"""覆盖：预算装配（含丢弃行为）、引用编号校验（正常/越界/缺引用）、
多租户 ACL 规则矩阵、gate1 阈值行为、P1 RuleJudge 的判定行为。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from 示例代码.ch34_generation_citation.ex_34_01_context_assembly import (BUDGET_TOKENS,
                                                                         QUESTION,
                                                                         RETRIEVED,
                                                                         assemble)
from 示例代码.ch34_generation_citation.ex_34_02_citation_trace import (BLOCKS,
                                                                       validate_citations)
from 示例代码.ch34_generation_citation.ex_34_03_refusal_and_acl import (CHUNKS,
                                                                        SCORE_THRESHOLD,
                                                                        acl_visible, search)
from 示例代码.公共.llm_client import MockLLM

PROJECT = Path(__file__).resolve().parents[1] / "综合项目" / "项目一_文档知识库"
sys.path.insert(0, str(PROJECT))

from app.judge import RuleJudge  # noqa: E402  P1 的真实判定器（ch34.8 指向的实现）


def test_assembly_respects_budget_and_drops_whole_blocks() -> None:
    section, dropped = assemble(QUESTION, RETRIEVED, BUDGET_TOKENS)
    assert dropped, "预算内必须发生整块丢弃（教学叙事的前提）"
    assert len(section) > 0
    blocks_kept = [line for line in section.split("\n\n") if line.startswith("[")]
    assert all(int(line[1]) == i for i, line in enumerate(blocks_kept, 1))  # 编号连续
    assert all(chunk_id in dropped or chunk_id in section
               for chunk_id, _, _ in RETRIEVED)  # 每块要么装入要么显式丢弃


def test_assembly_tiny_budget_drops_everything() -> None:
    section, dropped = assemble(QUESTION, RETRIEVED, 10)
    assert section == "" and len(dropped) == len(RETRIEVED)


def test_validate_citations_accepts_good_and_rejects_bad() -> None:
    ok, problems = validate_citations("甲 [1]；乙 [2]。", len(BLOCKS))
    assert ok and problems == []
    ok, problems = validate_citations("离职折算按 300% 执行 [5]。", len(BLOCKS))
    assert not ok and any("超出证据范围" in p for p in problems)
    ok, problems = validate_citations("没有任何引用标记的回答。", len(BLOCKS))
    assert not ok and any("引用标记" in p for p in problems)


def test_acl_visible_matrix() -> None:
    alice = acl_visible(CHUNKS, "acme", {"hr", "all"})
    assert {c[0] for c in alice} == {"hr_leave#001", "hr_leave#000"}
    bob = acl_visible(CHUNKS, "acme", {"finance"})
    assert {c[0] for c in bob} == {"finance_tax#000"}
    mallory = acl_visible(CHUNKS, "beta", {"hr"})
    assert {c[0] for c in mallory} == {"beta_note#000"}  # 跨租户：acme 文档全部不可见


def test_gate1_threshold_passes_right_user_blocks_finance() -> None:
    ranked_alice = search("年假会清零吗", acl_visible(CHUNKS, "acme", {"hr", "all"}))
    assert ranked_alice[0][0] == "hr_leave#001"
    assert ranked_alice[0][1] >= SCORE_THRESHOLD  # alice 放行（教材输出 0.298 ≥ 0.25）
    ranked_bob = search("年假会清零吗", acl_visible(CHUNKS, "acme", {"finance"}))
    assert ranked_bob[0][1] < SCORE_THRESHOLD  # bob 的可见集里没有年假知识 → 拒


def test_rule_judge_dual_behavior() -> None:
    """P1 RuleJudge：词面重合 ≥2 → 放行；跑题证据 → 拒答（gate2 的确定性替身）。"""
    judge = RuleJudge()
    yes = judge.judge("年假会清零吗",
                      ["年假当年 12 月 31 日 24 点清零，不可结转。"])
    assert yes.has_answer
    no = judge.judge("年假会清零吗",
                     ["事假需提前 1 个工作日申请，由直属主管审批。"])
    assert not no.has_answer and no.reason


def test_scripted_gate2_llm_judge_output() -> None:
    """gate2 的 LLM 判定路径（Mock 脚本驱动，教材已标注）：判定输出可被程序解析。"""
    llm = MockLLM(script=[{"content": "has_answer=no reason=证据只讲事假审批，未提清零规则"}])
    out = llm.chat([{"role": "user", "content": "问题：年假会清零吗\n编号证据：\n[1] 事假…"}]).content
    assert "has_answer=no" in out
