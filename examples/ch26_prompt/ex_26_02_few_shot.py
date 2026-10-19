# EX-26-02 | Zero-shot vs Few-shot：同 prompt 不同输出的对照实验 | 运行: python3 examples/ch26_prompt/ex_26_02_few_shot.py
"""完整可运行（Mock，脚本驱动）：同一任务分别用 Zero-shot 与 Few-shot 两种 prompt，
观察输出差异；并诚实说明——Mock 的差异是脚本模拟的，真实模型上 few-shot 示例
才会真正"教会"模型格式与口径（示例输出已在教材标注为非真实记录）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from examples.common.llm_client import MockLLM  # noqa: E402

TASK = "把客户留言分类为：退款 / 换货 / 咨询"
MESSAGE = "耳机用了三天就没声音了，我要退钱！"

ZERO_SHOT = f"""{TASK}
只输出 JSON：{{"label": "..."}}
留言：{MESSAGE}"""

FEW_SHOT = f"""{TASK}
只输出 JSON：{{"label": "..."}}，参考以下示例的判断口径：

示例1
留言：颜色和图片差太多，帮我重新寄一个。
输出：{{"label": "换货"}}

示例2
留言：这个保险是保什么的？
输出：{{"label": "咨询"}}

示例3
留言：喝了一半发现异物，钱退给我。
输出：{{"label": "退款"}}

现在处理新留言：
留言：{MESSAGE}"""


def main() -> None:
    # 脚本模拟两版输出差异：zero-shot 被情绪词带偏，few-shot 稳定到退款
    llm = MockLLM(script=[
        {"content": '{"label": "换货"}'},
        {"content": '{"label": "退款"}'},
    ])
    r1 = llm.chat([{"role": "user", "content": ZERO_SHOT}])
    r2 = llm.chat([{"role": "user", "content": FEW_SHOT}])

    print("[Zero-shot] 只给任务不给示例：")
    print(f"    prompt 长度（近似字符）={len(ZERO_SHOT)}")
    print(f"    输出：{r1.content}   ← '退钱'被理解为换台新的？边界模糊时口径漂移")
    print("\n[Few-shot] 给 3 个带口径的示例：")
    print(f"    prompt 长度（近似字符）={len(FEW_SHOT)}")
    print(f"    输出：{r2.content}   ← 示例钉死'要钱=退款'的判断口径")
    print("\n[诚实声明] 本对照在 Mock 上由脚本驱动，证明的是'程序如何组织两种 prompt'；")
    print("    真实模型上 few-shot 的效果需在真实流量上评估（ch28 的 golden set 回归就是干这个的）。")
    print("\n[成本提醒] 示例会进入每次请求的 prompt → 按 token 计费：")
    print(f"    few-shot 比 zero-shot 多 {len(FEW_SHOT) - len(ZERO_SHOT)} 字符，且每次请求都要重付。")
    print("    示例选 2~5 个代表性边界样本即可，别把说明书塞进去。")


if __name__ == "__main__":
    main()
