# 综合项目/项目二_日志排障助手/triage/state.py
"""图状态定义：所有节点共享的"工单看板"。

Java 对照：相当于一次排障流程实例的聚合根——字段就是流程变量，
Annotated reducer 定义并发写合并规则（类似多分支写同一流程变量时的归并器）。
"""
from __future__ import annotations

from typing import Annotated, Any, TypedDict


def merge_lists(left: list | None, right: list | None) -> list:
    """通用列表 reducer：并行/多轮写入时追加合并（顺序=写入顺序）。"""
    return (left or []) + (right or [])


class TriageState(TypedDict):
    """排障状态。

    records         解析后的日志记录 [{ts, level, service, trace_id, message}]
    alerts          规则预筛结果 [{type, service, dependency, count, samples}]
    queries         工具调用记录 [{tool, args, status, summary}]（与审计日志同源）
    evidence        证据条目 [{kind, ...}]（工具返回的结构化事实）
    hypothesis      模型节点输出 {primary_service, suspected_dependency, failure_mode, confidence}
    assessment      评估 {alerts, strength, corroborations, gaps, can_conclude,
                         suggested_actions, high_risk_actions}
    conclusion      最终结论 {level, verdict, message, gaps, suggested_actions,
                         actions_taken}
    executed_actions 副作用台账 [{action_key, action, service, status, detail}]
    """

    incident: dict[str, Any]
    records: Annotated[list[dict[str, Any]], merge_lists]
    alerts: Annotated[list[dict[str, Any]], merge_lists]
    queries: Annotated[list[dict[str, Any]], merge_lists]
    evidence: Annotated[list[dict[str, Any]], merge_lists]
    hypothesis: dict[str, Any]
    assessment: dict[str, Any]
    conclusion: dict[str, Any]
    executed_actions: Annotated[list[dict[str, Any]], merge_lists]
