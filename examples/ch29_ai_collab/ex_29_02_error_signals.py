# EX-29-02 | 识别模型错误输出的 5 个信号 | 运行: python3 examples/ch29_ai_collab/ex_29_02_error_signals.py
"""完整可运行（Mock，脚本驱动）：5 个"模型在胡说"的信号各配一个真实形态样例 +
人工/自动核查动作；最后演示信号 1 的自动化检测器（函数签名核实）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from examples.common.llm_client import MockLLM  # noqa: E402

SIGNALS: list[tuple[str, str, str]] = [
    ("信号1 虚构 API/参数",
     "使用 client.chat.completions.create(model=..., messages=..., max_retries=3, api_version='2024-06')",
     "对 SDK 签名逐一 inspect/查官方文档核实——api_version 不存在；max_retries 是客户端构造参数，create 不收"),
    ("信号2 过时写法",
     "from langchain.chains import LLMChain; LLMChain(llm=llm, prompt=prompt).run(x)",
     "查库版本（requirements.txt 是 1.x）与官方迁移指南——chains 老写法已被替代"),
    ("信号3 引用不存在的本地符号",
     "from app.services import OrderService; OrderService.refund(order_id)",
     "在本仓库 Grep/直接 import 验证——你的项目里没有这个类或方法"),
    ("信号4 过度自信话术",
     "这肯定能解决你的问题，100% 没问题，直接上线即可。",
     "凡绝对化表述一律加测试验证；模型没有执行过任何代码"),
    ("信号5 输出与运行结果矛盾",
     "代码已通过全部测试（其实从未运行过 pytest）",
     "自己跑一遍 pytest/示例再采信；以运行记录为准，不以口吻为准"),
]


def check_signal1(claim: str) -> list[str]:
    """信号 1 的自动检测：把模型建议的 kwargs 与真实 SDK 签名对比。"""
    import inspect

    from openai.resources.chat.completions import Completions

    valid = set(inspect.signature(Completions.create).parameters)
    claimed = {"model", "messages", "max_retries", "api_version"}
    return sorted(a for a in claimed if a not in valid)


def main() -> None:
    llm = MockLLM(script=[{"content": desc} for _, desc, _ in SIGNALS])

    print("5 个信号 ×（样例输出 → 核查动作）：\n")
    for i, (title, sample, action) in enumerate(SIGNALS, 1):
        r = llm.chat([{"role": "user", "content": title}])
        print(f"    {title}")
        print(f"      样例：{sample[:64]}{'…' if len(sample) > 64 else ''}")
        print(f"      核查：{action}\n")

    print("[信号 1 的自动化示例]（真实执行，非演示）")
    bad = check_signal1("api_version='2024-06'")
    print(f"    模型建议的参数中被真实 create 签名拒绝的：{bad}")
    assert bad == ["api_version", "max_retries"]
    print("    注意 max_retries 也被拒绝：它属于 OpenAI 客户端构造参数，不属于 create——")
    print("    这正是'参数张冠李戴'的常见形态。'让工具裁决模型'：签名/文档/测试是事实源，模型只是提议者。")

    print("\n[总原则] 模型输出的地位 = 实习生的 PR：可以采纳，但合并前必须过")
    print("    编译、测试、签名核实三道闸；三道闸都自动化，协作效率才真正起飞（ch29.4）。")


if __name__ == "__main__":
    main()
