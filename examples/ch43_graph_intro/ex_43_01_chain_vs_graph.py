# EX-43-01 | 链式硬编码 vs 图编排：需求变更下的两种命运 | 运行: python3 examples/ch43_graph_intro/ex_43_01_chain_vs_graph.py
"""完整可运行：不用任何框架，先体会"控制流写死在代码里"的维护代价。

场景（合成案例）：客服工单处理管线。v1 是一条硬编码链；v2 追加两条业务规则
（敏感工单先审、加急工单跳过排队）后 if/elif 蔓延。本章后面用 LangGraph 把
"控制流"从"业务函数"里拆出来——这正是"为什么需要图"的答案。
"""
from __future__ import annotations

from typing import Callable


def normalize(text: str) -> str:
    """清洗：去首尾空白、统一小写。"""
    return text.strip().lower()


def classify(text: str) -> str:
    """分类：关键词规则（真实系统里常换成模型分类，见 ch45）。"""
    if "发票" in text or "退款" in text:
        return "billing"
    if "报错" in text or "异常" in text:
        return "tech"
    return "general"


def handle_billing(text: str) -> str:
    return f"[账务通道] 处理：{text}"


def handle_tech(text: str) -> str:
    return f"[技术通道] 处理：{text}"


def handle_general(text: str) -> str:
    return f"[通用通道] 处理：{text}"


# ---------------------------------------------------------------------------
# v1：硬编码链——控制流和业务函数焊死在一起
# ---------------------------------------------------------------------------


def pipeline_v1(text: str) -> str:
    """一条直线：normalize → classify → 按类别分发。"""
    cleaned = normalize(text)
    category = classify(cleaned)
    handler: dict[str, Callable[[str], str]] = {
        "billing": handle_billing,
        "tech": handle_tech,
        "general": handle_general,
    }
    return handler[category](cleaned)


# ---------------------------------------------------------------------------
# v2：需求变更之后——if/elif 开始蔓延（每个新规则都要改这根链）
# ---------------------------------------------------------------------------


def pipeline_v2(text: str, *, is_vip: bool = False) -> str:
    cleaned = normalize(text)
    # 新规则 1：敏感工单必须先人工审核
    if "身份证" in cleaned or "银行卡" in cleaned:
        return f"[人工审核] 拦截：{text}"
    # 新规则 2：VIP 加急工单跳过排队
    if is_vip:
        return pipeline_v1(cleaned) + "（VIP 加急）"
    # 新规则 3：夜间时段账务工单只受理不执行……
    return pipeline_v1(cleaned)


def main() -> None:
    tickets = [
        "我的 发票 抬头开错了",
        "App 一直 报错 闪退",
        "请查一下我的 银行卡 绑定信息",
    ]
    print("== v1：硬编码链 ==")
    for t in tickets:
        print(f"  {t!r:>24} -> {pipeline_v1(t)}")

    print("== v2：规则长进代码里 ==")
    print(f"  {'敏感工单':>14} -> {pipeline_v2(tickets[2])}")
    print(f"  {'VIP 报错工单':>12} -> {pipeline_v2(tickets[1], is_vip=True)}")

    print(
        "结论：v2 里'业务函数'没变，变的是控制流——但控制流改一次，就要动一次管线代码。\n"
        "把控制流抽出来变成'图'，节点只管业务，连线只管流转，这就是 LangGraph 的出发点。"
    )


if __name__ == "__main__":
    main()
