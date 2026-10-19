# EX-37-01 | 什么时候不需要 LangChain：决策表自检 | 运行: python3 示例代码/ch37_lc_boundary/ex_37_01_decision_table.py
"""完整可运行（不联网、不依赖模型）：把"要不要上 LangChain"的判断标准写成可执行的
决策函数——输入一个场景特征包，输出"裸 SDK / 组件级使用 / 全家桶 / 换 LangGraph"建议。

这不是玩具：上线评审时把新 AI 需求的特征填进来跑一遍，比开会拍脑袋有据可依。
"""
from __future__ import annotations

from typing import Literal

# 每个特征都对应一章学过的能力：成本（ch21）、工具闭环（ch24/42）、检索（ch25/41）……
Advice = Literal["bare_sdk", "components_only", "full_langchain", "langgraph"]


def advise(
    *,
    single_turn: bool,            # 是否单轮问答（无多步状态）
    steps: int,                   # 流水线步骤数（1=直接调用，2~3=简单管道）
    needs_tools: bool,            # 是否需要模型点名工具（查库/调内部 API）
    needs_model_switch: bool,     # 是否需要频繁换厂商 / 多模型 A/B
    needs_retrieval: bool,        # 是否需要检索增强（RAG）
    needs_hitl_or_resume: bool,   # 是否需要人工审批 / 中断恢复 / 持久化
) -> Advice:
    """按第七部分的决策表给出建议。判定顺序 = 阻断性从高到低。"""
    if needs_hitl_or_resume:
        # 人工介入/中断恢复是状态机需求：LangChain（链）表达不了，直接 LangGraph
        return "langgraph"
    if single_turn and steps == 1 and not needs_tools and not needs_model_switch:
        # 裸 SDK 十行代码搞定，框架在这类场景是纯认知开销（37.2 案例 1）
        return "bare_sdk"
    if needs_tools:
        # create_agent 替你处理消息回写/tool_call_id 配对/循环终止（对照 EX-24-03）
        return "full_langchain"
    if needs_retrieval or needs_model_switch:
        # 用文档组件 / Retriever / Runnable 抽象，但别上重型 Agent
        return "components_only"
    if steps >= 2:
        # 简单管道：手写函数组合即可；想要统一 batch/stream/ainvoke 再引入 LCEL
        return "components_only"
    return "bare_sdk"


ADVICE_CN: dict[str, str] = {
    "bare_sdk": "裸 SDK（第四部分）——框架是纯开销",
    "components_only": "组件级使用（Prompt/文档/Retriever）——不引入 Agent",
    "full_langchain": "LangChain 全流程（create_agent + 工具）",
    "langgraph": "LangGraph（第八部分）——这是状态机需求，链表达不了",
}

CASES: list[tuple[str, dict[str, bool | int]]] = [
    ("案例 1：客服 FAQ 单轮问答，prompt 固定", dict(single_turn=True, steps=1, needs_tools=False,
                                                    needs_model_switch=False, needs_retrieval=False,
                                                    needs_hitl_or_resume=False)),
    ("案例 2：文档知识库问答（检索+生成）", dict(single_turn=True, steps=2, needs_tools=False,
                                                  needs_model_switch=False, needs_retrieval=True,
                                                  needs_hitl_or_resume=False)),
    ("案例 3：查订单+查物流后作答（两个内部 API）", dict(single_turn=True, steps=1, needs_tools=True,
                                                        needs_model_switch=False, needs_retrieval=False,
                                                        needs_hitl_or_resume=False)),
    ("案例 4：运维审批流——高危操作要人确认，可中断恢复", dict(single_turn=False, steps=3, needs_tools=True,
                                                          needs_model_switch=True, needs_retrieval=False,
                                                          needs_hitl_or_resume=True)),
    ("案例 5：多厂商 A/B 灰度，调用前要做脱敏预处理", dict(single_turn=True, steps=2, needs_tools=False,
                                                        needs_model_switch=True, needs_retrieval=False,
                                                        needs_hitl_or_resume=False)),
]


def main() -> None:
    print("决策表（判定顺序 = 阻断性从高到低）：")
    print("  1) 需要人工审批/中断恢复/持久化  → LangGraph")
    print("  2) 单轮 + 单步 + 无工具 + 不换模型 → 裸 SDK")
    print("  3) 需要工具调用循环              → create_agent（LangChain）")
    print("  4) 需要检索/换模型/简单管道       → 组件级使用\n")

    for title, feats in CASES:
        advice = advise(**feats)  # type: ignore[arg-type]
        print(f"{title}\n    → 建议：{ADVICE_CN[advice]}")

    # 边界自检：参数组合必须总有结论（决策表不许有"查无此项"）
    import itertools

    count = 0
    for combo in itertools.product([True, False], repeat=5):
        for steps in (1, 3):
            advise(single_turn=combo[0], steps=steps, needs_tools=combo[1],
                   needs_model_switch=combo[2], needs_retrieval=combo[3],
                   needs_hitl_or_resume=combo[4])
            count += 1
    print(f"\n[自检] {count} 种特征组合全部有唯一结论，决策表完备。")


if __name__ == "__main__":
    main()
