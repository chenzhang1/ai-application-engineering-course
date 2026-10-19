# EX-21-03 | 模型不确定性的 Mock 对照实验：temperature 在 Mock 下无效 | 运行: python3 示例代码/ch21_tokens/ex_21_03_mock_determinism.py
"""完整可运行（Mock 模式，不联网）：演示"同输入同输出"的确定性，并诚实展示
temperature 参数被 Mock 忽略的事实——真实模型上 temperature>0 会带来随机多样性。

幻觉/知识时效无法用 Mock 演示（Mock 没有"知识"），对应讨论见教材正文与示例输出标注。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from 示例代码.公共.llm_client import MockLLM, RealLLM  # noqa: E402

MESSAGES = [
    {"role": "system", "content": "你是一个客服助手"},
    {"role": "user", "content": "退货政策是什么？"},
]


def main() -> None:
    llm = MockLLM()
    print("[实验 1] Mock 同输入连跑 3 次（不传 temperature）：")
    outputs = [llm.chat(MESSAGES).content for _ in range(3)]
    for i, o in enumerate(outputs, 1):
        print(f"    第 {i} 次：{o}")
    assert outputs[0] == outputs[1] == outputs[2]
    print("    → 完全一致：MockLLM 是确定性规则模型，无随机数。")

    print("\n[实验 2] Mock 下传 temperature=1.5 / top_p=0.5：")
    r_hot = llm.chat(MESSAGES, temperature=1.5, top_p=0.5)
    r_cold = llm.chat(MESSAGES, temperature=0.0)
    print(f"    temperature=1.5 → {r_hot.content}")
    print(f"    temperature=0.0 → {r_cold.content}")
    print(f"    两者相同：{r_hot.content == r_cold.content}（Mock 接受参数但忽略——接口兼容，行为确定）")
    print("    ★ 类比：Mock 像写死的单元测试桩；真实模型 temperature>0 才会掷骰子。")

    print("\n[实验 3] 真实模式的行为约定（代码层面核实，不在本沙箱真实调用）：")
    try:
        RealLLM(api_key=None)
    except RuntimeError as e:
        print("    RealLLM 缺 Key 时抛 RuntimeError（前 2 行）：")
        for line in str(e).splitlines()[:3]:
            print(f"      {line}")
    print("    真实调用时 temperature 语义见教材 23.3：0≈稳定可复现，1≈默认多样，>1 易失控。")


if __name__ == "__main__":
    main()
