# projects/p2_log_triage/triage/nodes.py
"""图节点：解析 → 规则预筛 → 证据提取 → 受限只读查询 → 假设生成（LLM）→
证据强度评估 → 人工审批（高风险）→ 结论分级输出。

设计约定：
  - 节点工厂 make_nodes(cfg, audit) 用闭包注入配置与审计器（依赖注入，
    见 ch51 测试模式），可序列化的只有 TriageState 本身——checkpointer 才安全；
  - Mock 约定（全书统一）：模型节点 hypothesize 用
    examples.common.llm_client.get_llm()（LLM_MODE=mock 默认，从证据 key=value
    解析结构化字段，同输入同输出）；LLM_MODE=real 时同一 schema 由真实模型
    判断，控制流不变；
  - approval 节点遵守 ch48 幂等纪律：interrupt() 之前只读，副作用全在恢复后
    且过幂等账本。
"""
from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

from pydantic import BaseModel, Field

from triage.audit import AuditLog
from triage.config import TriageConfig
from triage.tools_readonly import (
    QUERY_DEPENDENCY,
    QUERY_ERROR_RECORDS,
    QUERY_SERVICE_STATUS,
    RESTART_SERVICE,
    ActionLedger,
    ToolWhitelistError,
    query_dependency,
    query_error_records,
    query_service_status,
    restart_service,
    validate_args,
)

# 日志行格式：2026-10-19 09:02:10.512|ERROR|order-service|trace-5002|message
_LINE_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})\|(TRACE|DEBUG|INFO|WARN|ERROR)\|"
    r"([a-z][a-z0-9-]*)\|(trace-[A-Za-z0-9-]+)\|(.*)$"
)
_TIMEOUT_RE = re.compile(r"Call to ([a-z][a-z0-9-]*) timed out", re.IGNORECASE)
_CONNREFUSED_RE = re.compile(r"Connect(?:ion)? to ([a-z][a-z0-9-]*) (?:failed|refused)", re.IGNORECASE)
_ANOMALY_RE = re.compile(r"Data anomaly: (.+)", re.IGNORECASE)


# ---------------------------------------------------------------------------
# 节点工厂：闭包持有 cfg / audit（依赖注入，便于测试替换）
# ---------------------------------------------------------------------------


def make_nodes(cfg: TriageConfig, audit: AuditLog) -> dict[str, Any]:
    """返回 {节点名: 可调用}。所有节点签名统一 (state: dict) -> dict（部分更新）。"""

    # ---------------- 1. 日志解析 ----------------
    def parse_logs(state: dict) -> dict:
        """读取 incident.sources 指定的日志文件，解析成结构化记录。

        非法行跳过（真实解析器应记 metrics）；文件缺失记为 alert 而非崩溃。
        """
        records: list[dict[str, Any]] = []
        missing: list[dict[str, Any]] = []
        for name in state["incident"]["sources"]:
            path = cfg.data_dir / name
            if not path.exists():
                missing.append({"type": "missing_source", "service": "n/a",
                                "dependency": "", "count": 1, "samples": [name]})
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                m = _LINE_RE.match(line.strip())
                if not m:
                    continue
                records.append({"ts": m.group(1), "level": m.group(2), "service": m.group(3),
                                "trace_id": m.group(4), "message": m.group(5),
                                "source": name})
        return {"records": records, "alerts": missing}

    # ---------------- 2. 规则预筛 ----------------
    def rule_prefilter(state: dict) -> dict:
        """把日志记录归类为三类告警：超时 / 连接失败 / 数据异常；正常样本不产告警。"""
        buckets: dict[tuple[str, str, str], dict[str, Any]] = {}

        def add(kind: str, service: str, dependency: str, rec: dict[str, Any]) -> None:
            key = (kind, service, dependency)
            b = buckets.setdefault(key, {"type": kind, "service": service,
                                         "dependency": dependency, "count": 0, "samples": []})
            b["count"] += 1
            if len(b["samples"]) < 3:
                b["samples"].append(f"{rec['ts']} {rec['trace_id']} {rec['message'][:60]}")

        for rec in state["records"]:
            msg = rec["message"]
            if m := _TIMEOUT_RE.search(msg):
                add("timeout", rec["service"], m.group(1), rec)
            elif m := _CONNREFUSED_RE.search(msg):
                add("connection_refused", rec["service"], m.group(1), rec)
            elif _ANOMALY_RE.search(msg):
                add("data_anomaly", rec["service"], "", rec)
            # INFO/WARN 普通行：不产告警（预筛只挑"值得取证"的样本）

        alerts = sorted(buckets.values(), key=lambda b: -b["count"])
        return {"alerts": alerts}

    # ---------------- 3. 证据提取（查询计划） ----------------
    def extract_evidence(state: dict) -> dict:
        """根据告警生成"取证计划"：只允许白名单工具 + 白名单参数。

        刻意把"想查什么"（计划）与"真的去查"（query_tools）拆成两个节点——
        计划可审查、可回放，也是把模型引入前的天然审计点。
        """
        plan: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        def add(tool: str, args: dict[str, Any]) -> None:
            key = (tool, json.dumps(args, sort_keys=True, ensure_ascii=False))
            if key not in seen:
                seen.add(key)
                plan.append({"tool": tool, "args": args})

        for alert in state["alerts"]:
            if alert["type"] == "missing_source":
                continue
            dep = alert.get("dependency") or ""
            if alert["type"] in ("timeout", "connection_refused") and dep:
                add(QUERY_ERROR_RECORDS, {"service": dep, "level": "ERROR", "limit": 10})
                add(QUERY_SERVICE_STATUS, {"service": dep})
                add(QUERY_DEPENDENCY, {"service": dep})
            if alert["type"] == "data_anomaly":
                add(QUERY_ERROR_RECORDS, {"service": alert["service"], "level": "ERROR", "limit": 10})
                add(QUERY_SERVICE_STATUS, {"service": alert["service"]})
        return {"queries": [{"tool": p["tool"], "args": p["args"], "status": "planned",
                             "summary": ""} for p in plan],
                "evidence": [{"kind": "query_plan", "plan": plan}]}

    # ---------------- 4. 受限只读工具查询 ----------------
    def query_tools(state: dict) -> dict:
        """执行取证计划：白名单校验 → 只读执行 → 审计留痕 → 证据归一。"""
        thread_id = state["incident"]["thread_id"]
        evidence: list[dict[str, Any]] = []
        queries: list[dict[str, Any]] = []

        for q in state["queries"]:
            if q["status"] != "planned":
                continue
            tool, args = q["tool"], q["args"]
            try:
                args = validate_args(tool, args)      # 白名单：工具名+参数名+参数值
            except ToolWhitelistError as e:
                audit.append("tool_rejected", thread_id=thread_id,
                             args={"tool": tool, "args": q["args"]},
                             result_summary=str(e), status="rejected")
                queries.append({**q, "status": "rejected", "summary": str(e)})
                evidence.append({"kind": "tool_rejected", "tool": tool, "reason": str(e)})
                continue

            try:
                if tool == QUERY_ERROR_RECORDS:
                    rows = query_error_records(cfg.data_dir / "ops_inventory.sqlite",
                                               service=args["service"],
                                               level=args.get("level", "ERROR"),
                                               limit=args.get("limit", 10))
                    summary = f"{len(rows)} 条错误事件（{args['service']}）"
                    evidence.append({"kind": "error_events", "service": args["service"],
                                     "count": len(rows),
                                     "top": [r["message"][:60] for r in rows[:3]]})
                elif tool == QUERY_SERVICE_STATUS:
                    status = query_service_status(cfg.data_dir / "service_status.json",
                                                  service=args["service"])
                    summary = f"{args['service']} 状态={status.get('status')}"
                    evidence.append({"kind": "service_status", "service": args["service"],
                                     "status": status.get("status", "unknown"),
                                     "error_rate": status.get("error_rate"),
                                     "pod_restarts": status.get("pod_restarts")})
                elif tool == QUERY_DEPENDENCY:
                    deps = query_dependency(cfg.data_dir / "ops_inventory.sqlite",
                                            service=args["service"])
                    summary = f"{len(deps)} 条依赖关系（{args['service']}）"
                    evidence.append({"kind": "dependency_map", "service": args["service"],
                                     "relations": deps})
                else:  # 防御分支：白名单已挡住，理论不可达
                    raise ToolWhitelistError(f"执行器未实现工具 {tool}")
                result, status_out = "ok", "ok"
            except (sqlite3.OperationalError, FileNotFoundError, json.JSONDecodeError) as e:
                result, status_out = f"数据源读取失败：{e}", "error"
                evidence.append({"kind": "tool_error", "tool": tool, "reason": str(e)})

            audit.append(tool, thread_id=thread_id, args={"tool": tool, **args},
                         result_summary=summary, status=status_out)
            queries.append({**q, "status": status_out,
                            "summary": summary if status_out == "ok" else result})

        return {"queries": queries, "evidence": evidence}

    # ---------------- 5. 假设生成（模型节点，Mock 驱动） ----------------
    class Hypothesis(BaseModel):
        """根因假设 schema：真实模型由证据推断，Mock 从证据 key=value 解析。"""

        primary_service: str = Field(default="unknown", description="首发故障服务")
        suspected_dependency: str = Field(default="unknown", description="疑似根因依赖")
        failure_mode: str = Field(default="unknown",
                                  description="timeout/connection_refused/data_anomaly/none")
        confidence: float = Field(default=0.0, description="0~1 置信度")

    def hypothesize(state: dict) -> dict:
        """模型节点：证据摘要 → 结构化假设（get_llm()，LLM_MODE 默认 mock）。"""
        from examples.common.llm_client import get_llm  # 全书统一基座

        alerts = [a for a in state["alerts"] if a["type"] != "missing_source"]
        if not alerts:
            return {"hypothesis": {"primary_service": "unknown",
                                   "suspected_dependency": "unknown",
                                   "failure_mode": "none", "confidence": 0.0}}

        top = max(alerts, key=lambda a: a["count"])
        # 证据事实行：Mock 模式从 key=value 解析（ch24/ch45 同款约定）；
        # 真实模式下模型读上文证据自行填写同一 schema。
        facts = (f"primary_service={top['service']} "
                 f"suspected_dependency={top['dependency'] or 'none'} "
                 f"failure_mode={top['type']}")
        messages = [
            {"role": "system",
             "content": "你是后端排障假设生成器。基于证据摘要输出结构化假设，"
                        "只使用证据里出现过的服务名，不得编造。"},
            {"role": "user",
             "content": f"证据摘要：{json.dumps(alerts, ensure_ascii=False)[:400]}\n"
                        f"证据事实：{facts}\n"
                        "请给出 primary_service / suspected_dependency / "
                        "failure_mode / confidence。"},
        ]
        h: Hypothesis = get_llm().chat_structured(messages, Hypothesis)
        dump = h.model_dump()
        if dump["suspected_dependency"] == "none":   # 数据异常类没有依赖方
            dump["suspected_dependency"] = dump["primary_service"]
        # Mock 无法产生真实置信度：用确定性的样本量启发式代替（0.5 + 每条告警 +0.1，上限 0.9）；
        # 真实模式下由模型输出。这里绝不假装它是模型判断——见 README 的 Mock 边界说明。
        dump["confidence"] = round(min(0.9, 0.5 + 0.1 * min(top["count"], 4)), 2)
        return {"hypothesis": dump}

    # ---------------- 6. 证据强度评估 ----------------
    def assess(state: dict) -> dict:
        """假设与工具证据互相印证打分，输出缺口清单与行动清单（建议 vs 高风险）。"""
        alerts = [a for a in state["alerts"] if a["type"] != "missing_source"]
        h = state["hypothesis"]
        dep = h.get("suspected_dependency", "unknown")
        corroborations: list[str] = []
        gaps: list[str] = []

        ev_status = next((e for e in state["evidence"]
                          if e["kind"] == "service_status" and e["service"] == dep), None)
        ev_errors = next((e for e in state["evidence"]
                          if e["kind"] == "error_events" and e["service"] == dep), None)
        ev_map = next((e for e in state["evidence"]
                       if e["kind"] == "dependency_map"
                       and any(r["direction"] == "upstream"
                               and r["service"] == h.get("primary_service")
                               for r in e["relations"])), None)

        if ev_status and ev_status["status"] in ("down", "degraded"):
            corroborations.append(f"{dep} 状态={ev_status['status']}")
        if ev_errors and ev_errors["count"] >= 2:
            corroborations.append(f"{dep} 有 {ev_errors['count']} 条 ERROR 事件")
        if ev_map:
            corroborations.append(f"{h.get('primary_service')} 依赖 {dep}（依赖表可查）")

        if not alerts:
            gaps.append("日志样本未发现超时/连接失败/数据异常，无告警可取证")
        if ev_status is None and dep != "unknown":
            gaps.append(f"缺少 {dep} 的服务状态快照证据")
        if ev_status is not None and ev_status["status"] == "unknown" and dep != "unknown":
            gaps.append(f"{dep} 不在服务状态快照中，无法确认其健康度")
        if ev_errors is None and dep != "unknown":
            gaps.append(f"数据库中缺少 {dep} 的错误事件佐证")
        if ev_map is None and dep != "unknown":
            gaps.append(f"依赖表中查不到 {h.get('primary_service')} → {dep} 的依赖记录")

        strength = len(corroborations)
        can_conclude = bool(alerts) and strength >= 2

        # 行动清单：文字建议（低风险） vs 高风险动作（须人工审批）
        suggested_actions: list[str] = []
        high_risk_actions: list[dict[str, Any]] = []
        if ev_status and ev_status["status"] in ("down", "degraded"):
            suggested_actions.append(f"联系 {dep} 负责人确认服务状态（只读沟通，低风险）")
            high_risk_actions.append({"action": RESTART_SERVICE, "service": dep,
                                      "reason": f"{dep} 状态={ev_status['status']}，"
                                                f"重启属高风险变更"})
        if alerts and alerts[0]["type"] == "data_anomaly" and can_conclude:
            suggested_actions.append("核对数据写入链路的校验逻辑，隔离脏数据（文字建议）")

        return {"assessment": {
            "alert_total": sum(a["count"] for a in alerts),
            "strength": strength,
            "corroborations": corroborations,
            "gaps": gaps,
            "can_conclude": can_conclude,
            "suggested_actions": suggested_actions,
            "high_risk_actions": high_risk_actions,
        }}

    def route_after_assess(state: dict) -> str:
        """条件路由：能下结论且有高风险动作 → 审批节点；否则直接出结论。"""
        a = state["assessment"]
        return "approval" if (a["can_conclude"] and a["high_risk_actions"]) else "conclude"

    # ---------------- 7. 人工审批（interrupt / Command(resume)） ----------------
    def approval(state: dict) -> dict:
        """人工审批节点（ch48 恢复语义的工程化落地）。

        resume 时本节点从头重跑——interrupt() 之前只读（拼审批单），
        副作用全部放在恢复之后，且经幂等账本（ActionLedger）兜底。
        """
        from langgraph.types import interrupt

        thread_id = state["incident"]["thread_id"]
        ledger = ActionLedger(cfg.ledger_path)
        actions = state["assessment"]["high_risk_actions"]
        ticket = [{"action": a["action"], "service": a["service"], "reason": a["reason"]}
                  for a in actions]                     # ← 只读

        decision: bool = bool(interrupt({"question": "是否批准以下高风险动作？",
                                         "tickets": ticket}))

        # —— 恢复之后：副作用（账本幂等 + 审计）——
        executed: list[dict[str, Any]] = []
        for a in actions:
            action_key = f"{a['action']}:{a['service']}:{thread_id}"
            try:
                validate_args(a["action"], {"service": a["service"]})
            except ToolWhitelistError as e:
                audit.append("approval.blocked", thread_id=thread_id,
                             args={"action_key": action_key},
                             result_summary=str(e), status="rejected")
                executed.append({"action_key": action_key, "action": a["action"],
                                 "service": a["service"], "status": "blocked",
                                 "detail": str(e)})
                continue
            result = restart_service(service=a["service"], action_key=action_key,
                                     ledger=ledger, approved=decision)
            executed.append({"action_key": action_key, **result})
            audit.append(f"approval.{a['action']}", thread_id=thread_id,
                         args={"action_key": action_key, "decision": decision},
                         result_summary=f"决策={decision} 执行结果={result['status']}",
                         status="executed" if result["status"] == "executed" else "not_executed")
        return {"executed_actions": executed}

    # ---------------- 8. 结论分级输出 ----------------
    def conclude(state: dict) -> dict:
        """最终结论：分级 P1/P2/UNKNOWN；证据不足必须明确拒答并列缺口。"""
        a = state["assessment"]
        h = state["hypothesis"]
        taken = state.get("executed_actions") or []
        gaps = list(a["gaps"])

        if not a["can_conclude"]:
            conclusion = {
                "level": "UNKNOWN",
                "verdict": "证据不足，无法下结论",
                "message": "现有日志与只读证据不足以支撑根因判断，请按缺口补充取证后重试。",
                "hypothesis": h,
                "corroborations": a["corroborations"],
                "gaps": gaps,
                "suggested_actions": a["suggested_actions"] or ["按缺口清单补充取证（见 gaps）"],
                "actions_taken": taken,
            }
        else:
            level = "P1" if a["alert_total"] >= 3 else "P2"
            conclusion = {
                "level": level,
                "verdict": f"{h['primary_service']} 受 {h['suspected_dependency']} "
                           f"故障影响（{h['failure_mode']}）",
                "message": (f"共 {a['alert_total']} 条告警；印证："
                            f"{'；'.join(a['corroborations'])}。"
                            f"置信度 {h.get('confidence', 0):.2f}。"),
                "hypothesis": h,
                "corroborations": a["corroborations"],
                "gaps": gaps,
                "suggested_actions": a["suggested_actions"],
                "actions_taken": taken,
            }
        return {"conclusion": conclusion}

    return {
        "parse_logs": parse_logs,
        "rule_prefilter": rule_prefilter,
        "extract_evidence": extract_evidence,
        "query_tools": query_tools,
        "hypothesize": hypothesize,
        "assess": assess,
        "route_after_assess": route_after_assess,
        "approval": approval,
        "conclude": conclude,
    }
