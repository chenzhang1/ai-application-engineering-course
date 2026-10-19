# EX-34-03 | 拒答双保险与检索前权限过滤 | 运行: python3 examples/ch34_generation_citation/ex_34_03_refusal_and_acl.py
"""完整可运行（gate1 真实计算；gate2 判定由脚本 Mock 驱动，已标注）：
拒答的两个闸门 + 多租户权限过滤：
gate1 分数阈值：检索器自己"不自信"（top1 分数低于阈值）→ 拒；
gate2 证据判定：分数过了但证据答不了问题 → 拒（LLM 判定，Mock 用脚本模拟）；
ACL：无权文档在打分前就被移出候选——不参与排序、不进上下文、不出现在引用里。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402

from examples.common.embeddings import get_embedder  # noqa: E402
from examples.common.llm_client import MockLLM  # noqa: E402

SCORE_THRESHOLD = 0.25  # 教学演示值；生产阈值必须用自家语料评估集校准（ch35）

# (doc_id, tenant, department, text)
CHUNKS = [
    ("hr_leave#001", "acme", "hr", "年假当年 12 月 31 日 24 点清零，不可结转。"),
    ("hr_leave#000", "acme", "hr", "事假需提前 1 个工作日申请，由直属主管审批。"),
    ("finance_tax#000", "acme", "finance", "个税专项附加扣除需在每年 12 月确认。"),
    ("beta_note#000", "beta", "hr", "Beta 公司入职当天由前台录入人脸门禁。"),
]


def acl_visible(chunks: list[tuple[str, str, str, str]],
                tenant: str, departments: set[str]) -> list[tuple[str, str, str, str]]:
    """检索前权限过滤：租户必须一致；部门为 all（公开）或命中用户部门。"""
    return [c for c in chunks
            if c[1] == tenant and (c[2] == "all" or c[2] in departments)]


def search(question: str, visible: list[tuple[str, str, str, str]]
           ) -> list[tuple[str, float]]:
    """余弦相似度检索：只看得到'可见候选'（权限过滤已先行）。"""
    emb = get_embedder()
    q = np.asarray(emb.embed_one(question))
    q = q / np.linalg.norm(q)
    scored = []
    for cid, _, _, text in visible:
        d = np.asarray(emb.embed_one(text))
        d = d / np.linalg.norm(d)
        scored.append((cid, float(d @ q)))
    return sorted(scored, key=lambda kv: -kv[1])


def main() -> None:
    # ---- 1) 权限过滤：同一问题，三种用户看到的候选集不同 ----
    question = "年假会清零吗"
    users = [
        ("alice（acme｜hr+all）", "acme", {"hr", "all"}),
        ("bob  （acme｜finance）", "acme", {"finance"}),
        ("mallory（beta｜hr）", "beta", {"hr"}),
    ]
    print("[1] 检索前权限过滤（过滤发生在打分之前——无权文档根本不进候选矩阵）")
    for name, tenant, depts in users:
        visible = acl_visible(CHUNKS, tenant, depts)
        print(f"    {name:<24} 可见 {len(visible)}/{len(CHUNKS)} 块："
              f"{[c[0] for c in visible]}")
    print("    → bob 看不见任何年假块（他是财务）；mallory 是另一家租户——")
    print("      对他而言 acme 的文档'不存在'，而不是'存在但被拒绝'（不泄露存在性）。")

    # ---- 2) gate1：分数阈值 ----
    print(f"\n[2] gate1：top1 分数阈值（本演示 {SCORE_THRESHOLD}）")
    for name, tenant, depts in users[:2]:
        visible = acl_visible(CHUNKS, tenant, depts)
        ranked = search(question, visible)
        top1 = ranked[0] if ranked else ("-", 0.0)
        verdict = "放行 → 进入 gate2" if top1[1] >= SCORE_THRESHOLD else "拒答（below_score_threshold）"
        print(f"    {name:<24} top1={top1[0]}({top1[1]:.3f}) → {verdict}")

    # ---- 3) gate2：证据充分性判定（LLM 判定；Mock 脚本模拟两次判定输出）----
    print("\n[3] gate2：证据判定——分数过了 ≠ 证据能回答（判定输出由脚本模拟）")
    llm = MockLLM(script=[
        {"content": "has_answer=yes reason=证据含年假清零条款"},          # 年假块 vs 年假问题
        {"content": "has_answer=no reason=证据只讲事假审批，未提清零规则"},  # 事假块 vs 年假问题
    ])
    cases = [
        ("年假会清零吗", ["年假当年 12 月 31 日 24 点清零，不可结转。"]),
        ("年假会清零吗", ["事假需提前 1 个工作日申请，由直属主管审批。"]),
    ]
    for q, evidence in cases:
        judge_msg = (f"问题：{q}\n编号证据：\n[1] {evidence[0]}\n"
                     "只依据证据判断能否回答（has_answer=yes/no reason=...）")
        out = llm.chat([{"role": "user", "content": judge_msg}]).content
        print(f"    证据：{evidence[0][:24]}…  → 判定：{out}")
    print("    → 第二种情况常见于：查询词撞上了相关文档（分数虚高），但文档讲的不是这件事。")
    print("      阈值拦不住'自信的跑题'，判定器拦得住——这就是双保险的意义。")
    print("      P1 项目的真实实现：mock 模式用词面重叠规则判定，real 模式用 chat_structured 结构化判定。")

    print("\n[拒答的口径] 拒答要返回结构化原因（below_score_threshold / evidence_insufficient_judge")
    print("    / no_relevant_evidence），而不是一句'我不知道'——前端可分级引导，")
    print("    运营可按原因统计坏例，评估可分别算误拒率与漏拒率（ch35）。")


if __name__ == "__main__":
    main()
