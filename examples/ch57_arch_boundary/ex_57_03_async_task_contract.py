# EX-57-03 | 异步任务模式：提交-查询-取消的最小契约与幂等提交 | 运行: python3 examples/ch57_arch_boundary/ex_57_03_async_task_contract.py
"""完整可运行（纯标准库，离线）：演示长任务集成模式的契约——
Spring 侧 POST 提交任务拿 job_id，轮询 GET 查状态，DELETE 请求取消。

三个关键设计点：
  1) 幂等提交：同一个 idempotency_key 重复提交返回同一个 job（网络重试不会重复执行）；
  2) 状态机单向流转：QUEUED → RUNNING → SUCCEEDED / FAILED，CANCELLED 只能从
     QUEUED/RUNNING 进入——终态拒绝一切转移；
  3) 取消是"请求"不是"保证"：RUNNING 中的任务收到取消请求后，由任务自身在安全点退出。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


# 终态集合：终态之后任何转移都拒绝（状态机的"单向阀"）
_TERMINAL = {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED}


@dataclass
class Job:
    job_id: str
    kind: str
    payload: dict[str, str]
    status: JobStatus = JobStatus.QUEUED
    result: str | None = None
    history: list[str] = field(default_factory=list)

    def _transition(self, nxt: JobStatus) -> None:
        if self.status in _TERMINAL:
            raise ValueError(f"任务 {self.job_id} 已处于终态 {self.status.value}，拒绝转移到 {nxt.value}")
        self.history.append(f"{self.status.value}->{nxt.value}")
        self.status = nxt


class TaskStore:
    """最小任务仓库（生产实现是数据库/Redis + 后台 worker，契约与这里完全一致）。"""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._idem: dict[str, str] = {}      # idempotency_key -> job_id

    def submit(self, kind: str, payload: dict[str, str], idempotency_key: str) -> tuple[Job, bool]:
        """返回 (任务, 是否新建)。同一幂等键重复提交 → 返回已有任务，绝不重复执行。"""
        if idempotency_key in self._idem:
            return self._jobs[self._idem[idempotency_key]], False
        job = Job(job_id=uuid.uuid4().hex[:12], kind=kind, payload=payload)
        self._jobs[job.job_id] = job
        self._idem[idempotency_key] = job.job_id
        return job, True

    def get(self, job_id: str) -> Job:
        return self._jobs[job_id]

    def advance(self, job_id: str) -> JobStatus:
        """模拟 worker 推进一格：QUEUED→RUNNING→SUCCEEDED；终态拒绝推进。"""
        job = self._jobs[job_id]
        if job.status is JobStatus.QUEUED:
            job._transition(JobStatus.RUNNING)
        elif job.status is JobStatus.RUNNING:
            job._transition(JobStatus.SUCCEEDED)
            job.result = f"done: {job.kind}"
        else:
            raise ValueError(f"任务 {job_id} 已处于终态 {job.status.value}，worker 拒绝推进")
        return job.status

    def cancel(self, job_id: str) -> bool:
        """取消：非终态才可取消；返回是否真的取消。RUNNING 的取消是'请求'，worker 在安全点响应。"""
        job = self._jobs[job_id]
        if job.status in _TERMINAL:
            return False
        job._transition(JobStatus.CANCELLED)
        return True


def main() -> None:
    store = TaskStore()

    print("── 1) 正常生命周期：提交 → 推进 → 完成 ──")
    job, created = store.submit("batch_summary", {"batch": "2026-10-19"}, idem_key := "spring-req-1001")
    print(f"    提交：job_id={job.job_id} status={job.status.value} created={created}")
    store.advance(job.job_id)
    print(f"    轮询 1：status={store.get(job.job_id).status.value}")
    store.advance(job.job_id)
    print(f"    轮询 2：status={store.get(job.job_id).status.value} result={store.get(job.job_id).result}")

    print("\n── 2) 幂等提交：Spring 超时重发同一个请求（同一个幂等键）──")
    again, created2 = store.submit("batch_summary", {"batch": "2026-10-19"}, idem_key)
    print(f"    二次提交：created={created2}，返回的是同一个 job？{again.job_id == job.job_id}")
    print(f"    （若不做幂等：同一批文档会被摘要两遍——token 双倍计费 + 结果互相覆盖）")

    print("\n── 3) 取消语义：RUNNING 可请求取消，终态拒绝 ──")
    job2, _ = store.submit("batch_ingest", {"docs": "12"}, "spring-req-1002")
    store.advance(job2.job_id)                      # → RUNNING
    print(f"    RUNNING 中请求取消 → 成功？{store.cancel(job2.job_id)}")
    print(f"    再推进（worker 迟到的消息到达）→ ", end="")
    try:
        store.advance(job2.job_id)
    except ValueError as exc:
        print(f"ValueError: {exc}")
    print(f"    对已完成任务请求取消 → 成功？{store.cancel(job.job_id)}（终态不可取消，返回 false 即可，不要报错）")

    print("\n[给 Spring 侧的对接提示] 轮询间隔用指数退避（1s→2s→4s，上限 10s）；")
    print("  结果保留设 TTL（如 24h）过期清理；job_id 要写进日志与 trace_id 串联（ch60）。")


if __name__ == "__main__":
    main()
