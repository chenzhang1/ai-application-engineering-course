# EX-35-02 | 忠实性与引用正确性的可计算定义 | 运行: python3 示例代码/ch35_evaluation/ex_35_02_faithfulness_citation.py
"""完整可运行（确定性程序，真实运行输出）：检索对了不等于答案对——答案还可能
"自由发挥"。本例给两个可自动计算的答案级指标：
1) 引用有效性：回答里的 [n] 都指向真实证据块（EX-34-02 的程序校验，这里作为指标）；
2) 忠实性代理：答案中的关键数字必须出现在被引块里——数字是最容易核对的
   "事实锚点"，编造的数字会被当场抓住（LLM-as-judge 的词面级替代/前置）。
诚实边界：这两个指标都是"抓错"而非"证对"——通过不代表答案全对（EX-35-03）。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

CITATION_RE = re.compile(r"\[(\d+)\]")
NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")

BLOCKS = {
    1: "年假按工龄计算，满 1 年不满 10 年每年 5 天。年假当年 12 月 31 日 24 点清零，不可结转。",
    2: "病假超过 3 天返岗后 2 个工作日内补交医院证明，否则按事假处理。",
    3: "报销款审核通过后 3 个工作日内到达工资卡。",
}


def citation_validity(answer: str, n_blocks: int) -> tuple[bool, list[str]]:
    marks = [int(m) for m in CITATION_RE.findall(answer)]
    problems = [f"引用 [{m}] 不在证据范围 1..{n_blocks}" for m in marks if not 1 <= m <= n_blocks]
    if not marks:
        problems.append("无任何引用标记")
    return not problems, problems


def faithfulness_numbers(answer: str, blocks: dict[int, str]) -> tuple[bool, list[str]]:
    """忠实性代理：答案里的每个数字必须出现在它引用的块中（未标引用则查全部块）。"""
    marks = [int(m) for m in CITATION_RE.findall(answer)] or list(blocks)
    cited_text = " ".join(blocks.get(m, "") for m in marks)
    problems = [f"数字 {num} 未出现在被引证据中" for num in NUMBER_RE.findall(answer)
                if num not in cited_text and num not in {str(m) for m in marks}]
    return not problems, problems


def evaluate(name: str, answer: str) -> None:
    ok_c, p_c = citation_validity(answer, len(BLOCKS))
    ok_f, p_f = faithfulness_numbers(answer, BLOCKS)
    print(f"[{name}]")
    print(f"    答案：{answer}")
    print(f"    引用有效性：{'✓' if ok_c else '✗ ' + '；'.join(p_c)}")
    print(f"    忠实性(数字锚点)：{'✓' if ok_f else '✗ ' + '；'.join(p_f)}")
    print(f"    结论：{'自动通过（仍需人工抽检，见 EX-35-03）' if ok_c and ok_f else '自动拦截 ✓'}\n")


def main() -> None:
    print("[证据块]")
    for i, text in BLOCKS.items():
        print(f"    [{i}] {text}")

    evaluate("答案 A（引用完整、数字有据）",
             "年假当年 12 月 31 日 24 点清零 [1]；病假超过 3 天要补医院证明 [2]。")
    evaluate("答案 B（幻觉引用）",
             "年假 12 月 31 日清零 [1]，离职折算按 300% [5]。")
    evaluate("答案 C（数字编造：把 3 个工作日说成 15 个）",
             "报销款 15 个工作日内到账 [3]。")
    evaluate("答案 D（无引用）",
             "年假年底清零，病假要医院证明。")

    print("[指标的分工]")
    print("    引用有效性=可溯源（说的每句都能查到出处）；忠实性=没添油加醋（出处里真的有）。")
    print("    数字锚点是忠实性最便宜的实现：规则、期限、金额、比例几乎都带数字。")
    print("    语义级忠实性（'大致如此'但数字没错的改写）需要 LLM-as-judge——")
    print("    成本高且有自身偏差，生产上通常'词面指标做守门 + LLM 判官做抽检 + 人工复核终审'。")
    print("[与 ch26 的呼应] 让答案带 [n] 是 Prompt 约定，本例把它变成可断言的接口契约——")
    print("    约束只有变成指标才会被遵守。")


if __name__ == "__main__":
    main()
