# EX-29-03 | 用 pytest 给 AI 生成的代码上护栏 | 运行: python3 examples/ch29_ai_collab/ex_29_03_guard_generated.py
"""完整可运行：一段"AI 生成的"去重函数自带典型 bug（把 list 当 set 元素会炸、
且误用 dict 去重会丢顺序），用 pytest 断言当场抓住，再展示修复版全绿。
工程含义：AI 写代码，你写测试——测试是协作的验收合同。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# ---- AI 生成的第一版（含两个真实常见 bug）----------------------------------
def dedupe_ai_buggy(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """AI 生成：用 dict.fromkeys 去重——对 unhashable 元素直接 TypeError。"""
    return list(dict.fromkeys(items))  # type: ignore[arg-type]


# ---- 修复版（人类补测试后迭代的结果）---------------------------------------
def dedupe(items: list[Any]) -> list[Any]:
    """保持首次出现顺序去重；可哈希元素直接比，dict 按内容签名比。"""
    seen: list[Any] = []
    out: list[Any] = []
    for x in items:
        try:
            key: Any = x  # 可哈希：直接当签名（str/int/tuple…）
        except TypeError:  # noqa: PERF203 —— unhashable（如 dict）：用内容字符串当签名
            key = str(sorted(x.items(), key=lambda kv: kv[0]))
        if key not in seen:
            seen.append(key)
            out.append(x)
    return out


def check(name: str, cond: bool, detail: str = "") -> bool:
    print(f"    {'✓' if cond else '✗'} {name}{('（' + detail + '）') if detail else ''}")
    return cond


def main() -> None:
    print("[护栏测试] 对 AI 第一版逐条断言（pytest 里同样的断言会 fail 并给堆栈）：")
    failed = False
    try:
        dedupe_ai_buggy([{"a": 1}, {"a": 1}])          # 可哈希？dict 不可哈希 → 直接炸
    except TypeError as e:
        failed = True
        print(f"    ✗ test_unhashable_input: TypeError: {e}")
    ok1 = check("test_unhashable_input（期望能处理 dict 列表）", not failed)

    result = dedupe_ai_buggy(["b", "a", "b", "a"])     # 字符串场景它反而"能用"
    ok2 = check("test_hashable_case（['b','a','b','a'] → ['b','a']）", result == ["b", "a"])
    print("\n    结论：第一版在简单场景蒙对、真实场景崩溃——不跑测试根本看不出来。")

    print("\n[修复版] 全部断言重跑：")
    passed = check("test_unhashable_input", dedupe([{"a": 1}, {"a": 1}]) == [{"a": 1}])
    passed &= check("test_hashable_case", dedupe(["b", "a", "b", "a"]) == ["b", "a"])  # type: ignore[arg-type]
    passed &= check("test_order_kept", dedupe([{"x": 2}, {"x": 1}, {"x": 2}])[0] == {"x": 2})
    verdict = "3/3 全绿" if passed else "仍有失败，继续迭代"  # 只看修复版的三条断言
    print(f"\n    修复版 {verdict} —— AI 迭代 + 人类测试 = 交付物。")
    print("\n[协作流程] AI 出码 → pytest 护栏（含边界/非法输入）→ 失败信息回喂 AI → 复跑全绿 → 才进 PR。")
    print("    本文件是可运行演示；真正的 pytest 版在 tests/test_ch29.py。")


if __name__ == "__main__":
    main()
