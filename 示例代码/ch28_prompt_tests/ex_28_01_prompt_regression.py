# EX-28-01 | Prompt 回归测试：golden set（固定输入 + 断言规则）| 运行: python3 示例代码/ch28_prompt_测试/ex_28_01_prompt_regression.py
"""完整可运行（Mock，脚本驱动）：为售后分类 prompt 建 golden set——
一组固定输入 + 每条输入的断言规则（必须含/不得含/格式约束），跑通过率。
同一套断言同时跑 v1 与 v2 两版 prompt，演示"改 prompt = 改代码，必须过测试"。

pytest 版本见 测试/test_ch28.py（本文件是可独立运行的 CLI 版）。
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from 示例代码.公共.llm_client import MockLLM  # noqa: E402

# ---- golden set：固定输入 + 断言规则（数据与断言分离，便于追加样本）---------
GOLDEN: list[dict[str, Any]] = [
    {"input": "耳机用了三天就没声音，我要退钱！", "must_contain": ["退款"], "must_not": ["换货"]},
    {"input": "颜色和图片差太多，帮我重新寄一个。", "must_contain": ["换货"], "must_not": ["退款"]},
    {"input": "这个保险是保什么的？", "must_contain": ["咨询"], "must_not": ["退款", "换货"]},
    {"input": "喝了一半发现异物，钱退给我。", "must_contain": ["退款"]},
    {"input": "屏幕摔碎了，能修吗？", "must_contain": ["咨询"]},
]

PROMPTS: dict[str, str] = {
    "v1": "把客户留言分类为：退款/换货/咨询。只输出 JSON：{{\"label\": \"...\"}}\n留言：{input}",
    "v2": ("你是售后分类器。判断口径：要钱=退款；要新的/重寄=换货；其余=咨询。\n"
           "只输出 JSON：{{\"label\": \"退款|换货|咨询\"}}\n留言：{input}"),
}

# 模拟两版 prompt 的模型行为（脚本驱动；真实模型行为见教材"示例输出"标注）
BEHAVIOR: dict[str, dict[str, str]] = {
    "v1": {"耳机用了三天就没声音，我要退钱！": '{"label": "换货"}',   # v1 口径漂移
           "颜色和图片差太多，帮我重新寄一个。": '{"label": "换货"}',
           "这个保险是保什么的？": '{"label": "咨询"}',
           "喝了一半发现异物，钱退给我。": '{"label": "退款"}',
           "屏幕摔碎了，能修吗？": '{"label": "咨询"}'},
    "v2": {"耳机用了三天就没声音，我要退钱！": '{"label": "退款"}',   # v2 口径钉死
           "颜色和图片差太多，帮我重新寄一个。": '{"label": "换货"}',
           "这个保险是保什么的？": '{"label": "咨询"}',
           "喝了一半发现异物，钱退给我。": '{"label": "退款"}',
           "屏幕摔碎了，能修吗？": '{"label": "咨询"}'},
}


def run_case(llm: MockLLM, prompt_tpl: str, case: dict[str, Any]) -> tuple[bool, str]:
    messages = [{"role": "user", "content": prompt_tpl.format(input=case["input"])}]
    out = llm.chat(messages).content
    problems: list[str] = []
    try:
        parsed = json.loads(out)
        label = str(parsed.get("label", ""))
    except json.JSONDecodeError:
        return False, f"输出不是合法 JSON：{out!r}"
    for word in case.get("must_contain", []):
        if word not in label:
            problems.append(f"应含'{word}'")
    for word in case.get("must_not", []):
        if word in label:
            problems.append(f"不得含'{word}'")
    return (not problems), (out + " " + "；".join(problems) if problems else out)


def run_suite(version: str) -> list[tuple[dict[str, Any], bool, str]]:
    llm = MockLLM(script=[{"content": BEHAVIOR[version][c["input"]]} for c in GOLDEN])
    results = []
    for case in GOLDEN:
        ok, detail = run_case(llm, PROMPTS[version], case)
        results.append((case, ok, detail))
    return results


def main() -> None:
    for version in ("v1", "v2"):
        results = run_suite(version)
        passed = sum(1 for _, ok, _ in results if ok)
        print(f"[{version}] 通过 {passed}/{len(GOLDEN)}")
        for case, ok, detail in results:
            mark = "✓" if ok else "✗"
            print(f"    {mark} 输入={case['input'][:18]}… → {detail}")
        print()

    print("[golden set 三原则]")
    print("    1) 输入固定：同一批样本永远不变，改的只有 prompt（被测对象）；")
    print("    2) 断言是规则不是全文：断'含退款/不含换货'，别断整句输出（模型措辞会变）；")
    print("    3) 失败样本回填：线上 badcase 脱敏后进 GOLDEN，回归网越滚越密。")
    print("    ★ Mock 只能测控制流；真实 prompt 的回归要在真实模型上跑（CI 中标夜间任务）。")


if __name__ == "__main__":
    main()
