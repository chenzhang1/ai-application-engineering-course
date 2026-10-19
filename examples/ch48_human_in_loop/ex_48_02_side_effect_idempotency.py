# EX-48-02 | 副作用幂等性：恢复时代码会从节点头重跑 | 运行: python3 examples/ch48_human_in_loop/ex_48_02_side_effect_idempotency.py
"""完整可运行：用执行计数器实证"恢复 = 节点从头重跑"，并给出两条防线。

实验 A（错误示范）：把副作用写在 interrupt() 之前 → 恢复时副作用执行 2 次。
实验 B（正确示范）：interrupt() 放最前 + 外部幂等账本（按 action_key 去重）→ 副作用恰好 1 次。
外部账本模拟真实系统的数据库唯一键/审计表——检查点本身不保证"恰好一次"，
跨系统的副作用必须自己做幂等（对应 Java 幂等消费：唯一业务键 + 去重表）。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402
from langgraph.graph import END, START, StateGraph  # noqa: E402
from langgraph.types import Command, interrupt  # noqa: E402


class WorkState(TypedDict):
    action_id: str
    done: bool
    trace: Annotated[list[str], lambda a, b: (a or []) + (b or [])]


def build_graph_wrong(log: list[str]):
    """A：副作用在 interrupt 之前——恢复时会被再执行一次。"""

    def node(s: WorkState) -> dict:
        log.append(f"副作用:{s['action_id']}")            # ← 危险：在暂停点之前
        decision = interrupt("等待审批")
        return {"done": bool(decision), "trace": [f"decision={decision}"]}

    g = StateGraph(WorkState)
    g.add_node("node", node)
    g.add_edge(START, "node"); g.add_edge("node", END)
    return g.compile(checkpointer=InMemorySaver())


def build_graph_right(log: list[str]):
    """B：interrupt 放最前 + 外部幂等账本。"""
    ledger: set[str] = set()   # 模拟数据库去重表（真实系统：唯一索引 + 插入失败即已存在）

    def node(s: WorkState) -> dict:
        decision = interrupt("等待审批")                 # 1) 先暂停，零副作用
        key = s["action_id"]
        if key in ledger:                                # 2) 恢复重跑时命中账本 → 跳过
            return {"done": True, "trace": [f"idempotent-skip:{key}"]}
        ledger.add(key)
        log.append(f"副作用:{key}")                      # 3) 副作用只在首次恢复执行
        return {"done": True, "trace": [f"executed:{key}"]}

    g = StateGraph(WorkState)
    g.add_node("node", node)
    g.add_edge(START, "node"); g.add_edge("node", END)
    return g.compile(checkpointer=InMemorySaver())


def main() -> None:
    print("── 实验 A：副作用写在 interrupt 之前 ──")
    log_a: list[str] = []
    app_a = build_graph_wrong(log_a)
    cfg_a = {"configurable": {"thread_id": "A"}}
    r = app_a.invoke({"action_id": "send-sms-1", "done": False, "trace": []}, cfg_a)
    print("第一次 invoke：", r["__interrupt__"][0].value, "| 已执行副作用：", log_a)
    app_a.invoke(Command(resume=True), cfg_a)
    print("恢复之后　　：副作用执行了", len(log_a), "次 ← 通知/扣款发两遍的事故就这么来的")

    print("── 实验 B：interrupt 放最前 + 幂等账本 ──")
    log_b: list[str] = []
    app_b = build_graph_right(log_b)
    cfg_b = {"configurable": {"thread_id": "B"}}
    app_b.invoke({"action_id": "send-sms-2", "done": False, "trace": []}, cfg_b)
    app_b.invoke(Command(resume=True), cfg_b)
    print("第一次恢复　：副作用执行了", len(log_b), "次")

    # 极端情况：执行成功但进程在写检查点前崩了 → 运维从中断检查点重新恢复
    # （时间旅行：回到 next=('node',) 的那个检查点，再 resume 一次）
    interrupt_cp = next(h for h in app_b.get_state_history(cfg_b) if h.next == ("node",))
    old_cfg = {"configurable": {"thread_id": "B",
                                "checkpoint_id": interrupt_cp.config["configurable"]["checkpoint_id"]}}
    r = app_b.invoke(Command(resume=True), old_cfg)
    print("从中断点重放：副作用仍是", len(log_b), "次，新轨迹：",
          [t for t in r["trace"] if t.startswith("idempotent")],
          "← 节点重跑了，但账本命中，副作用没有重复")


if __name__ == "__main__":
    main()
