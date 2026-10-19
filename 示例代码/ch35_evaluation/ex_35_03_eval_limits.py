# EX-35-03 | 自动评估的局限：两个"自动判分与人工判分相反"的案例 | 运行: python3 示例代码/ch35_evaluation/ex_35_03_eval_limits.py
"""完整可运行（确定性程序，真实运行输出）：自动指标是守门员不是裁判——
本例构造两个真实形态的分歧：
案例 A：关键词全中、指标全绿，但答案答非所问（张冠李戴）——自动通过、人工不通过；
案例 B：答案正确但换了个说法——自动不通过、人工通过。
由此给出自动评估与人工复核的分工协议。
"""
from __future__ import annotations

import re

# 证据（来自检索）与评估关键词（evalset 里写死的）
BLOCK_SICK = "病假超过 3 天返岗后 2 个工作日内补交医院证明，否则按事假处理。"
BLOCK_ANNUAL = "年假当年 12 月 31 日 24 点清零，不可结转。"
KEYWORDS = ["病假", "证明"]  # q02 的 expect_keywords


def keyword_metric(answer: str, keywords: list[str]) -> bool:
    return all(k in answer for k in keywords)


def number_anchor_metric(answer: str, evidence: str) -> bool:
    nums = re.findall(r"\d+", answer)
    return all(n in evidence for n in nums)  # 教学简化：不剔引用编号


def main() -> None:
    print("[案例 A：自动全绿，人工判错]")
    answer_a = "病假需要证明，年假也会清零 [1]。"  # 把病假证明的依据张冠李戴到年假块
    auto_a = keyword_metric(answer_a, KEYWORDS) and number_anchor_metric(answer_a, BLOCK_SICK)
    print(f"    答案：{answer_a}")
    print(f"    依据块 [1]：{BLOCK_ANNUAL}")
    print(f"    自动指标：关键词 {keyword_metric(answer_a, KEYWORDS)}，"
          f"数字锚点 {number_anchor_metric(answer_a, BLOCK_SICK)} → {'通过' if auto_a else '拦截'}")
    print("    人工判读：✗ ——'病假要证明'的出处不是年假块！答案把两个主题缝在一起，")
    print("    引用 [1] 指向了错误证据。词面指标对'语义归属'失明。")
    print("    根治手段：引用-句子对齐校验（被引块必须包含答案对应句的内容）+ 人工抽检。")

    print("\n[案例 B：自动拦截，人工判对]")
    answer_b = "超过 3 天的病假，记得回公司两个工作日内把医生开的单子交上去。"  # 正确但无引用
    auto_b = keyword_metric(answer_b, KEYWORDS) and number_anchor_metric(answer_b, BLOCK_SICK)
    print(f"    答案：{answer_b}")
    print(f"    自动指标：关键词 {keyword_metric(answer_b, KEYWORDS)}"
          f"（'证明'被改写成'单子'），数字锚点 {number_anchor_metric(answer_b, BLOCK_SICK)} → "
          f"{'通过' if auto_b else '拦截'}")
    print("    人工判读：✓ ——内容与证据一致，只是口语化转述。")
    print("    处置不是判错，而是要求补引用：转述可以，溯源必须。")

    print("\n[自动评估与人工复核的分工协议]")
    print("    1) 自动指标（hit@k/关键词/引用有效/数字锚点）：全量跑，做'回归守门'——")
    print("       指标回退=拦截合并，但它只抓回归，不保证绝对正确；")
    print("    2) 人工抽检：按比例抽样（如每周 30 条）+ 全量抽检拒答与低分段，做'绝对质量'终审；")
    print("    3) 分歧样本（自动过/人工不过）最高价值——回填评估集并补指标（如本例的对齐校验），")
    print("       让自动网越织越密；")
    print("    4) LLM-as-judge 可做'规模化初筛'，但判官自己会错且成本高：")
    print("       只当概率级信号，决策仍靠程序指标+人（与 ch29 '模型是提议者'同一原则）。")
    print("[诚实声明] 本例两个答案与判读是教学构造（非模型输出）；")
    print("    但两类分歧形态在真实评估中反复出现，比例需以自家评估为准（待核实项见章末）。")


if __name__ == "__main__":
    main()
