# EX-63-01 | 数据质量对 SFT 的影响：垃圾进垃圾出（教学模拟） | 运行: python3 示例代码/ch63_boundary/ex_63_01_garbage_in_garbage_out.py
"""完整可运行（共享 MockLLM，离线）：对照实验模拟"数据质量 → 微调效果"的因果方向。

【诚实标注】本示例用 MockLLM 的 script 模式扮演两个"微调后的模型"：
  clean_model 的脚本 = 假设用 1000 条一致、干净的样本训练后的典型行为；
  dirty_model 的脚本 = 假设用同样 1000 条但混入格式漂移/错别字/矛盾标签样本后的典型行为。
脚本内容是教学预设，不是真实训练的产物——真实 SFT 的行为由训练过程决定，
本示例只演示"为什么要先管数据"，不能替代任何真实实验（真实差异以你的评估集实测为准）。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from 示例代码.公共.llm_client import MockLLM  # noqa: E402

# ── 训练数据（示意）：同样的 3 条知识，两种质量 ────────────────────────────
TRAIN_CLEAN = [
    ("退货政策是什么？", "退货政策：7 天内可退，需保留包装。"),
    ("退货政策是什么？", "退货政策：7 天内可退，需保留包装。"),   # 一致：同问同答
    ("发票怎么开？", "发票政策：支持电子发票，下单后 24 小时内开具。"),
]
TRAIN_DIRTY = [
    ("退货政策是什么？", "7天无理由退货哦～记得包装别扔！"),          # 格式漂移（口语化）
    ("退货政策是什么？", "退货政策是 15 天内退货。"),                # 标签矛盾（7 天 vs 15 天）
    ("发票怎么开？", "发标支持电字发票，24小时内开据。"),             # 错别字（发标/电字/开据）
]

# ── 测试问题：3 条训练内 + 1 条训练外（考验泛化与拒答）────────────────────
TEST_QS = ["退货政策是什么？", "退货政策是什么？", "发票怎么开？", "换货流程是什么？"]

# clean_model：学会了一致的格式；对训练外问题按学到的"政策口径"诚实说不知道
SCRIPT_CLEAN = [
    {"content": "退货政策：7 天内可退，需保留包装。"},
    {"content": "退货政策：7 天内可退，需保留包装。"},
    {"content": "发票政策：支持电子发票，下单后 24 小时内开具。"},
    {"content": "（知识库中没有换货政策，无法回答）"},                 # 干净数据教会了"没依据就拒答"
]
# dirty_model：输出风格混乱；训练外问题编了一个具体天数（垃圾数据连"自信"都是错的）
SCRIPT_DIRTY = [
    {"content": "7天无理由退货哦～记得包装别扔！"},
    {"content": "退货政策是 15 天内退货。"},
    {"content": "发标支持电字发票，24小时内开据。"},
    {"content": "换货流程是 15 天内联系客服，产品需未拆封。"},          # 训练里根本没有换货政策——编造
]


def judge(outputs: list[str], unseen_idx: int = 3) -> list[str]:
    """逐条判定：格式一致 / 无错别字 / 口径不矛盾 / 训练外问题不编造。返回判定说明列表。"""
    verdicts: list[str] = []
    for i, out in enumerate(outputs):
        if out.startswith("（知识库中没有"):
            verdicts.append("✓ 拒答正确（训练外问题明确说不知道）")
            continue
        problems: list[str] = []
        if not (out.startswith("退货政策：") or out.startswith("发票政策：")):
            problems.append("格式偏离统一模板")
        if re.search(r"发标|电字|开据", out):
            problems.append("含错别字（脏数据教会了错别字）")
        if "15 天" in out and i != unseen_idx:
            problems.append("口径与标准答案矛盾（矛盾标签被学了进去）")
        if i == unseen_idx:
            problems.append("训练外问题编造了具体答案（幻觉，训练里根本没有换货政策）")
        verdicts.append("✗ " + "；".join(problems) if problems else "✓")
    return verdicts


def main() -> None:
    print("【教学模拟声明】两个'模型'由 MockLLM 脚本预设，模拟数据质量对 SFT 行为的")
    print("  影响方向；不是真实训练结果——真实差异必须用你自己的评估集实测（见 ch63.5.1）。")

    print("\n── 训练数据对照（同样 3 条知识，两种质量）──")
    print("    clean 集（一致/规范）：")
    for q, a in TRAIN_CLEAN[:2]:
        print(f"        {q} → {a}")
    print("    dirty 集（漂移/矛盾/错别字）：")
    for q, a in TRAIN_DIRTY[:2]:
        print(f"        {q} → {a}")

    for name, script in (("clean_model（干净数据）", SCRIPT_CLEAN),
                         ("dirty_model（脏数据）", SCRIPT_DIRTY)):
        llm = MockLLM(script=script)
        outs = [llm.chat([{"role": "user", "content": q}]).content for q in TEST_QS]
        verdicts = judge(outs)
        print(f"\n── {name} 在 {len(TEST_QS)} 个测试问题上的表现 ──")
        for q, out, verdict in zip(TEST_QS, outs, verdicts):
            print(f"    Q: {q}")
            print(f"       A: {out}")
            print(f"       判定：{verdict}")
        n_ok = sum(1 for v in verdicts if v.startswith("✓"))
        print(f"    可用率：{n_ok}/{len(outs)}")

    print("\n── 结论（方向性，非量化承诺）──")
    print("  1) 脏数据的三宗罪都会被模型'忠实'学走：格式漂移、矛盾口径、错别字；")
    print("  2) 最危险的损失在训练外：干净数据教会模型'没依据就拒答'，")
    print("     脏数据里没有一致的拒答范式 → 模型学会的是'永远编一个具体答案'（幻觉被放大）；")
    print("  3) 所以 ch63 的铁律：先建评估集、再做数据清洗（去重/统一口径/纠错/脱敏——ch58），")
    print("     数据质量检查清单见正文 63.5.1。没有评估集就别谈微调。")


if __name__ == "__main__":
    main()
