# EX-47-03 | 时间旅行：从历史检查点重放/分叉 | 运行: python3 示例代码/ch47_persistence/ex_47_03_time_travel.py
"""完整可运行（○ 进阶选修）：get_state_history 拿到任意历史检查点，
把它的 checkpoint_id 塞回 config 即可"回到过去"再执行。

两种玩法（本例实测）：
  A. 重放：invoke(None, 历史config)——从该检查点按原路继续跑完；
  B. 分叉：invoke(新输入, 历史config)——从该检查点换一条路走，产生新分支，
     原 thread 的"现在"指向新分支（旧历史仍在，可再回退）。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402
from langgraph.graph import END, START, StateGraph  # noqa: E402


def merge_list(a: list[str] | None, b: list[str] | None) -> list[str]:
    return (a or []) + (b or [])


class FlowState(TypedDict):
    steps: Annotated[list[str], merge_list]


def step_one(s: FlowState) -> dict:
    return {"steps": ["step_one"]}


def step_two(s: FlowState) -> dict:
    return {"steps": ["step_two"]}


def main() -> None:
    g = StateGraph(FlowState)
    g.add_node("step_one", step_one)
    g.add_node("step_two", step_two)
    g.add_edge(START, "step_one"); g.add_edge("step_one", "step_two"); g.add_edge("step_two", END)
    app = g.compile(checkpointer=InMemorySaver())

    cfg = {"configurable": {"thread_id": "tt"}}
    app.invoke({"steps": []}, cfg)
    print("正常跑完：", app.get_state(cfg).values["steps"])

    hist = list(app.get_state_history(cfg))
    replay_point = next(h for h in hist if h.next == ("step_two",))  # step_one 之后
    old_cfg = {"configurable": {"thread_id": "tt",
                                "checkpoint_id": replay_point.config["configurable"]["checkpoint_id"]}}
    print("回退点：next =", replay_point.next, "（即将执行 step_two）")

    # A. 重放：不传新输入（None），从检查点按原路继续
    r1 = app.invoke(None, old_cfg)
    print("A 重放结果：", r1["steps"], "；回放后 get_state().next =", app.get_state(cfg).next)

    # B. 分叉：回同一检查点，换输入重跑（这里用 None 之外的新输入改写状态）
    r2 = app.invoke({"steps": ["手工修正"]}, old_cfg)
    print("B 分叉结果：", r2["steps"], "；thread 的'现在'已切到新分支：",
          app.get_state(cfg).values["steps"])

    print("检查点历史仍是完整的——时间旅行 = 在不可变检查点链上自由检出新分支。")


if __name__ == "__main__":
    main()
