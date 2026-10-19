# EX-62-01 | RAG vs Prompt vs 微调：确定性选择树 | 运行: python3 examples/ch62_finetuning_boundary/ex_62_01_route_selector.py
"""完整可运行（纯标准库，离线）：输入业务诉求特征，输出建议技术路线与理由。

规则全部是本章 62.4 决策树的确定性翻译（同输入必同输出，可进测试）。
诚实边界：输出是"路线建议与理由"，不是可行性结论——预算/数据/合规三个门
必须人工再过一遍（62.5 的成本量级判断），最终拍板前没有评估集不动工（ch63）。
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class NeedFeatures:
    """业务诉求特征（用 EX-62-01 教材中的问卷收集）。"""

    knowledge_private: bool          # 依赖私有知识（内部文档/制度/工单）？
    knowledge_update_freq: str       # 知识更新频率："static" | "weekly" | "daily"
    needs_citations: bool            # 答案需要引用溯源？
    style_format_strict: bool        # 输出风格/格式强约束且 Prompt 已难以满足？
    labeled_pairs: int               # 可用于微调的高质量样本对数量（输入-期望输出）
    budget_small: bool               # 预算紧张（无 GPU/无训练平台/无标注预算）？

    def __post_init__(self) -> None:
        if self.labeled_pairs < 0:
            raise ValueError(f"labeled_pairs 不能为负数，收到 {self.labeled_pairs}")
        if self.knowledge_update_freq not in ("static", "weekly", "daily"):
            raise ValueError(
                f"knowledge_update_freq 只能是 static/weekly/daily，收到 {self.knowledge_update_freq!r}")


@dataclass
class Decision:
    route: str                       # prompt | rag | sft_lora | hybrid_rag_lora
    tree_path: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)


def decide(f: NeedFeatures) -> Decision:
    """把 62.4 的决策树翻译成代码：顺序判定，返回路线+理由。"""
    d = Decision(route="prompt")

    # 节点 1：知识侧有硬要求吗（私有/更新/引用）→ RAG 优先
    knowledge_hard = (f.knowledge_private and f.knowledge_update_freq in ("weekly", "daily")) \
        or f.knowledge_update_freq == "daily" or f.needs_citations
    if knowledge_hard:
        d.tree_path.append("知识侧硬要求（更新/引用/私有+更新）→ RAG")
        d.reasons.append("知识在模型外部管理：更新不改模型、答案可引用、可按权限过滤（ch58）")
        d.route = "rag"
    elif f.knowledge_private and f.knowledge_update_freq == "static":
        d.tree_path.append("私有但更新慢 → 先 Prompt 带上知识，量大再上 RAG")
        d.reasons.append("知识量小且稳定时，直接放进 Prompt 最便宜；chunk 数超过几十就转 RAG")
        d.route = "rag" if not f.budget_small else "prompt"

    # 节点 2：风格/格式强约束吗 → SFT 候选（LoRA），但样本量必须够
    if f.style_format_strict and f.labeled_pairs >= 1000:
        d.tree_path.append("风格/格式强约束 + 样本 ≥1000 → LoRA 微调候选")
        d.reasons.append("千级一致样本才能'教'出稳定格式；Prompt+few-shot 是第一基线（先做完再谈微调）")
        d.route = "hybrid_rag_lora" if d.route == "rag" else "sft_lora"
    elif f.style_format_strict:
        d.tree_path.append(f"风格约束但样本 {f.labeled_pairs} <1000 → 先 Prompt+few-shot，补样本")
        d.reasons.append("样本不足时微调大概率不如 few-shot；几十条精选样本 > 几百条噪声样本")
        d.reasons.append("把标注预算优先花在评估集与数据质量上（ch63：没有评估集就别谈微调）")
        if d.route == "rag":
            d.caveats.append("知识用 RAG 解决，风格问题继续用 Prompt——两件事别混成一个方案")
    else:
        d.tree_path.append("无风格硬约束 → 不需要微调")
        if d.route == "prompt":
            d.reasons.append("既无知识侧硬要求，也无格式硬要求：Prompt 工程 + 评估集就是全部")

    d.caveats.append("本结论是规则推导（确定性），未经过你的数据验证——先建评估集再动工（ch63）")
    if not f.budget_small:
        d.caveats.append("预算充足也不等于该微调：62.5 的成本构成（标注/算力/评估/运维）先估一遍")
    return d


def _print_case(title: str, f: NeedFeatures) -> None:
    d = decide(f)
    print(f"── {title} ──")
    print(f"    特征：私有知识={f.knowledge_private} 更新={f.knowledge_update_freq} "
          f"引用={f.needs_citations} 格式严格={f.style_format_strict} "
          f"样本={f.labeled_pairs} 预算紧={f.budget_small}")
    print(f"    路径：{' → '.join(d.tree_path)}")
    print(f"    路线：{d.route}")
    for r in d.reasons:
        print(f"    理由：{r}")
    for c in d.caveats:
        print(f"    边界：{c}")
    print()


def main() -> None:
    print("── 决策树走树演示（三个真实感案例，路径与理由全部输出）──\n")
    _print_case(
        "案例 1：客服回复语气统一（无知识缺口）",
        NeedFeatures(knowledge_private=False, knowledge_update_freq="static",
                     needs_citations=False, style_format_strict=True,
                     labeled_pairs=80, budget_small=True))
    _print_case(
        "案例 2：企业制度问答（私有知识+需引用+月度更新）",
        NeedFeatures(knowledge_private=True, knowledge_update_freq="weekly",
                     needs_citations=True, style_format_strict=False,
                     labeled_pairs=0, budget_small=True))
    _print_case(
        "案例 3：医疗报告结构化抽取（格式严格+5000 对标注）",
        NeedFeatures(knowledge_private=False, knowledge_update_freq="static",
                     needs_citations=False, style_format_strict=True,
                     labeled_pairs=5000, budget_small=False))

    print("── 非法输入校验（负样本量 / 非法更新频率）──")
    bad_inputs = [dict(knowledge_private=False, knowledge_update_freq="static",
                       needs_citations=False, style_format_strict=False,
                       labeled_pairs=-1, budget_small=True),
                  dict(knowledge_private=False, knowledge_update_freq="everyday",
                       needs_citations=False, style_format_strict=False,
                       labeled_pairs=0, budget_small=True)]
    for bad in bad_inputs:
        try:
            decide(NeedFeatures(**bad))
        except ValueError as exc:
            print(f"    ValueError: {exc}")


if __name__ == "__main__":
    main()
