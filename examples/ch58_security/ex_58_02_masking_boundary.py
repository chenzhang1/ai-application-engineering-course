# EX-58-02 | 数据脱敏：正则为主 + LLM 补充的混合方案边界 | 运行: python3 examples/ch58_security/ex_58_02_masking_boundary.py
"""完整可运行（标准库 + 共享 MockLLM，离线）：演示"正则+LLM 混合脱敏"各自能干什么、
会在哪里失守。核心结论：
  - 正则：确定性、可审计、可回归——漏报模式可以枚举并逐个修复（保下限）；
  - LLM：覆盖面广（能处理变体），但会改错内容、无法回归测试（概率级，不能当唯一防线）；
  - 生产姿势：正则为主 + LLM 结果只作"疑似敏感"提示交人工确认 + 脱敏发生在
    进 Prompt/进日志之前 + 脱敏映射表单独保管（不在日志里出现明文对照）。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from examples.common.llm_client import MockLLM  # noqa: E402

# 正则模式库：每种模式一个"类型 + 正则 + 替换占位符"（生产会放进配置并可热更新）
PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("手机号", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"), "[手机号]"),
    ("身份证", re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"), "[身份证号]"),
    ("邮箱", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[邮箱]"),
]


def mask_with_regex(text: str) -> tuple[str, list[str]]:
    """正则脱敏：返回 (脱敏后文本, 命中类型列表)。确定性：同输入必同输出。"""
    kinds: list[str] = []
    for kind, pattern, placeholder in PATTERNS:
        if pattern.search(text):
            kinds.append(kind)
            text = pattern.sub(placeholder, text)
    return text, kinds


def main() -> None:
    print("── 第一幕：正则脱敏的标准命中 ──")
    case1 = "客户张三，手机 13812345678，邮箱 zs@example.com，已实名。"
    masked, kinds = mask_with_regex(case1)
    print(f"    原文：{case1}")
    print(f"    脱敏：{masked}  命中：{kinds}")

    print("\n── 第二幕：正则的漏报边界（两个真实世界的变体）──")
    case2 = "备用联系方式：１３８１２３４５６７８（全角数字）"   # 全角数字：\d 不匹配
    masked2, kinds2 = mask_with_regex(case2)
    print(f"    变体A 原文：{case2}")
    print(f"    变体A 脱敏：{masked2}  命中：{kinds2} ← 漏报！\\d 只匹配半角数字")
    case3 = "填表写的号码是 138-1234-5678，分段格式"
    masked3, kinds3 = mask_with_regex(case3)
    print(f"    变体B 原文：{case3}")
    print(f"    变体B 脱敏：{masked3}  命中：{kinds3} ← 漏报！分隔符破坏了连续 11 位假设")
    print("    教训：正则的漏报可枚举、可逐个修复（把变体加进模式库再回归），")
    print("          但'修复到什么程度算够'是业务决定——这正是不该指望单一防线的原因。")

    print("\n── 第三幕：LLM 脱敏的误改风险（Mock 脚本模拟，脚本模拟真实模型常见失守形态）──")
    llm = MockLLM(script=[
        # 真实模型做"脱敏改写"时的典型输出：敏感信息遮住了，但顺手改了不该改的
        {"content": "客户张三（[手机号]，[邮箱]），工号 9 开头的员工负责跟进，已实名。"},
    ])
    case4 = "客户张三，手机 13812345678，邮箱 zs@example.com，工号 A1024 的员工负责跟进，已实名。"
    llm_output = llm.chat([
        {"role": "system", "content": "你是脱敏助手：把文本中的手机号/邮箱替换为占位符，其余内容保持原样。"},
        {"role": "user", "content": case4},
    ])
    print(f"    原文：        {case4}")
    print(f"    LLM 脱敏后：  {llm_output.content}")
    print(f"    对比：工号 A1024 被改成了'工号 9 开头'——业务字段被误改，且这种错")
    print("          无法用回归测试锁定（同输入两次输出可能不同），只能人工抽检。")

    print("\n── 生产姿势小结（三层）──")
    print("  1) 正则为主：所有确定性可枚举的形态；模式库进版本管理，改动走回归；")
    print("  2) LLM 只做'疑似敏感'标记器：输出候选区间交人工确认，不直接改写正文；")
    print("  3) 位置纪律：脱敏必须发生在进 Prompt / 进日志 / 进评估集之前；")
    print("     脱敏映射表（占位符↔原文）单独加密保管，且永不进日志——否则日志本身成了新的泄露源。")


if __name__ == "__main__":
    main()
