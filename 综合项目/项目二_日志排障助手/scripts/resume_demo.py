# 综合项目/项目二_日志排障助手/scripts/resume_demo.py | 持久化与恢复演示 | 运行: python3 scripts/resume_demo.py
"""恢复语义端到端演示：中断 → 人工决策 → 恢复 → 状态一致 → 幂等不重复执行。

三个部分：
  A. 进程内恢复（InMemorySaver）：第一次 invoke 暂停在审批节点，Command(resume=False)
     拒绝 → 高风险动作不执行，结论照常产出；
  B. 跨进程恢复（SqliteSaver，需 langgraph-checkpoint-sqlite）："进程 1" 暂停后退出，
     "进程 2" 重新编译图、打开同一个 SQLite 检查点库 → get_state 看到暂停点 →
     Command(resume=True) 批准 → 副作用执行一次；
  C. 幂等验证：从暂停检查点再次重放恢复 → 账本命中，副作用不重复。

真实进程重启的恢复方式（README 展开）：检查点库放到进程外（SQLite 文件/Postgres），
新进程用同样的图定义 + checkpointer + thread_id 启动，先 get_state 判断是否停在
interrupt，再由人工平台把决策以 Command(resume=...) 提交。
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # 综合项目/项目二_日志排障助手
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent.parent))          # 仓库根

from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402

from triage.audit import AuditLog                    # noqa: E402
from triage.config import TriageConfig               # noqa: E402
from triage.graph import (                           # noqa: E402
    TriageRun,
    build_triage_graph,
    resume_triage,
    run_triage,
)
from triage.synth_data import build_all              # noqa: E402
from triage.tools_readonly import ActionLedger       # noqa: E402

SOURCES = ["order_service.log", "gateway_service.log", "db_task_runner.log"]


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="p2_resume_demo_"))
    build_all(tmp)                                    # 数据目录独立，不污染教材 data/
    cfg = TriageConfig(data_dir=tmp, audit_path=tmp / "audit.jsonl",
                       ledger_path=tmp / "ledger.jsonl")
    cfg.ensure_dirs()

    print("═══ A. 进程内恢复（InMemorySaver）：拒绝高风险动作 ═══")
    audit = AuditLog(cfg.audit_path, operator="duty-engineer")
    run = run_triage("demo-reject", SOURCES, cfg, audit, checkpointer=InMemorySaver())
    intr = run.result["__interrupt__"][0]
    print("⏸  暂停点 next =", run.app.get_state(run.config).next)
    print("    审批单：", json.dumps(intr.value, ensure_ascii=False)[:100], "…")
    run2 = resume_triage(run, False)                  # 人工拒绝
    c = run2.conclusion
    print("✅ 恢复后结论：", c["level"], "|", c["verdict"])
    print("   actions_taken =", [(a["action"], a["service"], a["status"])
                                 for a in c["actions_taken"]])
    print("   副作用账本行数 =", len(ActionLedger(cfg.ledger_path).read_all()),
          "（拒绝 → 不执行）")

    print("\n═══ B. 跨进程恢复（SqliteSaver）：新进程接续旧会话 ═══")
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
    except ImportError:
        print("（未安装 langgraph-checkpoint-sqlite，B/C 跳过——pip install "
              "langgraph-checkpoint-sqlite 后重跑，本书实测版本 3.1.2）")
        return
    db_file = tmp / "checkpoints.db"
    # ——"进程 1"：跑到 interrupt 就退出——
    with SqliteSaver.from_conn_string(str(db_file)) as saver1:
        audit1 = AuditLog(tmp / "audit_b1.jsonl")
        run1 = run_triage("demo-approve", SOURCES, cfg, audit1, checkpointer=saver1)
        assert run1.interrupted, "预期停在审批节点"
        print("进程 1 暂停在：", run1.app.get_state(run1.config).next, "（然后'进程退出'）")
    # ——"进程 2"：全新编译 + 同一个检查点库（真实恢复路径：不重放输入，直接 get_state）——
    with SqliteSaver.from_conn_string(str(db_file)) as saver2:
        audit2 = AuditLog(tmp / "audit_b2.jsonl")
        app = build_triage_graph(cfg, audit2, checkpointer=saver2)
        graph_cfg = {"configurable": {"thread_id": "demo-approve"}}
        snap = app.get_state(graph_cfg)
        print("进程 2 get_state：next =", snap.next, "| interrupts =",
              [i.value["question"] for i in snap.interrupts])
        from langgraph.types import Command

        paused = {"__interrupt__": [snap.interrupts[0]]}
        run3 = resume_triage(TriageRun(app=app, config=graph_cfg, result=paused), True)
        c = run3.conclusion
        print("✅ 恢复后结论：", c["level"], "|", c["verdict"])
        print("   actions_taken =", [(a["action"], a["service"], a["status"])
                                     for a in c["actions_taken"]])

        print("\n═══ C. 幂等验证：从暂停检查点重放恢复 ═══")
        cp = next(h for h in app.get_state_history(graph_cfg) if h.next == ("approval",))
        old = {"configurable": {"thread_id": "demo-approve",
                                "checkpoint_id": cp.config["configurable"]["checkpoint_id"]}}
        r = app.invoke(Command(resume=True), old)
        print("重放后 actions_taken 状态：",
              [(a["action_key"].split(":")[2], a["status"]) for a in r["executed_actions"]])
        ledger_rows = ActionLedger(cfg.ledger_path).read_all()
        executed_rows = [x for x in ledger_rows if x.get("status") == "executed"]
        print("副作用账本 executed 记录数 =", len(executed_rows),
              "（应仍为 1：账本命中 already_done，不重复重启）")

    print(f"\n演示数据目录（可检查审计 JSONL 与账本）：{tmp}")


if __name__ == "__main__":
    main()
