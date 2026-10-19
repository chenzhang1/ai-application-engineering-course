# EX-01-01 | 运行命令: python3 examples/ch01_concepts/ex_01_01_concept_sketches.py
"""五种 AI 应用形态的最小结构示意（不联网、不调用任何模型 API）。

脚本里的 fake_llm 用固定规则模拟"模型返回"，只用于看清五种形态的
程序结构差异：直调 / RAG / 工具调用 / 工作流 / Agent。
真实模型调用从第四部分开始，统一走 examples/common/llm_client.py。
"""
from __future__ import annotations

from typing import Callable


def fake_llm(messages: list[dict[str, str]]) -> str:
    """确定性假模型：永远回同样格式的字符串（仅示意调用形态）。"""
    return f"[模拟回复] 已收到：{messages[-1]['content'][:18]}…"


def demo_plain_llm() -> None:
    """形态一：大模型直调。一次请求，一次回复。"""
    print("== 1. 大模型直调（LLM API）==")
    reply = fake_llm([{"role": "user", "content": "把这句话翻译成英文：你好"}])
    print("   程序结构：messages -> 模型 -> reply（一次往返）")
    print(f"   {reply}\n")


def demo_rag() -> None:
    """形态二：RAG。先检索资料，再把资料塞进提示词。"""
    print("== 2. RAG（检索增强生成）==")
    knowledge_base: dict[str, str] = {"年假": "公司年假每年 15 天，可跨年结转 5 天。"}
    question = "年假可以跨年吗？"
    context = knowledge_base["年假"]  # 现实中是向量检索，这里是查字典示意
    reply = fake_llm([{"role": "user", "content": f"参考资料：{context}\n问题：{question}"}])
    print("   程序结构：问题 -> 检索 -> (资料+问题) -> 模型 -> 带引用的回答")
    print(f"   检索到的资料：{context}")
    print(f"   {reply}\n")


def demo_tool_call() -> None:
    """形态三：工具调用。模型点名要哪个函数，程序来执行。"""
    print("== 3. 工具调用（Function Calling）==")
    tools: dict[str, Callable[[str], str]] = {"query_order": lambda oid: f"订单 {oid}：已发货"}
    ask = "帮我查订单 A1001"
    chosen_tool, args = "query_order", "A1001"  # 现实中由模型输出，这里写死示意
    result = tools[chosen_tool](args)  # 执行者是程序，不是模型
    reply = fake_llm([{"role": "user", "content": f"工具结果：{result}\n问题：{ask}"}])
    print("   程序结构：问题 -> 模型点名工具 -> 程序执行 -> 结果回传 -> 模型作答")
    print(f"   模型点名：{chosen_tool}({args})；执行结果：{result}")
    print(f"   {reply}\n")


def demo_workflow() -> None:
    """形态四：工作流。节点顺序写死在代码里，确定性执行。"""
    print("== 4. 工作流（Workflow）==")
    state: dict[str, object] = {"ticket": "用户反馈：页面打不开"}
    state["classify"] = "网络类"  # 节点 1：分类（现实实现可以是模型或规则）
    state["reply"] = f"已按『{state['classify']}』走标准处理流程"  # 节点 2：应答
    print("   程序结构：节点1 -> 节点2 -> …（路线固定，代码说了算）")
    print(f"   最终状态：{state}\n")


def demo_agent() -> None:
    """形态五：Agent。模型在循环里自己决定下一步，直到任务完成。"""
    print("== 5. Agent（智能体）==")
    steps: list[str] = []
    goal = "找出订单 A1001 的物流单号"
    done = False
    turn = 0
    while not done:  # 现实中有最大轮数、预算等终止条件
        turn += 1
        if turn == 1:
            steps.append("决定：调用 query_order(A1001)")
        else:
            steps.append("决定：信息够了，输出答案")
            done = True
    print("   程序结构：while 未完成： 模型决定下一步 -> 执行 -> 回到循环")
    for s in steps:
        print(f"   第{steps.index(s) + 1}轮 {s}")
    print(f"   目标：{goal}\n")


def main() -> None:
    demo_plain_llm()
    demo_rag()
    demo_tool_call()
    demo_workflow()
    demo_agent()


if __name__ == "__main__":
    main()
