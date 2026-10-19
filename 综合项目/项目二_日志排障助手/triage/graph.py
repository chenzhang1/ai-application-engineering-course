# 综合项目/项目二_日志排障助手/triage/graph.py
"""组图与运行入口。

拓扑（8 节点 + 1 条件边）：

    START → parse_logs → rule_prefilter → extract_evidence → query_tools
          → hypothesize → assess ─(条件)─→ conclude → END
                                    └─→ approval ─(interrupt/Command(resume))─→ conclude

- 线性主干保证确定性可复现；唯一分支是 assess 之后"要不要人工审批"；
- checkpointer 可选注入：InMemorySaver（进程内演示）/ SqliteSaver（跨进程恢复）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langgraph.graph import END, START, StateGraph

from triage.audit import AuditLog
from triage.config import TriageConfig
from triage.nodes import make_nodes
from triage.state import TriageState


def build_triage_graph(cfg: TriageConfig, audit: AuditLog,
                       checkpointer: Any | None = None):
    """编译排障图。checkpointer 传入即启用持久化/恢复能力。"""
    nodes = make_nodes(cfg, audit)
    g = StateGraph(TriageState)
    g.add_node("parse_logs", nodes["parse_logs"])
    g.add_node("rule_prefilter", nodes["rule_prefilter"])
    g.add_node("extract_evidence", nodes["extract_evidence"])
    g.add_node("query_tools", nodes["query_tools"])
    g.add_node("hypothesize", nodes["hypothesize"])
    g.add_node("assess", nodes["assess"])
    g.add_node("approval", nodes["approval"])
    g.add_node("conclude", nodes["conclude"])

    g.add_edge(START, "parse_logs")
    g.add_edge("parse_logs", "rule_prefilter")
    g.add_edge("rule_prefilter", "extract_evidence")
    g.add_edge("extract_evidence", "query_tools")
    g.add_edge("query_tools", "hypothesize")
    g.add_edge("hypothesize", "assess")
    g.add_conditional_edges("assess", nodes["route_after_assess"],
                            {"approval": "approval", "conclude": "conclude"})
    g.add_edge("approval", "conclude")
    g.add_edge("conclude", END)
    return g.compile(checkpointer=checkpointer)


def initial_state(incident_id: str, sources: list[str]) -> dict:
    """首次运行的输入：incident 元信息 + 空白看板。"""
    return {
        "incident": {"thread_id": incident_id, "sources": list(sources)},
        "records": [], "alerts": [], "queries": [], "evidence": [],
        "hypothesis": {}, "assessment": {}, "conclusion": {},
        "executed_actions": [],
    }


@dataclass
class TriageRun:
    """一次排障运行的句柄：含编译好的图与 thread 配置，供恢复使用。"""

    app: Any
    config: dict[str, Any]
    result: dict[str, Any]

    @property
    def interrupted(self) -> bool:
        return "__interrupt__" in self.result

    @property
    def conclusion(self) -> dict[str, Any]:
        return self.result.get("conclusion", {})


def run_triage(incident_id: str, sources: list[str], cfg: TriageConfig, audit: AuditLog,
               checkpointer: Any | None = None) -> TriageRun:
    """运行一次排障；若图在审批节点暂停，返回 interrupted=True 的 TriageRun。"""
    app = build_triage_graph(cfg, audit, checkpointer)
    graph_cfg = {"configurable": {"thread_id": incident_id}}
    result = app.invoke(initial_state(incident_id, sources), graph_cfg)
    return TriageRun(app=app, config=graph_cfg, result=result)


def resume_triage(run: TriageRun, decision: bool) -> TriageRun:
    """人工决策后恢复（Command(resume=...)）。decision=True 批准 / False 拒绝。"""
    from langgraph.types import Command

    result = run.app.invoke(Command(resume=decision), run.config)
    return TriageRun(app=run.app, config=run.config, result=result)
