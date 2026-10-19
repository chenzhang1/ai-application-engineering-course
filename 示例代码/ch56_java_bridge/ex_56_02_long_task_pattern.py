# EX-56-02 | 长任务模式：202 Accepted + task_id + 轮询 + 取消（对接 Java 异步 API）
# 运行: python3 示例代码/ch56_java_bridge/ex_56_02_long_task_pattern.py
"""完整可运行（httpx + 线程内 Java 替身 /tasks 端点，确定性）：

同步 HTTP 调用撑不住"分析跑 2 分钟"：网关 30s 掐断、客户端重试造成重复执行、
用户刷新页面请求就丢了。长任务模式是标准解（56.4 的状态机图）：

    POST /tasks          → 202 Accepted + {"task_id", "status": "pending"}（立即返回！）
    GET  /tasks/{id}     → 200 {"status": "pending|running|succeeded|cancelled", "result": ...}
    DELETE /tasks/{id}   → 202 {"status": "cancelled"}（协作式取消）| 409 已结束

Python 侧三件套：
    1. 提交后只拿 task_id（绝不阻塞等结果）；
    2. 轮询带间隔与上限（本例 0.1s × 50 次；生产用指数间隔 + 超时上限 + 回调/SSE 通知）；
    3. 取消是"请求 + 确认"两步：DELETE 返回 202 只代表请求受理，状态变 cancelled 才算数。
项目三的 POST /analysis 就是本模式在 Python 侧对外提供时的样子（角色对调：FastAPI 当服务方）。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stub_java_service import StubJavaService  # noqa: E402


class TaskHandle:
    """一个长任务的客户端句柄：提交一次，随后的查询/取消都凭 task_id。"""

    def __init__(self, client: httpx.Client, task_id: str) -> None:
        self._client = client
        self.task_id = task_id

    def poll(self) -> dict[str, Any]:
        r = self._client.get(f"/tasks/{self.task_id}")
        r.raise_for_status()
        return r.json()

    def wait(self, *, interval_s: float = 0.1, max_polls: int = 50) -> dict[str, Any]:
        """轮询到终态（succeeded/failed/cancelled）；超过 max_polls 抛超时——
        轮询必须带上限，否则上游卡死时调用方跟着挂死（ch15 的规矩）。"""
        for i in range(max_polls):
            snap = self.poll()
            if snap["status"] in {"succeeded", "failed", "cancelled"}:
                return snap
            if i == max_polls - 1:
                raise TimeoutError(f"任务 {self.task_id} 轮询 {max_polls} 次仍未终态")
            time.sleep(interval_s)
        raise TimeoutError("unreachable")

    def cancel(self) -> dict[str, Any]:
        r = self._client.delete(f"/tasks/{self.task_id}")
        if r.status_code == 409:  # 已结束的任务不可取消
            return {"cancelled": False, "reason": "task_already_finished"}
        r.raise_for_status()
        return {"cancelled": True, **r.json()}


def submit_task(client: httpx.Client, payload: dict[str, Any]) -> TaskHandle:
    """提交长任务：202 Accepted 才算受理成功（200 反而要警惕——可能不是异步语义）。"""
    r = client.post("/tasks", json=payload)
    if r.status_code != 202:
        raise RuntimeError(f"预期 202，实际 {r.status_code}：{r.text[:100]}")
    body = r.json()
    print(f"    ← 202 Accepted，task_id={body['task_id']}（立即返回，不阻塞）")
    return TaskHandle(client, body["task_id"])


def main() -> None:
    svc = StubJavaService()
    base = svc.start()
    client = httpx.Client(base_url=base, timeout=httpx.Timeout(connect=2.0, read=5.0, write=2.0, pool=2.0))
    print(f"== 长任务模式（目标服务 {base}）==\n")

    print("[1] 正常路径：提交 → 轮询到 succeeded")
    t0 = time.monotonic()
    handle = submit_task(client, {"duration_s": 0.4})
    snap = handle.wait(interval_s=0.1)
    print(f"    终态：{snap['status']}，result={snap['result']}（等待 {time.monotonic()-t0:.1f}s）")

    print("\n[2] 取消路径：提交 → DELETE → 状态变 cancelled")
    h2 = submit_task(client, {"duration_s": 3.0})
    print(f"    cancel → {h2.cancel()}")
    print(f"    poll   → {h2.poll()['status']}（协作式取消：任务线程每 0.05s 查一次标志位）")

    print("\n[3] 取消已结束的任务 → 409 Conflict（终态不可撤销）")
    print(f"    cancel → {handle.cancel()}")

    print("\n[4] 查询不存在的任务 → 404")
    r = client.get("/tasks/TASK-nope")
    print(f"    GET /tasks/TASK-nope → {r.status_code} {r.json()}")

    print("\n模式要点：202 只代表'受理'；状态机 pending→running→succeeded|cancelled|failed")
    print("由服务方维护；Python 侧唯一职责是凭 task_id 查询/取消并给轮询加上限。")
    svc.stop()


if __name__ == "__main__":
    main()
