# EX-34-02 | 引用溯源：[n] 标记的生成约定与程序校验 | 运行: python3 examples/ch34_generation_citation/ex_34_02_citation_trace.py
"""完整可运行（Mock，脚本驱动）：引用不是"让模型自觉"——是接口约定 + 程序校验：
1) Prompt 约定回答必须带 [n] 标记（EX-34-01 的约束段）；
2) 程序解析回答里的 [n]，逐个校验：编号存在（防幻觉引用）、编号指向的块真实参与过检索；
3) 校验失败 → 丢弃回答，回退到抽取式答案（宁可朴素不可编造）。
Mock 的两次模型输出由脚本模拟（真实模型行为见教材标注）。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from examples.common.llm_client import MockLLM  # noqa: E402

CITATION_RE = re.compile(r"\[(\d+)\]")

# 检索证据（编号与块，EX-34-01 的产物）
BLOCKS = [
    ("hr_leave_policy#001", "年假当年 12 月 31 日 24 点清零，不可结转。"),
    ("hr_leave_policy#000", "病假超过 3 天返岗后 2 个工作日内补交医院证明。"),
]


def validate_citations(answer: str, n_blocks: int) -> tuple[bool, list[str]]:
    """程序侧校验：所有 [n] 必须是 1..n_blocks 的有效编号，且至少引用 1 个。"""
    marks = [int(m) for m in CITATION_RE.findall(answer)]
    if not marks:
        return False, ["回答没有任何引用标记，无法溯源"]
    bad = [str(m) for m in marks if not 1 <= m <= n_blocks]
    if bad:
        return False, [f"引用编号 {bad} 超出证据范围（1..{n_blocks}）——幻觉引用"]
    return True, []


def main() -> None:
    llm = MockLLM(script=[
        # 合规输出：引用 [1] 与 [2]，内容与证据一致
        {"content": "年假当年 12 月 31 日 24 点清零，不可结转 [1]；病假超过 3 天需补交医院证明 [2]。"},
        # 违规输出 1：引用了不存在的 [5]（幻觉引用的典型形态）
        {"content": "年假 12 月 31 日清零 [1]，离职折算按 300% 执行 [5]。"},
    ])

    print("[证据块]")
    for i, (cid, text) in enumerate(BLOCKS, 1):
        print(f"    [{i}] {cid}：{text}")

    print("\n[回答 1] 引用校验：")
    a1 = llm.chat([{"role": "user", "content": "（约束：末尾用 [n] 标注依据的块编号）"}]).content
    print(f"    {a1}")
    ok, problems = validate_citations(a1, len(BLOCKS))
    print(f"    校验：{'✓ 通过' if ok else '✗ ' + '；'.join(problems)}")

    print("\n[回答 2] 引用校验：")
    a2 = llm.chat([{"role": "user", "content": "（第二次请求）"}]).content
    print(f"    {a2}")
    ok2, problems2 = validate_citations(a2, len(BLOCKS))
    print(f"    校验：{'✓ 通过' if ok2 else '✗ ' + '；'.join(problems2)}")
    if not ok2:
        fallback = "（Mock·抽取式回答）" + BLOCKS[0][1] + " [1]"
        print(f"    处置：丢弃该回答 → 回退抽取式：{fallback}")
        print("    理由：'离职折算 300%'可能是编的（证据里没有），且 [5] 指向不存在的块——")
        print("    溯源断了的内容不能出口，宁可给朴素的原句。")

    print("\n[引用的完整数据结构]（P1 项目 AskResponse.citations 的字段）")
    print("    [{index: 1, doc_id: 'hr_leave_policy', chunk_id: 'hr_leave_policy#001',")
    print("      score: 0.41, snippet: '年假当年 12 月 31 日…'}]")
    print("    index 对应回答里的 [n]；doc_id/chunk_id 可反查原文；score 留痕排序依据；")
    print("    snippet 让前端不用反查就能展示'依据'卡片。")

    print("\n[两层校验的分工]")
    print("    程序校验（本例）：编号有效性——确定性，必须做；")
    print("    内容校验（ch35 忠实性）：被引块是否真的支持答案——词面级可计算代理 + 人工抽检。")
    print("[Java 对照] 引用校验 ≈ 出参白名单/防篡改校验：模型输出在出口处过一道确定性闸门，")
    print("    和'不信任下游系统返回'是同一条工程原则。")


if __name__ == "__main__":
    main()
