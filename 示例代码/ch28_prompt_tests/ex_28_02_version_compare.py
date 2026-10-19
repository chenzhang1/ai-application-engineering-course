# EX-28-02 | Prompt 版本管理：歧义任务改写前后的输出对比 | 运行: python3 示例代码/ch28_prompt_测试/ex_28_02_version_compare.py
"""完整可运行（Mock，脚本驱动）：一个歧义任务（"处理一下这个订单"）的 v1/v2 prompt，
演示歧义如何导致不可预测行为，以及改写模板化后的可预期输出；版本记录如何写 commit。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from 示例代码.公共.llm_client import MockLLM  # noqa: E402

ORDER = "ORD-30021（用户备注：家里没人，周末再送）"

# v1：歧义任务——"处理"是送？取消？改地址？模型只能猜
V1 = f"处理一下这个订单：{ORDER}"

# v2：把"处理"拆成明确的输入变量 + 动作清单 + 禁止项
V2 = f"""你是订单操作助手。对给定订单执行且仅执行"安排周末配送"操作：
1. 调用 reschedule_order(order_id, new_window="周末 09:00-18:00")；
2. 输出一行确认：已改期 + 新时间窗。
禁止：取消订单、修改商品、联系用户以外的操作。
订单：{ORDER}"""


def main() -> None:
    # 脚本模拟：v1 面对歧义可能走错分支；v2 确定走改期分支
    llm = MockLLM(script=[
        {"content": "好的，我将取消订单 ORD-30021 并退款，取消原因：用户无法收货。"},
        {"content": "已改期：ORD-30021 新配送窗口为周末 09:00-18:00。"},
    ])

    print("[v1 歧义 prompt]：")
    print(f"    prompt：{V1}")
    r1 = llm.chat([{"role": "user", "content": V1}])
    print(f"    输出：{r1.content}")
    print("    ★ 歧义任务的行为是抽盲盒：'处理'被理解成'取消+退款'——高危操作直接触发！")

    print("\n[v2 模板化改写]：")
    print(f"    prompt：{V2.splitlines()[0]} …（完整模板见源码）")
    r2 = llm.chat([{"role": "user", "content": V2}])
    print(f"    输出：{r2.content}")
    print("    动作唯一、禁止项显式、输出一行可断言——进 golden set 才有意义。")

    print("\n[版本管理实践]")
    print("    1) prompt 存 Git（同代码评审），重大改动走 PR+回归测试（ex_28_01）；")
    print("    2) 版本命名带语义：v1_ambiguous → v2_reschedule_only；")
    print("    3) 变更记录三件事：为什么改/改了哪些口径/回归结果（通过数与失败样本）；")
    print("    4) 线上按版本打标，能回滚：prompt 也是代码，出事要能退回上一版。")


if __name__ == "__main__":
    main()
