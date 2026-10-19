# EX-50-02 | 节点重试 RetryPolicy 与图级错误处理 | 运行: python3 示例代码/ch50_streaming_errors/ex_50_02_retry_and_errors.py
"""完整可运行：三个实验。

  A. RetryPolicy：抖动节点前两次抛 ValueError，第 3 次成功——节点级自动重试
     （参数在 1.2.16 实测：initial_interval/backoff_factor/max_interval/
       max_attempts/jitter/retry_on，来自 langgraph.types）；
  B. 重试耗尽：异常从 invoke 冒出，节点名与任务 id 在错误信息里；
  C. "错误即数据"模式：节点内 try/except，把失败写进状态，用条件边走降级分支
     ——生产上最常用的兜底。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from langgraph.graph import END, START, StateGraph  # noqa: E402
from langgraph.types import RetryPolicy  # noqa: E402


def merge_list(a: list[str] | None, b: list[str] | None) -> list[str]:
    return (a or []) + (b or [])


class JobState(TypedDict):
    result: str
    errors: Annotated[list[str], merge_list]


def make_flaky_node(fail_times: int, tag: str):
    """闭包计数：前 fail_times 次抛异常（真实场景：下游 5xx/超时）。"""
    calls = {"n": 0}

    def flaky(state: JobState) -> dict:
        calls["n"] += 1
        if calls["n"] <= fail_times:
            raise ValueError(f"{tag} 第 {calls['n']} 次调用失败（模拟下游抖动）")
        return {"result": f"{tag} 成功（第 {calls['n']} 次尝试）"}

    return flaky


def main() -> None:
    # A：RetryPolicy 自动重试——max_attempts=3，指数退避从 0.05s 起，关抖动保证输出可复现
    g = StateGraph(JobState)
    g.add_node("flaky", make_flaky_node(2, "flaky"),
               retry_policy=RetryPolicy(retry_on=ValueError, max_attempts=3,
                                        initial_interval=0.05, jitter=False))
    g.add_edge(START, "flaky"); g.add_edge("flaky", END)
    r = g.compile().invoke({"result": "", "errors": []})
    print("A 重试成功：", r["result"])

    # B：重试耗尽 → 异常冒泡
    g2 = StateGraph(JobState)
    g2.add_node("flaky", make_flaky_node(99, "hopeless"),
                retry_policy=RetryPolicy(retry_on=ValueError, max_attempts=2,
                                         initial_interval=0.05, jitter=False))
    g2.add_edge(START, "flaky"); g2.add_edge("flaky", END)
    try:
        g2.compile().invoke({"result": "", "errors": []})
    except ValueError as e:
        print("B 重试耗尽：", e)

    # C：错误即数据——节点内兜底，条件边走降级分支
    def resilient(state: JobState) -> dict:
        try:
            raise TimeoutError("下游 3 秒未响应")
        except Exception as e:                     # 生产：只捕获预期异常类型
            return {"errors": [f"resilient 捕获 {type(e).__name__}: {e}"], "result": ""}

    def fallback(state: JobState) -> dict:
        return {"result": "降级：返回缓存的上次结果"}

    g3 = StateGraph(JobState)
    g3.add_node("resilient", resilient)
    g3.add_node("fallback", fallback)
    g3.add_edge(START, "resilient")
    g3.add_conditional_edges(
        "resilient",
        lambda s: "fallback" if s["errors"] else END,
        {"fallback": "fallback", END: END},
    )
    g3.add_edge("fallback", END)
    r3 = g3.compile().invoke({"result": "", "errors": []})
    print("C 错误即数据：errors =", r3["errors"], "| result =", r3["result"])


if __name__ == "__main__":
    main()
