# EX-54-03 | 审计日志：每一次工具调用都要能回答"谁、何时、用什么参数、做了什么、结果如何"
# 运行: python3 示例代码/ch54_tool_governance/ex_54_03_audit_log.py
"""完整可运行（纯标准库 + tmpfile，无模型调用，确定性）：

ch52 的 EventTracer 解决"看得见"（控制台事件流）；本例把同一套事件模型
**落盘成 JSONL**，解决"查得回"（事后追责/合规/复盘）。一条审计记录五个 W：
    who（actor+role）/ when（ts, ISO8601）/ what（tool+args 摘要）/
    outcome（ok/denied/error + 结果摘要）/ context（trace_id 串起一次会话）。

三条工程纪律：
    1. 审计写在"统一执行入口"（EX-54-02 的 execute_tool）里，不散落在各工具内；
    2. 被拒绝的调用也要留痕（denied 是最有价值的审计事件）；
    3. JSONL 追加写 + 每行独立 JSON（ch54 与项目二/p3 共用此形状，方便 grep/jq）。
Java 对照：≈ 访问日志 + 审计切面（Logback MDC 放 trace_id）——Python 侧
用 logging + 自定义 handler 或直接 append JSONL，本项目选后者（依赖少、可流式入库）。
"""
from __future__ import annotations

import json
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any


class AuditLog:
    """JSONL 追加式审计日志（线程安全说明：本项目单写者；多进程部署走采集管道）。"""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, *, trace_id: str, actor: str, role: str, tool: str,
               args: dict[str, Any], outcome: str, detail: str = "",
               duration_ms: float = 0.0) -> dict[str, Any]:
        """写一条审计记录并返回（outcome ∈ ok / denied / validation_error / error）。"""
        rec = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()) + f".{int(time.time() * 1000) % 1000:03d}",
            "trace_id": trace_id,
            "actor": actor,
            "role": role,
            "tool": tool,
            "args": args,
            "outcome": outcome,
            "detail": detail[:200],
            "duration_ms": round(duration_ms, 1),
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec

    def by_trace(self, trace_id: str) -> list[dict[str, Any]]:
        """按 trace_id 检索一次会话的完整轨迹（合规调查的最小查询）。"""
        if not self.path.exists():
            return []
        return [json.loads(line) for line in
                self.path.read_text(encoding="utf-8").splitlines()
                if json.loads(line).get("trace_id") == trace_id]


def governed_execute(audit: AuditLog, trace_id: str, actor: str, role: str,
                     tool: str, args: dict[str, Any], *, allowed: bool,
                     plan_qty: int = 1000) -> dict[str, Any]:
    """统一执行入口的审计接线（EX-54-02 的 execute_tool 简化版 + 审计切面）。"""
    t0 = time.monotonic()
    if not allowed:
        audit.record(trace_id=trace_id, actor=actor, role=role, tool=tool, args=args,
                     outcome="denied", detail=f"角色 {role} 无权调用 {tool}",
                     duration_ms=(time.monotonic() - t0) * 1000)
        return {"ok": False, "outcome": "denied"}
    time.sleep(0.005)  # 模拟工具执行耗时（查询/写库）
    if tool == "query_plan":
        result, outcome = {"plan_id": args.get("plan_id"), "status": "延期"}, "ok"
    else:
        result, outcome = {"submitted": True, "plan_id": args.get("plan_id")}, "ok"
    audit.record(trace_id=trace_id, actor=actor, role=role, tool=tool, args=args,
                 outcome=outcome, detail=json.dumps(result, ensure_ascii=False),
                 duration_ms=(time.monotonic() - t0) * 1000)
    return {"ok": True, "outcome": outcome, "result": result}


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        audit = AuditLog(Path(td) / "audit" / "tools.jsonl")
        trace = f"trace-{uuid.uuid4().hex[:8]}"

        print(f"== 一次会话的审计轨迹（trace_id={trace}）==")
        governed_execute(audit, trace, "agent-p3", "operator", "query_plan",
                         {"plan_id": "P-1002"}, allowed=True)
        governed_execute(audit, trace, "agent-p3", "viewer", "submit_adjustment",
                         {"plan_id": "P-1002", "new_qty": 1200}, allowed=False)
        governed_execute(audit, trace, "agent-p3", "operator", "submit_adjustment",
                         {"plan_id": "P-1002", "new_qty": 1150, "reason": "客户加急订单5%内"},
                         allowed=True)

        records = audit.by_trace(trace)
        print(f"\n共 {len(records)} 条记录（含被拒绝的调用——denied 也必须留痕）：")
        for r in records:
            print(f"  {r['ts']} {r['actor']:<10} {r['role']:<8} {r['tool']:<18} "
                  f"{r['outcome']:<16} {r['duration_ms']:>5}ms  {r['detail'][:40]}")

        denied = [r for r in records if r["outcome"] == "denied"]
        print(f"\n合规三问（都能从 JSONL 回答）：")
        print(f"  ① 有没有人试过越权？→ {len(denied)} 次 denied（viewer 提交调整）")
        print(f"  ② 提交调整用的什么参数？→ {records[-1]['args']}")
        print(f"  ③ 这次会话按时间线是什么？→ {len(records)} 条按 ts 排序即完整时间线")
        print("\n治理闭环：EX-52-02 事件流（看得见）→ 本例 JSONL（查得回）→ "
              "ch60 可观测（聚合告警）——同一套事件字段贯穿。")


if __name__ == "__main__":
    main()
