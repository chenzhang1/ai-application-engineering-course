# EX-23-02 | 参数实验：temperature/top_p/max_tokens 在 Mock 与 Real 下的差异 | 运行: python3 示例代码/ch23_chat/ex_23_02_params_demo.py
"""完整可运行（Mock）：把三类生成参数传给 MockLLM，验证"接口接受、行为确定"；
真实模型的参数语义（含 max_tokens 超限时的 finish_reason=length）见教材表格——
本沙箱无 Key，不进行真实调用，不做任何虚构输出。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from 示例代码.公共.llm_client import MockLLM  # noqa: E402

MESSAGES = [{"role": "user", "content": "给这个订单写一句催发货的话"}]


def main() -> None:
    llm = MockLLM()
    print("[实验] 同一组消息，传不同生成参数（Mock 接受并忽略）：")
    param_sets: list[tuple[str, dict[str, object]]] = [
        ("默认", {}),
        ("temperature=0.0", {"temperature": 0.0}),
        ("temperature=1.2, top_p=0.9", {"temperature": 1.2, "top_p": 0.9}),
        ("max_tokens=5", {"max_tokens": 5}),
    ]
    results = []
    for label, params in param_sets:
        r = llm.chat(MESSAGES, **params)
        results.append(r.content)
        print(f"    {label:<28} → {r.content}  (finish_reason={r.finish_reason})")

    same = len(set(results)) == 1
    print(f"\n    四次输出完全相同：{same}（Mock 无随机源；真实模型上前两组通常不同）")

    print("\n[接口契约] Mock/Real 对生成参数的态度：")
    print("    Mock：签名接受 **kwargs 全部吞掉 → 保证教学脚本在双模式下都能跑；")
    print("    Real：参数原样透传 client.chat.completions.create（openai 3.35.1 签名已核实")
    print("          含 temperature/top_p/max_tokens/max_completion_tokens）。")
    print("    ★ 诚实声明：Mock 无法演示真实模型上这些参数的效果差异，教材相应表格标注为语义说明。")


if __name__ == "__main__":
    main()
