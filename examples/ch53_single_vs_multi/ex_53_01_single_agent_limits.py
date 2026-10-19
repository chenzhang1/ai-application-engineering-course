# EX-53-01 | 单 Agent 的三个疲劳信号：上下文膨胀、工具误选、职责混杂
# 运行: python3 examples/ch53_single_vs_multi/ex_53_01_single_agent_limits.py
"""完整可运行（tiktoken 真实计数 + 确定性匹配器，无网络）：

把三个领域的任务（订单查询 / 物流跟踪 / 发票开具）都塞给**一个** Agent，
用两个可测量的量演示"单 Agent 大杂烩"的成本：
    ① 上下文膨胀：每轮对话都背着全部历史与全部工具说明，token 数逐轮增长
       （count_tokens 用 tiktoken 真实计数，cl100k_base）；
    ② 工具误选：工具多了、描述相近了，"按请求选工具"的确定性匹配器
       （模拟模型选择依据的关键词匹配，教学替身）开始选错。
Java 对照：一个应用塞下所有功能 ↔ 单体应用没有模块边界——不是不能用，
是每加一个功能都在加重所有请求的负担。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # 仓库根
from examples.common.llm_client import count_tokens

# ---- 单 Agent 大杂烩：3 个领域 6 个工具，描述刻意写得相似 -------------------------
TOOLS_ALL: dict[str, str] = {
    "query_order": "查询订单信息，处理订单问题，返回订单状态",
    "query_logistics": "查询物流信息，处理订单的物流跟踪问题",
    "query_invoice": "查询发票信息，处理订单的发票开具问题",
    "create_invoice": "创建发票，为订单开具发票",
    "cancel_order": "取消订单，处理订单变更",
    "change_address": "修改订单地址，处理订单信息变更",
}
# 领域隔离后的子 Agent：每个只带自己领域的 2 个工具，描述更短更准
TOOLS_ORDER: dict[str, str] = {
    "query_order": "按订单号查询订单状态（金额/收货人/当前节点）",
    "cancel_order": "取消未发货订单（写操作，需审批）",
}
TOOLS_LOGISTICS: dict[str, str] = {
    "query_logistics": "按订单号查询物流轨迹与预计送达时间",
    "change_address": "修改未发货订单的收货地址",
}

_KV_SKIP = {"查", "一下", "的", "帮我", "请问", "怎么", "订单", "信息"}


def pick_tool(tools: dict[str, str], request: str) -> str:
    """确定性工具选择器（教学替身，模拟"模型按描述匹配请求"）：
    对请求做 2-gram 切分，与工具描述求重叠得分，取最高分（平分取先声明者）。"""
    grams = {request[i:i + 2] for i in range(len(request) - 1)} - _KV_SKIP
    best, best_score = "", -1
    for name, desc in tools.items():
        score = sum(1 for g in grams if g in desc)
        if score > best_score:
            best, best_score = name, score
    return best


def main() -> None:
    print("== 信号①：上下文膨胀（tiktoken cl100k_base 真实计数）==")
    system_all = "你是全能客服助手。可用工具：\n" + "\n".join(
        f"- {n}: {d}" for n, d in TOOLS_ALL.items())
    history: list[str] = []
    turns = ["帮我查一下订单 A1001 的信息", "再看看它的物流", "顺便把发票开了",
             "改一下收货地址", "还是取消吧"]
    for i, turn in enumerate(turns, 1):
        history.append(turn)
        prompt = system_all + "\n历史：\n" + "\n".join(history)
        n, method = count_tokens(prompt)
        print(f"  第{i}轮请求 prompt ≈ {n:>4} tokens（{method}）")

    print("\n== 信号②：工具误选（确定性匹配器，模拟选择依据）==")
    cases = [
        ("帮我查一下订单 A1001 的信息", "query_order"),
        ("这个包裹到哪了", "query_logistics"),
        ("开一张发票", "query_invoice"),
        ("改地址", "change_address"),
    ]
    wrong = 0
    for request, expected in cases:
        got = pick_tool(TOOLS_ALL, request)
        mark = "✓" if got == expected else "✗"
        wrong += got != expected
        print(f"  {mark} 「{request}」→ {got}（期望 {expected}）")
    print(f"  大杂烩 6 工具：误选 {wrong}/{len(cases)}")
    wrong_iso = sum(pick_tool(TOOLS_ORDER, r) != "query_order"
                    for r, e in cases if e == "query_order")
    print(f"  领域隔离后（订单子 Agent 只见 2 个工具）：查询类误选 {wrong_iso} 次，"
          f"且 prompt 系统段从 {count_tokens(system_all)[0]} tokens 缩到 "
          f"{count_tokens('你是订单助手。可用工具：\n' + chr(10).join(f'- {n}: {d}' for n, d in TOOLS_ORDER.items()))[0]} tokens")

    print("\n== 信号③：职责混杂（无法独立测试/独立上线）==")
    print("  - 发票工具改一个字段校验 → 全能 Agent 的 6 个工具一起回归测试")
    print("  - 权限模型：查/写/撤销混在同一个上下文，工具级权限（ch54）无法按领域收敛")
    print("  - 结论预告：这不是'必须拆多 Agent'，而是'拆了之后每个部件可独立演进'——53.2 给判断标准")


if __name__ == "__main__":
    main()
