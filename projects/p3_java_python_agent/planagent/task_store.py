# projects/p3_java_python_agent/planagent/task_store.py
"""异步任务状态机：POST /analysis 提交 → 后台跑 Agent → 轮询 → 审批/取消。

状态机（与教材 56.4 的图一致）：
    pending → running → succeeded | failed | waiting_approval | cancelled
    waiting_approval → succeeded（approve/reject 恢复后）| cancelled（撤销审批）
终态不可再取消/审批（对应 HTTP 409 Conflict）。

取消是协作式的：running 中置 cancel_event，工具入口在下一个检查点抛
TaskCancelled → 任务转 cancelled。这是"取消请求受理（202）≠ 立即停止"的教学实现。
"""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver

from planagent.agent_core import resume_analysis, run_analysis
from planagent.audit import AuditLog
from planagent.tools_layer import (
    JavaClient,
    Role,
    TaskCancelled,
    ToolContext,
)

TERMINAL = {"succeeded", "failed", "cancelled"}


class TaskNotFound(KeyError):
    pass


class TaskConflict(RuntimeError):
    """非法状态迁移（对终态取消/审批）→ HTTP 409。"""


@dataclass
class TaskRecord:
    task_id: str
    question: str
    status: str = "pending"
    created_at: str = ""
    result: dict[str, Any] | None = None
    approval_request: dict[str, Any] | None = None
    thread_id: str = ""

    def public(self) -> dict[str, Any]:
        return {"task_id": self.task_id, "question": self.question,
                "status": self.status, "created_at": self.created_at,
                "result": self.result, "approval_request": self.approval_request}


@dataclass
class TaskStore:
    """进程内任务表 + 后台执行器（生产替换：DB/Redis 任务表 + 任务队列 worker）。"""

    java_base_url: str
    audit_path: str
    checkpointer: InMemorySaver = field(default_factory=InMemorySaver)
    role: Role = Role.OPERATOR
    demo_date: str = "2026-03-18"
    read_s: float = 5.0
    max_attempts: int = 3

    def __post_init__(self) -> None:
        self._tasks: dict[str, TaskRecord] = {}
        self._cancel_events: dict[str, threading.Event] = {}
        self._lock = threading.Lock()
        self.audit = AuditLog(self.audit_path)

    # -- 提交与后台执行 ------------------------------------------------------
    def submit(self, question: str) -> TaskRecord:
        task_id = f"task-{uuid.uuid4().hex[:12]}"
        rec = TaskRecord(task_id=task_id, question=question,
                         created_at=_now(), thread_id=task_id)
        with self._lock:
            self._tasks[task_id] = rec
            self._cancel_events[task_id] = threading.Event()
        threading.Thread(target=self._execute, args=(task_id,), daemon=True).start()
        return rec

    def _make_ctx(self, task_id: str) -> ToolContext:
        return ToolContext(
            client=JavaClient(self.java_base_url, read_s=self.read_s,
                              max_attempts=self.max_attempts),
            audit=self.audit, task_id=task_id, trace_id=task_id,
            role=self.role, cancel_event=self._cancel_events[task_id],
            demo_date=self.demo_date,
        )

    def _execute(self, task_id: str) -> None:
        rec = self._tasks[task_id]
        self._set_status(rec, "running")
        ctx = self._make_ctx(task_id)
        try:
            outcome = run_analysis(ctx, self.checkpointer, rec.question)
        except TaskCancelled as e:
            self._finish(rec, "cancelled", {"reason": str(e)})
            return
        except Exception as e:  # noqa: BLE001 —— 任务失败要可见，不能让线程静默死亡
            self._finish(rec, "failed", {"error": f"{type(e).__name__}: {e}"})
            return
        if outcome["status"] == "waiting_approval":
            with self._lock:
                rec.status = "waiting_approval"
                rec.approval_request = outcome["approval_request"]
            self.audit.record(trace_id=task_id, actor="agent-p3", role=self.role.value,
                              tool="human_approval", args=outcome["approval_request"]["args"],
                              outcome="waiting", detail="高风险调整等待人工审批")
        else:
            self._finish(rec, "succeeded", {"final": outcome["final"]})

    # -- 查询 / 审批 / 取消 ---------------------------------------------------
    def get(self, task_id: str) -> TaskRecord:
        rec = self._tasks.get(task_id)
        if rec is None:
            raise TaskNotFound(task_id)
        return rec

    def decide(self, task_id: str, decision: str, operator: str) -> TaskRecord:
        """审批决定：approve / reject（ch48：拒绝也是一等结果，落审计）。"""
        rec = self.get(task_id)
        with self._lock:
            if rec.status != "waiting_approval":
                raise TaskConflict(f"任务状态为 {rec.status}，不能审批（仅 waiting_approval 可审）")
            rec.status = "deciding"  # 防并发双审的过渡态
        if decision not in {"approve", "reject"}:
            with self._lock:
                rec.status = "waiting_approval"
            raise TaskConflict(f"decision 必须是 approve/reject，得到 {decision!r}")
        self.audit.record(trace_id=task_id, actor=operator, role="reviewer",
                          tool="human_approval", args=rec.approval_request or {},
                          outcome="approved" if decision == "approve" else "rejected",
                          detail=f"decision={decision}")
        ctx = self._make_ctx(task_id)
        try:
            outcome = resume_analysis(ctx, self.checkpointer, task_id, decision)
        except TaskCancelled as e:
            self._finish(rec, "cancelled", {"reason": str(e)})
            return rec
        except Exception as e:  # noqa: BLE001
            self._finish(rec, "failed", {"error": f"{type(e).__name__}: {e}"})
            return rec
        self._finish(rec, "succeeded", {"final": outcome["final"],
                                        "decision": decision, "operator": operator})
        return rec

    def cancel(self, task_id: str) -> TaskRecord:
        rec = self.get(task_id)
        with self._lock:
            if rec.status in TERMINAL:
                raise TaskConflict(f"任务已是终态 {rec.status}，不可取消")
            if rec.status == "waiting_approval":
                prev = rec.status
                rec.status = "cancelled"  # 挂起中的审批直接撤销（无需工具协作）
                rec.result = {"reason": "审批前取消"}
            else:
                prev = rec.status
                self._cancel_events[task_id].set()  # 协作式：工具入口下一个检查点生效
                rec.status = "cancelling"
        self.audit.record(trace_id=task_id, actor="api", role="system",
                          tool="cancel_task", args={}, outcome="cancelled",
                          detail=f"取消自状态 {prev}")
        return rec

    # -- 内部 ------------------------------------------------------------------
    def _set_status(self, rec: TaskRecord, status: str) -> None:
        with self._lock:
            rec.status = status

    def _finish(self, rec: TaskRecord, status: str, result: dict[str, Any]) -> None:
        with self._lock:
            rec.status = status
            rec.result = result


def _now() -> str:
    import time

    return time.strftime("%Y-%m-%dT%H:%M:%S")
