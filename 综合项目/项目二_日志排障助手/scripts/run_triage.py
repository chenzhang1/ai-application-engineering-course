# 综合项目/项目二_日志排障助手/scripts/run_triage.py | CLI 入口 | 运行: python3 scripts/run_triage.py --help
"""排障助手命令行。

常用命令（在 综合项目/项目二_日志排障助手 目录下执行）：
  python3 scripts/run_triage.py --scenario payment-outage
  python3 scripts/run_triage.py --scenario payment-outage --auto-approve   # 自动批准高风险动作（演示用）
  python3 scripts/run_triage.py --scenario clean                           # 无告警样本 → 证据不足拒答

退出码：0 正常出结论；2 图在审批处暂停（未加 --auto-approve 时）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # 综合项目/项目二_日志排障助手
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent.parent))          # 仓库根

from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402

from triage.audit import AuditLog                    # noqa: E402
from triage.config import TriageConfig               # noqa: E402
from triage.graph import resume_triage, run_triage   # noqa: E402
from triage.synth_data import build_all              # noqa: E402

SCENARIOS: dict[str, list[str]] = {
    # 全量日志：超时 + 连接失败 + 数据异常 → P1 + 高风险动作（重启 payment-service）
    "payment-outage": ["order_service.log", "gateway_service.log", "db_task_runner.log"],
    # 只有网关日志：能确认 connection_refused，但数据库佐证依赖完整 → 也可下结论（P2/P1 视条数）
    "gateway-only": ["gateway_service.log"],
    # 只有空日志：无告警 → 证据不足拒答
    "clean": ["empty.log"],
}


def main() -> None:
    parser = argparse.ArgumentParser(description="P2 生产日志排障助手（LangGraph）")
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), default="payment-outage")
    parser.add_argument("--incident-id", default=None, help="thread_id，默认 incident-<scenario>")
    parser.add_argument("--auto-approve", action="store_true",
                        help="遇到高风险动作自动批准（模拟人工点'同意'；生产不得自动批准）")
    parser.add_argument("--rebuild-data", action="store_true", help="先重建合成数据")
    args = parser.parse_args()

    cfg = TriageConfig()
    cfg.ensure_dirs()
    if args.rebuild_data or not (cfg.data_dir / "ops_inventory.sqlite").exists():
        build_all(cfg.data_dir)
    if args.scenario == "clean":
        from triage.synth_data import build_empty_log
        build_empty_log(cfg.data_dir)

    audit = AuditLog(cfg.audit_path, operator=cfg.operator)
    incident_id = args.incident_id or f"incident-{args.scenario}"
    # 审批/恢复要求同一进程内持有检查点（跨进程恢复见 resume_demo.py 的 SqliteSaver 部分）
    run = run_triage(incident_id, SCENARIOS[args.scenario], cfg, audit,
                     checkpointer=InMemorySaver())

    if run.interrupted:
        intr = run.result["__interrupt__"][0]
        print("⏸  图在人工审批节点暂停。审批单：")
        print(json.dumps(intr.value, ensure_ascii=False, indent=2))
        if not args.auto_approve:
            print("（重新运行时加 --auto-approve 可模拟人工批准；或用 resume_demo.py 看恢复全过程）")
            sys.exit(2)
        print("→ 模拟人工批准（--auto-approve），Command(resume=True) 恢复……")
        run = resume_triage(run, True)

    print(json.dumps(run.conclusion, ensure_ascii=False, indent=2))
    print(f"\n审计日志：{cfg.audit_path}（本次共 {len(audit.read_all())} 条事件）")


if __name__ == "__main__":
    main()
