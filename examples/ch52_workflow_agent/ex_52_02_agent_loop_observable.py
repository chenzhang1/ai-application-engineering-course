# EX-52-02 | Agent loop 的外部可观察行为：用日志事件流看清一轮完整循环
# 运行: python3 examples/ch52_workflow_agent/ex_52_02_agent_loop_observable.py
"""完整可运行（LLM_MODE=mock，MockLLM script 驱动，输出确定性）：

Agent 从外面看就是个黑盒函数：输入一句话，输出一段话。本例把黑盒拆开，
在 loop 的每个环节打**结构化事件**（event/round/trace_id/tool/duration_ms），
打印出"一轮完整 Agent loop"的事件流——这正是生产上排查 Agent 行为的依据
（ch54 的审计日志、ch60 的可观测都建立在同一套事件模型上）。

循环结构（ch24 手写过六步，ch42 框架托管过，本例为了看事件流再手写一遍）：
    loop_start → model_call(发起工具调用) → tool_call(执行) → tool_result(回传)
              → model_call(整合作答) → final_answer → loop_end
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # 仓库根：保证直接运行可 import examples
from examples.common.llm_client import ChatResult, get_llm


class EventTracer:
    """极简事件追踪器：生产上这里写 JSONL/Otel，教学上打印成对齐表格。"""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def emit(self, event: str, **fields: Any) -> None:
        rec = {"ts": round(time.monotonic() * 1000), "event": event, **fields}
        self.events.append(rec)
        print(f"  {rec['event']:<14} " + " ".join(f"{k}={v}" for k, v in fields.items()))


def tool_query_plan(plan_id: str) -> dict[str, Any]:
    """教学工具：查生产计划（真实场景=HTTP 调 Java 服务，ch56 展开）。"""
    return {"plan_id": plan_id, "product": "转向节", "qty": 1200, "status": "延期"}


TOOLS: dict[str, Callable[..., Any]] = {"query_plan": tool_query_plan}


def run_agent(question: str, *, tracer: EventTracer, max_rounds: int = 5) -> str:
    """手写 Agent loop：模型点名工具 → 执行 → 回传 → 直到模型不再点名工具。"""
    tracer.emit("loop_start", question=question)
    llm = get_llm(script=[
        # 第 1 轮模型输出：发起工具调用（MockLLM script 按调用次序返回）
        {"tool_calls": [{"name": "query_plan",
                         "arguments": {"plan_id": "P-1002"}}]},
        # 第 2 轮模型输出：整合工具结果作答（finish_reason=stop → 循环结束）
        {"content": "P-1002（转向节，1200 件）当前延期，建议先查供应商交付记录。"},
    ])
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": "你是生产计划助手，先查数据再下结论。"},
        {"role": "user", "content": question},
    ]
    for round_no in range(1, max_rounds + 1):
        t0 = time.monotonic()
        result: ChatResult = llm.chat(messages)
        tracer.emit("model_call", round=round_no,
                    finish_reason=result.finish_reason,
                    tool_calls=[c.name for c in result.tool_calls] or None,
                    duration_ms=round((time.monotonic() - t0) * 1000, 1))
        assistant_msg: dict[str, Any] = {"role": "assistant", "content": result.content}
        if result.tool_calls:  # 真实 API 形态：assistant 消息必须带回 tool_calls 原文
            assistant_msg["tool_calls"] = [
                {"id": c.id, "name": c.name, "arguments": c.arguments} for c in result.tool_calls]
        messages.append(assistant_msg)
        if not result.has_tool_calls:  # finish_reason=stop：模型认为可以收口了
            tracer.emit("final_answer", round=round_no, chars=len(result.content))
            tracer.emit("loop_end", rounds=round_no)
            return result.content
        for tc in result.tool_calls:  # 执行模型点名的每个工具
            fn = TOOLS.get(tc.name)
            tracer.emit("tool_call", round=round_no, tool=tc.name, args=json.dumps(tc.arguments, ensure_ascii=False))
            output = fn(**tc.arguments) if fn else {"error": f"未知工具 {tc.name}"}
            tracer.emit("tool_result", round=round_no, tool=tc.name,
                        summary=json.dumps(output, ensure_ascii=False)[:40])
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": json.dumps(output, ensure_ascii=False)})
    raise RuntimeError(f"超过 max_rounds={max_rounds}，模型一直在点名工具（防线见 52.7③）")


def main() -> None:
    tracer = EventTracer()
    print("== Agent loop 事件流（外部观察者视角）==")
    answer = run_agent("P-1002 这单什么情况？", tracer=tracer)
    print(f"\n最终回答：{answer}")
    print(f"\n事件总数={len(tracer.events)}，事件类型序列=")
    print(" → ".join(e["event"] for e in tracer.events))


if __name__ == "__main__":
    main()
