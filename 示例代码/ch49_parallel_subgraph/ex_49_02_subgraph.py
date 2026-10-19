# EX-49-02 | 子图封装与状态映射：大图拆小图 | 运行: python3 示例代码/ch49_parallel_subgraph/ex_49_02_subgraph.py
"""完整可运行：两种子图用法。

  用法 1（schema 对齐）：编译好的子图直接 add_node——父状态字段与子图输入/输出
   字段同名时，LangGraph 自动完成映射；
  用法 2（schema 不同）：写一个"映射节点"包住子图，显式做字段搬运（类似
   Java 里两个服务之间的 DTO 转换器）。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from langgraph.graph import END, START, StateGraph  # noqa: E402

# ── 子图：告警分析（自己的小状态） ──────────────────────────────────────────


class AlertState(TypedDict):
    alert: str
    cause: str


def analyze(state: AlertState) -> dict:
    return {"cause": f"{state['alert']} 的根因是连接池耗尽"}


def build_subgraph():
    sg = StateGraph(AlertState)
    sg.add_node("analyze", analyze)
    sg.add_edge(START, "analyze"); sg.add_edge("analyze", END)
    return sg.compile()


# ── 用法 1：父状态直接包含子图全部字段 ─────────────────────────────────────


class ParentDirect(TypedDict):
    alert: str
    cause: str          # 与子图同名 → 自动映射
    trace: Annotated[list[str], lambda a, b: (a or []) + (b or [])]


def direct_wrap(state: ParentDirect) -> dict:
    return {"trace": ["direct:进入子图"]}   # 子图本身作为节点由框架调用


def report_direct(state: ParentDirect) -> dict:
    return {"trace": [f"direct-report:{state['cause']}"]}


# ── 用法 2：父状态字段名不同 → 显式映射节点 ────────────────────────────────


class ParentMapped(TypedDict):
    incident: str                    # 父图叫 incident
    cause: str
    trace: Annotated[list[str], lambda a, b: (a or []) + (b or [])]


def mapped_bridge(state: ParentMapped) -> dict:
    """映射节点：父字段 → 子图输入；子图输出 → 父字段（DTO 转换器）。"""
    sub_out: AlertState = build_subgraph().invoke({"alert": state["incident"], "cause": ""})
    return {"cause": sub_out["cause"], "trace": ["mapped:子图结果已搬运"]}


def report_mapped(state: ParentMapped) -> dict:
    return {"trace": [f"mapped-report:{state['cause']}"]}


def main() -> None:
    # 用法 1：子图直接当节点
    g1 = StateGraph(ParentDirect)
    g1.add_node("sub_alert", build_subgraph())   # 编译图也是节点
    g1.add_node("report", report_direct)
    g1.add_edge(START, "sub_alert"); g1.add_edge("sub_alert", "report"); g1.add_edge("report", END)
    r1 = g1.compile().invoke({"alert": "ALERT-7", "cause": "", "trace": []})
    print("用法 1（schema 对齐）：", r1["trace"])

    # 用法 2：显式映射
    g2 = StateGraph(ParentMapped)
    g2.add_node("bridge", mapped_bridge)
    g2.add_node("report", report_mapped)
    g2.add_edge(START, "bridge"); g2.add_edge("bridge", "report"); g2.add_edge("report", END)
    r2 = g2.compile().invoke({"incident": "INC-9", "cause": "", "trace": []})
    print("用法 2（显式映射）：", r2["trace"])


if __name__ == "__main__":
    main()
